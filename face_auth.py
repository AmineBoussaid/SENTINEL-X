from __future__ import annotations

import os
import re
import shutil
import threading
import unicodedata
from pathlib import Path

import cv2
import numpy as np


BASE_DIR = Path(__file__).resolve().parent
FACES_DIR = BASE_DIR / "visages_connus"
YUNET_MODEL = (
    BASE_DIR
    / "models"
    / "face_detection_yunet_2023mar.onnx"
)
SFACE_MODEL = (
    BASE_DIR
    / "models"
    / "face_recognition_sface_2021dec.onnx"
)

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp"
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MATCH_THRESHOLD = float(
    os.getenv(
        "FACE_LOGIN_THRESHOLD",
        "0.30"
    )
)

_model_lock = threading.RLock()
_detector = None
_recognizer = None
_profile_cache: dict[
    str,
    tuple[tuple, list[np.ndarray]]
] = {}


class FaceAuthError(ValueError):
    pass


def _models():
    global _detector
    global _recognizer

    if _detector is not None:
        return _detector, _recognizer

    if not YUNET_MODEL.is_file():
        raise FaceAuthError(
            "Le modèle YuNet est introuvable."
        )

    if not SFACE_MODEL.is_file():
        raise FaceAuthError(
            "Le modèle SFace est introuvable."
        )

    _detector = cv2.FaceDetectorYN_create(
        str(YUNET_MODEL),
        "",
        (320, 320),
        0.9,
        0.3,
        5000
    )
    _recognizer = cv2.FaceRecognizerSF_create(
        str(SFACE_MODEL),
        ""
    )

    return _detector, _recognizer


def _decode_image(payload: bytes):
    if not payload:
        raise FaceAuthError(
            "Une image importée est vide."
        )

    if len(payload) > MAX_IMAGE_BYTES:
        raise FaceAuthError(
            "Chaque image doit faire moins de 5 Mo."
        )

    image = cv2.imdecode(
        np.frombuffer(
            payload,
            dtype=np.uint8
        ),
        cv2.IMREAD_COLOR
    )

    if image is None:
        raise FaceAuthError(
            "Une image importée est illisible."
        )

    return image


def _embedding(image):
    with _model_lock:
        detector, recognizer = _models()
        height, width = image.shape[:2]
        detector.setInputSize(
            (width, height)
        )
        _, faces = detector.detect(image)

        if faces is None or len(faces) == 0:
            raise FaceAuthError(
                "Aucun visage détecté sur une image."
            )

        if len(faces) > 1:
            raise FaceAuthError(
                "Une image ne doit contenir qu'un seul visage."
            )

        aligned = recognizer.alignCrop(
            image,
            faces[0]
        )
        return recognizer.feature(
            aligned
        )


def _folder_part(value: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        value
    ).encode(
        "ascii",
        "ignore"
    ).decode("ascii")

    cleaned = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        normalized.strip()
    ).strip("_")

    return cleaned or "Utilisateur"


def save_profile_images(
    files,
    first_name: str,
    last_name: str
) -> tuple[str | None, int]:
    uploads = [
        file
        for file in files
        if file and file.filename
    ]

    # Un compte sans image reste autorisé :
    # son login utilisera uniquement le mot de passe.
    if not uploads:
        return None, 0

    validated: list[
        tuple[str, bytes]
    ] = []

    for upload in uploads:
        extension = Path(
            upload.filename
        ).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise FaceAuthError(
                "Formats acceptés : JPG, JPEG, PNG et BMP."
            )

        payload = upload.read()
        image = _decode_image(payload)

        # Calcule une empreinte maintenant pour refuser
        # les images inutilisables avant la création du compte.
        _embedding(image)
        validated.append(
            (extension, payload)
        )

    FACES_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    base_name = (
        f"{_folder_part(first_name)}_"
        f"{_folder_part(last_name)}"
    )
    folder_name = base_name
    counter = 2

    while (
        FACES_DIR
        / folder_name
    ).exists():
        folder_name = (
            f"{base_name}_{counter}"
        )
        counter += 1

    folder = FACES_DIR / folder_name
    folder.mkdir()

    try:
        for index, (
            extension,
            payload
        ) in enumerate(
            validated,
            start=1
        ):
            (
                folder
                / f"photo_{index}{extension}"
            ).write_bytes(payload)
    except Exception:
        shutil.rmtree(
            folder,
            ignore_errors=True
        )
        raise

    return folder_name, len(validated)


def remove_profile_folder(
    folder_name: str | None
) -> None:
    if not folder_name:
        return

    target = (
        FACES_DIR
        / Path(folder_name).name
    ).resolve()
    faces_root = FACES_DIR.resolve()

    if target.parent != faces_root:
        return

    shutil.rmtree(
        target,
        ignore_errors=True
    )
    _profile_cache.pop(
        folder_name,
        None
    )


def profile_exists(
    folder_name: str | None
) -> bool:
    if not folder_name:
        return False

    folder = (
        FACES_DIR
        / Path(folder_name).name
    )

    return (
        folder.is_dir()
        and any(
            path.suffix.lower()
            in ALLOWED_EXTENSIONS
            for path in folder.iterdir()
        )
    )


def _profile_embeddings(
    folder_name: str
) -> list[np.ndarray]:
    folder = (
        FACES_DIR
        / Path(folder_name).name
    )

    if not folder.is_dir():
        raise FaceAuthError(
            "Profil facial introuvable."
        )

    paths = sorted(
        path
        for path in folder.iterdir()
        if path.suffix.lower()
        in ALLOWED_EXTENSIONS
    )
    signature = tuple(
        (
            path.name,
            path.stat().st_mtime_ns,
            path.stat().st_size
        )
        for path in paths
    )

    cached = _profile_cache.get(
        folder_name
    )

    if cached and cached[0] == signature:
        return cached[1]

    embeddings = []

    for path in paths:
        image = _decode_image(
            path.read_bytes()
        )
        embeddings.append(
            _embedding(image)
        )

    if not embeddings:
        raise FaceAuthError(
            "Le profil ne contient aucune image valide."
        )

    _profile_cache[folder_name] = (
        signature,
        embeddings
    )

    return embeddings


def verify_face(
    payload: bytes,
    folder_name: str
) -> tuple[bool, float]:
    test_embedding = _embedding(
        _decode_image(payload)
    )
    references = _profile_embeddings(
        folder_name
    )

    with _model_lock:
        _, recognizer = _models()
        scores = [
            float(
                recognizer.match(
                    reference,
                    test_embedding,
                    cv2.FaceRecognizerSF_FR_COSINE
                )
            )
            for reference in references
        ]

    best_score = max(scores)

    return (
        best_score >= MATCH_THRESHOLD,
        round(best_score, 3)
    )
