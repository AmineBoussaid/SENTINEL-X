import cv2
import os
import numpy as np
import winsound
import time

# =========================================================
# CONFIGURATION SENTINEL-X
# =========================================================

DOSSIER_VISAGES = "visages_connus"

# Avec LBPH : PLUS PETIT = meilleure correspondance
# 80 est assez permissif pour notre prototype
SEUIL_RECONNAISSANCE = 80.0

MAX_ECHECS = 3

# Une tentative toutes les 1,5 secondes
DELAI_ENTRE_ESSAIS = 1.5

# Si plus aucun visage pendant 2 secondes,
# on considère qu'une nouvelle personne pourra arriver
RESET_APRES_ABSENCE = 2.0


# =========================================================
# VERIFICATION OPENCV
# =========================================================

if not hasattr(cv2, "face"):
    print("ERREUR : cv2.face n'est pas disponible.")
    print("Installe :")
    print("pip install opencv-contrib-python==4.12.0.88")
    exit()


# =========================================================
# DETECTEUR DE VISAGES
# =========================================================

cascade_path = (
    cv2.data.haarcascades
    + "haarcascade_frontalface_default.xml"
)

detecteur = cv2.CascadeClassifier(cascade_path)

if detecteur.empty():
    print("ERREUR : impossible de charger Haar Cascade.")
    exit()


# =========================================================
# RECONNAISSEUR LBPH
# =========================================================

reconnaisseur = cv2.face.LBPHFaceRecognizer_create()

visages_entrainement = []
labels_entrainement = []

noms = {}

label_actuel = 0


# =========================================================
# CHARGEMENT DES PERSONNES CONNUES
# =========================================================

print()
print("======================================")
print("      SENTINEL-X - CHARGEMENT")
print("======================================")
print()

if not os.path.isdir(DOSSIER_VISAGES):
    print(
        f"ERREUR : dossier '{DOSSIER_VISAGES}' introuvable."
    )
    exit()


extensions_images = (
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

    visages_personne = 0

    for fichier in os.listdir(dossier_personne):

        if not fichier.lower().endswith(extensions_images):
            continue

        chemin = os.path.join(
            dossier_personne,
            fichier
        )

        image = cv2.imread(chemin)

        if image is None:
            print(f"Image impossible a lire : {chemin}")
            continue

        gris = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )

        # Améliore un peu les variations de lumière
        gris = cv2.equalizeHist(gris)

        detections = detecteur.detectMultiScale(
            gris,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(80, 80)
        )

        if len(detections) == 0:
            print(
                f"Aucun visage trouve : "
                f"{nom_personne}/{fichier}"
            )
            continue

        # On utilise le plus grand visage détecté
        x, y, w, h = max(
            detections,
            key=lambda r: r[2] * r[3]
        )

        visage = gris[y:y+h, x:x+w]

        visage = cv2.resize(
            visage,
            (200, 200)
        )

        visages_entrainement.append(visage)
        labels_entrainement.append(label_actuel)

        visages_personne += 1

        print(
            f"OK : {nom_personne} / {fichier}"
        )


    if visages_personne > 0:

        noms[label_actuel] = nom_personne

        print(
            f"> {nom_personne} : "
            f"{visages_personne} visage(s) charge(s)"
        )

        label_actuel += 1

    print()


# =========================================================
# VERIFICATION ENTRAINEMENT
# =========================================================

if len(visages_entrainement) == 0:
    print("ERREUR : aucun visage exploitable.")
    exit()


reconnaisseur.train(
    visages_entrainement,
    np.array(labels_entrainement)
)


print("======================================")
print("    PERSONNES AUTORISEES")
print("======================================")

for _, nom in noms.items():
    print("->", nom)

print()

print(
    f"Total images d'entrainement : "
    f"{len(visages_entrainement)}"
)

print()
print("Ouverture de la webcam...")


# =========================================================
# WEBCAM
# =========================================================

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("ERREUR : impossible d'ouvrir la webcam.")
    exit()


# Optionnel : résolution
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)


# =========================================================
# VARIABLES DE SECURITE
# =========================================================

echecs = 0

dernier_essai = 0

alarme_declenchee = False

dernier_visage_vu = time.time()


# =========================================================
# ALARME
# =========================================================

def alarme():

    print()
    print("########################################")
    print("### ALERTE : PERSONNE NON AUTORISEE ###")
    print("########################################")
    print()

    winsound.Beep(1000, 250)
    winsound.Beep(1400, 250)
    winsound.Beep(1800, 700)


# =========================================================
# BOUCLE PRINCIPALE
# =========================================================

while True:

    ok, image = camera.read()

    if not ok:
        print("Erreur lecture webcam.")
        break


    gris = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    gris = cv2.equalizeHist(gris)


    detections = detecteur.detectMultiScale(
        gris,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(100, 100)
    )


    visage_connu = False
    visage_inconnu = False


    # =====================================================
    # ANALYSE DES VISAGES
    # =====================================================

    for (x, y, w, h) in detections:

        dernier_visage_vu = time.time()

        visage = gris[y:y+h, x:x+w]

        visage = cv2.resize(
            visage,
            (200, 200)
        )


        label, distance = reconnaisseur.predict(
            visage
        )


        # =============================================
        # PERSONNE RECONNUE
        # =============================================

        if (
            label in noms
            and distance <= SEUIL_RECONNAISSANCE
        ):

            nom = noms[label]

            visage_connu = True

            couleur = (0, 255, 0)

            texte = (
                f"{nom} - score {distance:.0f}"
            )


        # =============================================
        # PERSONNE INCONNUE
        # =============================================

        else:

            nom = "INCONNU"

            visage_inconnu = True

            couleur = (0, 0, 255)

            texte = (
                f"INCONNU - score {distance:.0f}"
            )


        # Rectangle
        cv2.rectangle(
            image,
            (x, y),
            (x+w, y+h),
            couleur,
            3
        )


        # Nom
        cv2.putText(
            image,
            texte,
            (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            couleur,
            2
        )


    maintenant = time.time()


    # =====================================================
    # VISAGE INCONNU
    # =====================================================

    # Priorité sécurité :
    # s'il y a au moins un inconnu, on le compte,
    # même si une personne connue est aussi présente.

    if visage_inconnu:

        if (
            maintenant - dernier_essai
            >= DELAI_ENTRE_ESSAIS
        ):

            dernier_essai = maintenant

            # Le compteur ne dépassera JAMAIS 3
            if echecs < MAX_ECHECS:

                echecs += 1

                print(
                    f"Echec reconnaissance : "
                    f"{echecs}/{MAX_ECHECS}"
                )


            # =============================================
            # ALARME AU TROISIEME ECHEC
            # =============================================

            if (
                echecs >= MAX_ECHECS
                and not alarme_declenchee
            ):

                alarme()

                alarme_declenchee = True


    # =====================================================
    # PERSONNE AUTORISEE
    # =====================================================

    elif visage_connu:

        if echecs > 0 or alarme_declenchee:

            print(
                "Personne autorisee reconnue "
                "-> compteur remis a zero"
            )

        echecs = 0

        alarme_declenchee = False


    # =====================================================
    # AUCUN VISAGE
    # =====================================================

    elif len(detections) == 0:

        # Si personne n'est devant la caméra pendant
        # quelques secondes, on prépare une nouvelle session

        if (
            maintenant - dernier_visage_vu
            >= RESET_APRES_ABSENCE
        ):

            if echecs > 0 or alarme_declenchee:

                print(
                    "Zone vide -> remise a zero"
                )

            echecs = 0

            alarme_declenchee = False


    # =====================================================
    # AFFICHAGE
    # =====================================================

    if echecs == 0:

        statut = "SURVEILLANCE ACTIVE"

        couleur_statut = (0, 255, 0)

    elif echecs < MAX_ECHECS:

        statut = (
            f"RECONNAISSANCE ECHOUEE "
            f"{echecs}/{MAX_ECHECS}"
        )

        couleur_statut = (0, 165, 255)

    else:

        statut = "ALERTE - PERSONNE INCONNUE"

        couleur_statut = (0, 0, 255)


    cv2.putText(
        image,
        statut,
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        couleur_statut,
        2
    )


    cv2.putText(
        image,
        f"Echecs : {echecs}/{MAX_ECHECS}",
        (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )


    cv2.imshow(
        "SENTINEL-X - Reconnaissance faciale",
        image
    )


    # Q pour quitter
    touche = cv2.waitKey(1) & 0xFF

    if touche == ord("q"):
        break


# =========================================================
# FIN
# =========================================================

camera.release()

cv2.destroyAllWindows()

print()
print("SENTINEL-X Vision arrete.")