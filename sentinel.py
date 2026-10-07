import cv2
import os
import time
import winsound
import serial


# ==========================================================
# CONFIGURATION
# ==========================================================

PORT = "COM8"
VITESSE = 115200

DOSSIER_VISAGES = "visages_connus"

MODELE_YUNET = os.path.join(
    "models",
    "face_detection_yunet_2023mar.onnx"
)

MODELE_SFACE = os.path.join(
    "models",
    "face_recognition_sface_2021dec.onnx"
)

SEUIL_RECONNAISSANCE = 0.30

MAX_ECHECS = 3

DELAI_RECONNAISSANCE = 1.5

SEUIL_TEMPERATURE = 40.0
SEUIL_HUMIDITE = 70.0

DELAI_ALERTE_CAPTEUR = 5


# ==========================================================
# ALARME
# ==========================================================

def alarme():

    winsound.Beep(
        1000,
        250
    )

    winsound.Beep(
        1400,
        250
    )

    winsound.Beep(
        1800,
        700
    )


# ==========================================================
# CONNEXION ESP8266
# ==========================================================

print()
print(
    "Connexion a l'ESP8266..."
)

try:

    esp = serial.Serial(
        PORT,
        VITESSE,
        timeout=1
    )

except serial.SerialException:

    print()
    print(
        f"ERREUR : impossible "
        f"d'ouvrir {PORT}"
    )

    print(
        "Verifie le port COM."
    )

    exit()


time.sleep(2)

esp.reset_input_buffer()


# ==========================================================
# CHARGEMENT YUNET + SFACE
# ==========================================================

print()
print(
    "Chargement reconnaissance faciale..."
)


detecteur = cv2.FaceDetectorYN_create(
    MODELE_YUNET,
    "",
    (320, 320),
    0.9,
    0.3,
    5000
)


reconnaisseur = (
    cv2.FaceRecognizerSF_create(
        MODELE_SFACE,
        ""
    )
)


# ==========================================================
# DETECTION
# ==========================================================

def detecter_visages(image):

    hauteur, largeur = (
        image.shape[:2]
    )

    detecteur.setInputSize(
        (
            largeur,
            hauteur
        )
    )

    resultat = (
        detecteur.detect(
            image
        )
    )

    if resultat[1] is None:
        return []

    return resultat[1]


# ==========================================================
# CREATION EMPREINTE
# ==========================================================

def creer_empreinte(
    image,
    visage
):

    try:

        aligne = (
            reconnaisseur.alignCrop(
                image,
                visage
            )
        )

        return (
            reconnaisseur.feature(
                aligne
            )
        )

    except cv2.error:

        return None


# ==========================================================
# CHARGEMENT PERSONNES AUTORISEES
# ==========================================================

base_visages = {}

extensions = (
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp"
)


print()
print(
    "Personnes autorisees :"
)


for nom in sorted(
    os.listdir(
        DOSSIER_VISAGES
    )
):

    dossier = os.path.join(
        DOSSIER_VISAGES,
        nom
    )

    if not os.path.isdir(
        dossier
    ):
        continue


    empreintes = []


    for fichier in os.listdir(
        dossier
    ):

        if not fichier.lower().endswith(
            extensions
        ):
            continue


        chemin = os.path.join(
            dossier,
            fichier
        )


        image = cv2.imread(
            chemin
        )


        if image is None:
            continue


        visages = detecter_visages(
            image
        )


        if len(visages) == 0:
            continue


        visage = max(
            visages,
            key=lambda v:
                float(v[2])
                * float(v[3])
        )


        empreinte = creer_empreinte(
            image,
            visage
        )


        if empreinte is not None:

            empreintes.append(
                empreinte
            )


    if empreintes:

        base_visages[nom] = (
            empreintes
        )

        print(
            f"-> {nom} : "
            f"{len(empreintes)} photos"
        )


if not base_visages:

    print(
        "Aucun visage connu charge."
    )

    esp.close()

    exit()


# ==========================================================
# COMPARAISON
# ==========================================================

def reconnaitre(
    empreinte_test
):

    meilleur_nom = None

    meilleur_score = -1


    for nom, empreintes in (
        base_visages.items()
    ):

        for empreinte in empreintes:

            score = (
                reconnaisseur.match(
                    empreinte,
                    empreinte_test,
                    cv2.FaceRecognizerSF_FR_COSINE
                )
            )


            if score > meilleur_score:

                meilleur_score = score

                meilleur_nom = nom


    if (
        meilleur_score
        >= SEUIL_RECONNAISSANCE
    ):

        return (
            True,
            meilleur_nom,
            meilleur_score
        )


    return (
        False,
        "INCONNU",
        meilleur_score
    )


# ==========================================================
# PHASE 1
# RECONNAISSANCE FACIALE
# ==========================================================

print()
print(
    "=========================================="
)

print(
    "    PHASE 1 - RECONNAISSANCE FACIALE"
)

print(
    "=========================================="
)

print()


camera = cv2.VideoCapture(
    0,
    cv2.CAP_DSHOW
)


if not camera.isOpened():

    camera = (
        cv2.VideoCapture(0)
    )


if not camera.isOpened():

    print(
        "Impossible d'ouvrir "
        "la webcam."
    )

    esp.close()

    exit()


echecs = 0

dernier_essai = 0

decision_terminee = False

personne_autorisee = False


while not decision_terminee:

    ok, frame = camera.read()


    if not ok:
        break


    visages = detecter_visages(
        frame
    )


    maintenant = time.time()


    for visage in visages:

        empreinte = (
            creer_empreinte(
                frame,
                visage
            )
        )


        if empreinte is None:
            continue


        reconnu, nom, score = (
            reconnaitre(
                empreinte
            )
        )


        x = int(
            visage[0]
        )

        y = int(
            visage[1]
        )

        w = int(
            visage[2]
        )

        h = int(
            visage[3]
        )


        # ==============================================
        # PERSONNE AUTORISEE
        # ==============================================

        if reconnu:

            couleur = (
                0,
                255,
                0
            )

            texte = (
                f"{nom} | "
                f"{score:.3f}"
            )


            cv2.rectangle(
                frame,
                (x, y),
                (x+w, y+h),
                couleur,
                3
            )


            cv2.putText(
                frame,
                texte,
                (
                    x,
                    max(
                        y - 10,
                        30
                    )
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                couleur,
                2
            )


            cv2.imshow(
                "SENTINEL-X",
                frame
            )

            cv2.waitKey(
                1000
            )


            print()
            print(
                "PERSONNE AUTORISEE :",
                nom
            )

            print(
                "Score :",
                round(
                    score,
                    3
                )
            )


            personne_autorisee = True

            decision_terminee = True

            break


        # ==============================================
        # PERSONNE NON RECONNUE
        # ==============================================

        else:

            couleur = (
                0,
                0,
                255
            )

            texte = (
                f"INCONNU | "
                f"{score:.3f}"
            )


            cv2.rectangle(
                frame,
                (x, y),
                (x+w, y+h),
                couleur,
                3
            )


            cv2.putText(
                frame,
                texte,
                (
                    x,
                    max(
                        y - 10,
                        30
                    )
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                couleur,
                2
            )


            if (
                maintenant
                - dernier_essai
                >= DELAI_RECONNAISSANCE
            ):

                dernier_essai = (
                    maintenant
                )

                echecs += 1


                print(
                    f"Echec reconnaissance "
                    f"{echecs}/{MAX_ECHECS}"
                )


                if (
                    echecs
                    >= MAX_ECHECS
                ):

                    print()
                    print(
                        "PERSONNE NON AUTORISEE"
                    )

                    alarme()

                    personne_autorisee = (
                        False
                    )

                    decision_terminee = (
                        True
                    )

                    break


    cv2.putText(
        frame,
        f"Echecs : "
        f"{echecs}/{MAX_ECHECS}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (
            255,
            255,
            255
        ),
        2
    )


    cv2.imshow(
        "SENTINEL-X - Identification",
        frame
    )


    if (
        cv2.waitKey(1) & 0xFF
        == ord("q")
    ):

        decision_terminee = True

        break


camera.release()

cv2.destroyAllWindows()


# ==========================================================
# DECISION ENVOYEE A L'ESP
# ==========================================================

print()
print(
    "=========================================="
)

print(
    "       DECISION SENTINEL-X"
)

print(
    "=========================================="
)


if personne_autorisee:

    print(
        "PERSONNE AUTORISEE"
    )

    print(
        "Detecteur mouvement : DESACTIVE"
    )

    esp.write(
        b"DESACTIVER_MOUVEMENT\n"
    )


else:

    print(
        "PERSONNE NON AUTORISEE"
    )

    print(
        "Detecteur mouvement : ACTIF"
    )

    esp.write(
        b"ACTIVER_MOUVEMENT\n"
    )


print(
    "Temperature : ACTIVE"
)

print(
    "Humidite : ACTIVE"
)

print()


time.sleep(1)


# ==========================================================
# PHASE 2
# SURVEILLANCE DES CAPTEURS
# ==========================================================

print(
    "=========================================="
)

print(
    "      PHASE 2 - SURVEILLANCE"
)

print(
    "=========================================="
)

print()


dernier_mouvement = 0

derniere_temperature = 0

derniere_humidite = 0


try:

    while True:

        ligne = (
            esp.readline()
            .decode(
                "utf-8",
                errors="ignore"
            )
            .strip()
        )


        if not ligne:
            continue


        print(
            ligne
        )


        maintenant = (
            time.time()
        )


        # ==============================================
        # MOUVEMENT
        # ==============================================

        if (
            "ALERTE_MOUVEMENT"
            in ligne
        ):

            if (
                maintenant
                - dernier_mouvement
                > DELAI_ALERTE_CAPTEUR
            ):

                print()
                print(
                    "!!! MOUVEMENT DETECTE !!!"
                )

                alarme()

                dernier_mouvement = (
                    maintenant
                )


        # ==============================================
        # TEMPERATURE
        # ==============================================

        if (
            "Temperature :"
            in ligne
        ):

            try:

                temperature = float(
                    ligne
                    .split(":")[1]
                    .replace(
                        "C",
                        ""
                    )
                    .strip()
                )


                if (
                    temperature
                    > SEUIL_TEMPERATURE
                ):

                    if (
                        maintenant
                        - derniere_temperature
                        > DELAI_ALERTE_CAPTEUR
                    ):

                        print()
                        print(
                            "!!! TEMPERATURE "
                            "TROP ELEVEE !!!"
                        )

                        alarme()

                        derniere_temperature = (
                            maintenant
                        )

            except ValueError:
                pass


        # ==============================================
        # HUMIDITE
        # ==============================================

        if (
            "Humidite :"
            in ligne
        ):

            try:

                humidite = float(
                    ligne
                    .split(":")[1]
                    .replace(
                        "%",
                        ""
                    )
                    .strip()
                )


                if (
                    humidite
                    > SEUIL_HUMIDITE
                ):

                    if (
                        maintenant
                        - derniere_humidite
                        > DELAI_ALERTE_CAPTEUR
                    ):

                        print()
                        print(
                            "!!! HUMIDITE "
                            "TROP ELEVEE !!!"
                        )

                        alarme()

                        derniere_humidite = (
                            maintenant
                        )

            except ValueError:
                pass


except KeyboardInterrupt:

    print()
    print(
        "Arret SENTINEL-X"
    )


finally:

    esp.close()