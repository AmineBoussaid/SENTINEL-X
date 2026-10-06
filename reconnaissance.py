import cv2
import os
import time
import winsound
import numpy as np


# ==========================================================
# CONFIGURATION SENTINEL-X
# ==========================================================

DOSSIER_VISAGES = "visages_connus"

# LBPH :
# plus le score est PETIT, meilleure est la correspondance.
#
# 45-50 = assez strict
# 55-60 = plus permissif
#
# NE PAS remettre 80.
SEUIL_RECONNAISSANCE = 50.0

# Nombre d'échecs consécutifs avant alarme
MAX_ECHECS = 3

# Une vraie tentative toutes les 1.5 secondes
DELAI_ENTRE_ESSAIS = 1.5

# Après combien de secondes sans visage on réinitialise
DELAI_RESET_ABSENCE = 3.0


# ==========================================================
# VERIFICATION OPENCV
# ==========================================================

if not hasattr(cv2, "face"):
    print()
    print("ERREUR : cv2.face n'est pas disponible.")
    print()
    print("Installe OpenCV Contrib avec :")
    print("pip install opencv-contrib-python==4.12.0.88")
    exit()


# ==========================================================
# HAAR CASCADE
# ==========================================================

cascade_path = (
    cv2.data.haarcascades
    + "haarcascade_frontalface_default.xml"
)

detecteur = cv2.CascadeClassifier(cascade_path)

if detecteur.empty():
    print("ERREUR : impossible de charger Haar Cascade.")
    exit()


# ==========================================================
# RECONNAISSEUR LBPH
# ==========================================================

reconnaisseur = cv2.face.LBPHFaceRecognizer_create()

visages_entrainement = []
labels_entrainement = []

noms = {}

label_actuel = 0


# ==========================================================
# CHARGEMENT DES PHOTOS
# ==========================================================

print()
print("==========================================")
print("       SENTINEL-X RECONNAISSANCE")
print("==========================================")
print()
print("Chargement des personnes autorisees...")
print()


if not os.path.isdir(DOSSIER_VISAGES):

    print(
        f"ERREUR : le dossier '{DOSSIER_VISAGES}' "
        "n'existe pas."
    )

    exit()


extensions_valides = (
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp"
)


for nom_personne in sorted(os.listdir(DOSSIER_VISAGES)):

    dossier_personne = os.path.join(
        DOSSIER_VISAGES,
        nom_personne
    )

    if not os.path.isdir(dossier_personne):
        continue


    nombre_visages = 0


    for fichier in sorted(os.listdir(dossier_personne)):

        if not fichier.lower().endswith(extensions_valides):
            continue


        chemin = os.path.join(
            dossier_personne,
            fichier
        )


        image = cv2.imread(chemin)


        if image is None:

            print(
                f"Image illisible : "
                f"{nom_personne}/{fichier}"
            )

            continue


        gris = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )


        # Uniformise un peu la lumière
        gris = cv2.equalizeHist(gris)


        detections = detecteur.detectMultiScale(
            gris,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(80, 80)
        )


        if len(detections) == 0:

            print(
                f"Aucun visage detecte : "
                f"{nom_personne}/{fichier}"
            )

            continue


        # Prend le plus grand visage de la photo
        x, y, w, h = max(
            detections,
            key=lambda rectangle:
                rectangle[2] * rectangle[3]
        )


        visage = gris[
            y:y + h,
            x:x + w
        ]


        visage = cv2.resize(
            visage,
            (200, 200)
        )


        visages_entrainement.append(
            visage
        )

        labels_entrainement.append(
            label_actuel
        )


        nombre_visages += 1


        print(
            f"OK : {nom_personne} / {fichier}"
        )


    if nombre_visages > 0:

        noms[label_actuel] = nom_personne

        print(
            f"> {nom_personne} : "
            f"{nombre_visages} photo(s)"
        )

        print()

        label_actuel += 1


# ==========================================================
# VERIFICATION DES DONNEES
# ==========================================================

if len(visages_entrainement) == 0:

    print()
    print("ERREUR : aucun visage exploitable.")
    print()

    exit()


# ==========================================================
# ENTRAINEMENT
# ==========================================================

reconnaisseur.train(
    visages_entrainement,
    np.array(labels_entrainement)
)


print()
print("==========================================")
print("       PERSONNES AUTORISEES")
print("==========================================")

for nom in noms.values():

    print("->", nom)


print()
print(
    "Nombre total de photos utilisees :",
    len(visages_entrainement)
)

print()
print("Ouverture de la webcam...")
print()


# ==========================================================
# WEBCAM
# ==========================================================

camera = cv2.VideoCapture(
    0,
    cv2.CAP_DSHOW
)


if not camera.isOpened():

    # Deuxième tentative
    camera = cv2.VideoCapture(0)


if not camera.isOpened():

    print("ERREUR : impossible d'ouvrir la webcam.")

    exit()


camera.set(
    cv2.CAP_PROP_FRAME_WIDTH,
    1280
)

camera.set(
    cv2.CAP_PROP_FRAME_HEIGHT,
    720
)


# ==========================================================
# VARIABLES
# ==========================================================

echecs = 0

dernier_essai = 0

dernier_visage_vu = time.time()

alarme_declenchee = False


# ==========================================================
# ALARME SONORE
# ==========================================================

def alarme():

    print()
    print("############################################")
    print("### ALERTE : PERSONNE NON AUTORISEE !!! ###")
    print("############################################")
    print()

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
# BOUCLE PRINCIPALE
# ==========================================================

print("SENTINEL-X actif.")
print("Appuie sur Q pour quitter.")
print()


while True:

    ok, frame = camera.read()


    if not ok:

        print(
            "Erreur pendant la lecture de la webcam."
        )

        break


    gris = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )


    gris = cv2.equalizeHist(
        gris
    )


    detections = detecteur.detectMultiScale(
        gris,
        scaleFactor=1.1,
        minNeighbors=6,
        minSize=(100, 100)
    )


    # Résultat de cette image
    personne_connue = False
    personne_inconnue = False

    meilleur_nom = None
    meilleur_score = None


    # ======================================================
    # ANALYSE DES VISAGES
    # ======================================================

    for (x, y, w, h) in detections:

        dernier_visage_vu = time.time()


        visage = gris[
            y:y + h,
            x:x + w
        ]


        visage = cv2.resize(
            visage,
            (200, 200)
        )


        label, score = reconnaisseur.predict(
            visage
        )


        # --------------------------------------------------
        # PERSONNE CONNUE
        # --------------------------------------------------

        if (
            label in noms
            and score <= SEUIL_RECONNAISSANCE
        ):

            nom = noms[label]

            personne_connue = True

            couleur = (
                0,
                255,
                0
            )

            texte = (
                f"{nom} | score {score:.1f}"
            )


            if (
                meilleur_score is None
                or score < meilleur_score
            ):

                meilleur_score = score
                meilleur_nom = nom


        # --------------------------------------------------
        # PERSONNE INCONNUE
        # --------------------------------------------------

        else:

            personne_inconnue = True

            couleur = (
                0,
                0,
                255
            )

            texte = (
                f"INCONNU | score {score:.1f}"
            )


        # Rectangle
        cv2.rectangle(
            frame,
            (x, y),
            (x + w, y + h),
            couleur,
            3
        )


        # Nom / score
        cv2.putText(
            frame,
            texte,
            (x, max(30, y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            couleur,
            2
        )


    maintenant = time.time()


    # ======================================================
    # VISAGE INCONNU
    # ======================================================

    # S'il y a au moins un inconnu,
    # on considère la tentative comme échouée.
    if personne_inconnue:

        if (
            maintenant - dernier_essai
            >= DELAI_ENTRE_ESSAIS
        ):

            dernier_essai = maintenant


            if echecs < MAX_ECHECS:

                echecs += 1


            print(
                f"Echec reconnaissance : "
                f"{echecs}/{MAX_ECHECS}"
            )


            # ----------------------------------------------
            # ALARME AU 3e ECHEC
            # ----------------------------------------------

            if (
                echecs >= MAX_ECHECS
                and not alarme_declenchee
            ):

                alarme()

                alarme_declenchee = True


    # ======================================================
    # PERSONNE CONNUE
    # ======================================================

    elif personne_connue:

        if (
            echecs > 0
            or alarme_declenchee
        ):

            print(
                f"Personne autorisee reconnue : "
                f"{meilleur_nom}"
            )

            print(
                "Compteur remis a zero."
            )


        echecs = 0

        alarme_declenchee = False


    # ======================================================
    # AUCUN VISAGE
    # ======================================================

    elif len(detections) == 0:

        if (
            maintenant - dernier_visage_vu
            >= DELAI_RESET_ABSENCE
        ):

            if (
                echecs > 0
                or alarme_declenchee
            ):

                print(
                    "Aucun visage -> "
                    "compteur remis a zero."
                )


            echecs = 0

            alarme_declenchee = False


    # ======================================================
    # AFFICHAGE DU STATUT
    # ======================================================

    if echecs == 0:

        statut = "SURVEILLANCE ACTIVE"

        couleur_statut = (
            0,
            255,
            0
        )


    elif echecs < MAX_ECHECS:

        statut = (
            f"ECHEC {echecs}/{MAX_ECHECS}"
        )

        couleur_statut = (
            0,
            165,
            255
        )


    else:

        statut = (
            "ALERTE - PERSONNE INCONNUE"
        )

        couleur_statut = (
            0,
            0,
            255
        )


    cv2.putText(
        frame,
        statut,
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        couleur_statut,
        2
    )


    cv2.putText(
        frame,
        f"Echecs : {echecs}/{MAX_ECHECS}",
        (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )


    cv2.imshow(
        "SENTINEL-X - Reconnaissance faciale",
        frame
    )


    touche = cv2.waitKey(1) & 0xFF


    if touche == ord("q"):

        break


# ==========================================================
# FIN DU PROGRAMME
# ==========================================================

camera.release()

cv2.destroyAllWindows()

print()
print("SENTINEL-X Vision arrete.")