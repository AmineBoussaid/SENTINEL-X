import cv2
import os
import time
import serial
import winsound
import threading

from database import (
    initialiser_db,
    ajouter_mesure,
    ajouter_evenement
)


# ==========================================================
# DOSSIERS
# ==========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


# ==========================================================
# CONFIGURATION ESP8266
# ==========================================================

PORT = "COM8"
VITESSE = 115200


# ==========================================================
# CONFIGURATION RECONNAISSANCE FACIALE
# ==========================================================

DOSSIER_VISAGES = os.path.join(
    BASE_DIR,
    "visages_connus"
)

MODELE_YUNET = os.path.join(
    BASE_DIR,
    "models",
    "face_detection_yunet_2023mar.onnx"
)

MODELE_SFACE = os.path.join(
    BASE_DIR,
    "models",
    "face_recognition_sface_2021dec.onnx"
)

SEUIL_RECONNAISSANCE = 0.30

MAX_ECHECS = 3

DELAI_RECONNAISSANCE = 1.5


# ==========================================================
# SEUILS CAPTEURS
# ==========================================================

SEUIL_TEMPERATURE = 40.0

SEUIL_HUMIDITE = 70.0


# ==========================================================
# BASE DE DONNEES
# ==========================================================

# Enregistre température/humidité toutes les 10 secondes
INTERVALLE_MESURES = 10


# ==========================================================
# DELAIS ENTRE ALERTES
# ==========================================================

DELAI_ALERTE_TEMPERATURE = 30

DELAI_ALERTE_HUMIDITE = 30

DELAI_ALERTE_MOUVEMENT = 5


# ==========================================================
# ETAT GLOBAL SENTINEL-X
# ==========================================================

etat = {

    "temperature": None,

    "humidite": None,

    "mouvement_actif": False,

    "mouvement_detecte": False,

    "personne": "En attente",

    "autorisee": None,

    "score": None,

    "alarme": False,

    # Permet de couper uniquement le son
    "alarme_active": True,

    "systeme": "DEMARRAGE",

    "phase": "DEMARRAGE",

    "dernier_evenement":
        "Initialisation SENTINEL-X"
}


verrou_etat = threading.Lock()


# ==========================================================
# MODIFICATION ETAT
# ==========================================================

def modifier_etat(**kwargs):

    with verrou_etat:

        for cle, valeur in kwargs.items():

            etat[cle] = valeur


# ==========================================================
# LECTURE ETAT
# ==========================================================

def obtenir_etat():

    with verrou_etat:

        return etat.copy()


# ==========================================================
# SIRENE
# ==========================================================

verrou_alarme = threading.Lock()


def jouer_alarme(force=False):

    # Vérifie si la sirène est activée
    with verrou_etat:

        active = etat[
            "alarme_active"
        ]


    # Si OFF depuis le dashboard,
    # l'événement reste enregistré
    # mais aucun son n'est joué.
    if not active and not force:

        print(
            "Sirene desactivee."
        )

        return


    # Empêche deux alarmes de jouer
    # exactement en même temps.
    if verrou_alarme.locked():

        return


    def sirene():

        with verrou_alarme:

            modifier_etat(
                alarme=True
            )

            print()
            print(
                "================================"
            )
            print(
                "   ALARME SENTINEL-X"
            )
            print(
                "================================"
            )
            print()


            # Sirène montante / descendante
            for _ in range(4):

                for frequence in range(
                    700,
                    1900,
                    150
                ):

                    winsound.Beep(
                        frequence,
                        70
                    )


                for frequence in range(
                    1900,
                    700,
                    -150
                ):

                    winsound.Beep(
                        frequence,
                        70
                    )


            modifier_etat(
                alarme=False
            )


    threading.Thread(
        target=sirene,
        daemon=True
    ).start()


# ==========================================================
# ACTIVER / DESACTIVER SIRENE
# ==========================================================

def regler_alarme(active):

    active = bool(active)


    modifier_etat(

        alarme_active=active,

        dernier_evenement=(

            "Sirene activee manuellement"

            if active

            else

            "Sirene desactivee manuellement"
        )
    )


    ajouter_evenement(

        "CONTROLE",

        "INFO",

        (
            "ALARME_ACTIVE"

            if active

            else

            "ALARME_DESACTIVEE"
        ),

        "Modification depuis le dashboard"
    )


    print()

    if active:

        print(
            "Sirene SENTINEL-X : ACTIVE"
        )

    else:

        print(
            "Sirene SENTINEL-X : DESACTIVEE"
        )

    print()


    return active


# ==========================================================
# TEST MANUEL SIRENE
# ==========================================================

def tester_alarme():

    ajouter_evenement(

        "CONTROLE",

        "INFO",

        "TEST_ALARME",

        "Test manuel de la sirene"
    )


    modifier_etat(
        dernier_evenement=
            "Test manuel de la sirene"
    )


    jouer_alarme(
        force=True
    )


# ==========================================================
# CHARGEMENT YUNET + SFACE
# ==========================================================

def charger_reconnaissance():

    if not os.path.isfile(
        MODELE_YUNET
    ):

        raise FileNotFoundError(
            "Modele YuNet introuvable : "
            + MODELE_YUNET
        )


    if not os.path.isfile(
        MODELE_SFACE
    ):

        raise FileNotFoundError(
            "Modele SFace introuvable : "
            + MODELE_SFACE
        )


    detecteur = (
        cv2.FaceDetectorYN_create(

            MODELE_YUNET,

            "",

            (320, 320),

            0.9,

            0.3,

            5000
        )
    )


    reconnaisseur = (
        cv2.FaceRecognizerSF_create(

            MODELE_SFACE,

            ""
        )
    )


    return (
        detecteur,
        reconnaisseur
    )


# ==========================================================
# DETECTION DES VISAGES
# ==========================================================

def detecter_visages(
    image,
    detecteur
):

    hauteur, largeur = (
        image.shape[:2]
    )


    detecteur.setInputSize(
        (
            largeur,
            hauteur
        )
    )


    resultat = detecteur.detect(
        image
    )


    if resultat[1] is None:

        return []


    return resultat[1]


# ==========================================================
# CREATION EMPREINTE SFACE
# ==========================================================

def creer_empreinte(
    image,
    visage,
    reconnaisseur
):

    try:

        visage_aligne = (
            reconnaisseur.alignCrop(

                image,

                visage
            )
        )


        empreinte = (
            reconnaisseur.feature(
                visage_aligne
            )
        )


        return empreinte


    except cv2.error:

        return None


# ==========================================================
# CHARGEMENT PERSONNES AUTORISEES
# ==========================================================

def charger_personnes(
    detecteur,
    reconnaisseur
):

    base = {}


    extensions = (

        ".jpg",

        ".jpeg",

        ".png",

        ".bmp"
    )


    if not os.path.isdir(
        DOSSIER_VISAGES
    ):

        print(
            "Dossier visages_connus introuvable."
        )

        return base


    print()
    print(
        "================================"
    )
    print(
        " PERSONNES AUTORISEES"
    )
    print(
        "================================"
    )
    print()


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


        for fichier in sorted(
            os.listdir(
                dossier
            )
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
                image,
                detecteur
            )


            if len(visages) == 0:

                continue


            # Prend le plus grand visage
            visage = max(

                visages,

                key=lambda v:
                    float(v[2])
                    * float(v[3])
            )


            empreinte = creer_empreinte(

                image,

                visage,

                reconnaisseur
            )


            if empreinte is not None:

                empreintes.append(
                    empreinte
                )


        if empreintes:

            base[nom] = (
                empreintes
            )


            print(
                f"-> {nom} : "
                f"{len(empreintes)} photo(s)"
            )


    print()


    return base


# ==========================================================
# COMPARAISON FACIALE
# ==========================================================

def reconnaitre(
    empreinte_test,
    base,
    reconnaisseur
):

    meilleur_nom = None

    meilleur_score = -1.0


    for nom, empreintes in (
        base.items()
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


    reconnu = (
        meilleur_score
        >= SEUIL_RECONNAISSANCE
    )


    return (

        reconnu,

        meilleur_nom,

        meilleur_score
    )


# ==========================================================
# PHASE 1 : IDENTIFICATION FACIALE
# ==========================================================

def identification():

    modifier_etat(

        phase="RECONNAISSANCE",

        systeme="IDENTIFICATION",

        personne="Recherche...",

        autorisee=None,

        score=None,

        dernier_evenement=
            "Reconnaissance faciale en cours"
    )


    ajouter_evenement(

        "RECONNAISSANCE",

        "INFO",

        "DEMARRAGE",

        "Demarrage de la reconnaissance faciale"
    )


    # ======================================================
    # CHARGEMENT IA
    # ======================================================

    try:

        detecteur, reconnaisseur = (
            charger_reconnaissance()
        )


    except Exception as erreur:

        print(
            "Erreur reconnaissance :",
            erreur
        )


        ajouter_evenement(

            "ERREUR",

            "CRITIQUE",

            "RECONNAISSANCE",

            str(erreur)
        )


        modifier_etat(

            systeme="ERREUR IA",

            dernier_evenement=
                "Erreur reconnaissance faciale"
        )


        return False


    # ======================================================
    # CHARGEMENT BASE VISAGES
    # ======================================================

    base = charger_personnes(

        detecteur,

        reconnaisseur
    )


    if not base:

        print(
            "Aucune personne autorisee chargee."
        )


        ajouter_evenement(

            "ERREUR",

            "CRITIQUE",

            "VISAGES",

            "Aucune personne autorisee chargee"
        )


        return False


    # ======================================================
    # CAMERA
    # ======================================================

    camera = cv2.VideoCapture(
        0,
        cv2.CAP_DSHOW
    )


    if not camera.isOpened():

        camera = cv2.VideoCapture(
            0
        )


    if not camera.isOpened():

        print(
            "Impossible d'ouvrir la webcam."
        )


        ajouter_evenement(

            "ERREUR",

            "CRITIQUE",

            "CAMERA",

            "Impossible d'ouvrir la webcam"
        )


        return False


    camera.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280
    )

    camera.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720
    )


    echecs = 0

    dernier_essai = 0


    print()
    print(
        "Reconnaissance faciale active..."
    )
    print()


    # ======================================================
    # BOUCLE CAMERA
    # ======================================================

    while True:

        ok, frame = camera.read()


        if not ok:

            continue


        visages = detecter_visages(

            frame,

            detecteur
        )


        maintenant_timestamp = (
            time.time()
        )


        for visage in visages:

            empreinte = creer_empreinte(

                frame,

                visage,

                reconnaisseur
            )


            if empreinte is None:

                continue


            reconnu, nom, score = (
                reconnaitre(

                    empreinte,

                    base,

                    reconnaisseur
                )
            )


            score_arrondi = round(
                float(score),
                3
            )


            modifier_etat(
                score=score_arrondi
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


            # ==================================================
            # PERSONNE AUTORISEE
            # ==================================================

            if reconnu:

                modifier_etat(

                    personne=nom,

                    autorisee=True,

                    dernier_evenement=
                        f"{nom} reconnu(e)"
                )


                ajouter_evenement(

                    "RECONNAISSANCE",

                    "INFO",

                    nom,

                    (
                        "Personne autorisee - "
                        f"score {score_arrondi}"
                    )
                )


                print()
                print(
                    "================================"
                )
                print(
                    f" PERSONNE AUTORISEE : {nom}"
                )
                print(
                    f" SCORE : {score_arrondi}"
                )
                print(
                    "================================"
                )
                print()


                cv2.rectangle(

                    frame,

                    (x, y),

                    (x + w, y + h),

                    (0, 255, 0),

                    3
                )


                cv2.putText(

                    frame,

                    f"{nom} | {score:.3f}",

                    (
                        x,
                        max(
                            y - 10,
                            30
                        )
                    ),

                    cv2.FONT_HERSHEY_SIMPLEX,

                    0.8,

                    (0, 255, 0),

                    2
                )


                cv2.imshow(
                    "SENTINEL-X",
                    frame
                )


                cv2.waitKey(
                    1000
                )


                camera.release()

                cv2.destroyAllWindows()


                return True


            # ==================================================
            # PERSONNE INCONNUE
            # ==================================================

            else:

                modifier_etat(

                    personne="INCONNU",

                    autorisee=False
                )


                cv2.rectangle(

                    frame,

                    (x, y),

                    (x + w, y + h),

                    (0, 0, 255),

                    3
                )


                cv2.putText(

                    frame,

                    f"INCONNU | {score:.3f}",

                    (
                        x,
                        max(
                            y - 10,
                            30
                        )
                    ),

                    cv2.FONT_HERSHEY_SIMPLEX,

                    0.8,

                    (0, 0, 255),

                    2
                )


                if (

                    maintenant_timestamp

                    - dernier_essai

                    >= DELAI_RECONNAISSANCE

                ):

                    dernier_essai = (
                        maintenant_timestamp
                    )


                    echecs += 1


                    print(
                        f"Echec reconnaissance "
                        f"{echecs}/{MAX_ECHECS}"
                    )


                    modifier_etat(

                        dernier_evenement=
                            f"Echec reconnaissance "
                            f"{echecs}/{MAX_ECHECS}"
                    )


                    ajouter_evenement(

                        "RECONNAISSANCE",

                        "ATTENTION",

                        "INCONNU",

                        (
                            f"Echec "
                            f"{echecs}/{MAX_ECHECS} "
                            f"- score {score_arrondi}"
                        )
                    )


                    # ==========================================
                    # 3 ECHECS
                    # ==========================================

                    if (
                        echecs
                        >= MAX_ECHECS
                    ):

                        print()
                        print(
                            "================================"
                        )
                        print(
                            " PERSONNE NON AUTORISEE"
                        )
                        print(
                            "================================"
                        )
                        print()


                        ajouter_evenement(

                            "ALERTE_RECONNAISSANCE",

                            "CRITIQUE",

                            "INCONNU",

                            (
                                "Personne non autorisee "
                                "apres 3 echecs"
                            )
                        )


                        modifier_etat(

                            personne="INCONNU",

                            autorisee=False,

                            dernier_evenement=
                                "Personne non autorisee"
                        )


                        camera.release()

                        cv2.destroyAllWindows()


                        jouer_alarme()


                        return False


        # ======================================================
        # AFFICHAGE COMPTEUR
        # ======================================================

        cv2.putText(

            frame,

            f"Echecs : "
            f"{echecs}/{MAX_ECHECS}",

            (20, 40),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.9,

            (255, 255, 255),

            2
        )


        cv2.imshow(
            "SENTINEL-X - Identification",
            frame
        )


        # Q = quitter
        if (
            cv2.waitKey(1) & 0xFF
            == ord("q")
        ):

            camera.release()

            cv2.destroyAllWindows()


            ajouter_evenement(

                "RECONNAISSANCE",

                "INFO",

                "ANNULEE",

                (
                    "Identification fermee "
                    "par utilisateur"
                )
            )


            return False


# ==========================================================
# PHASE 2 : SURVEILLANCE CAPTEURS
# ==========================================================

def surveiller_capteurs(
    esp
):

    dernier_mouvement = 0

    derniere_alerte_temperature = 0

    derniere_alerte_humidite = 0

    dernier_enregistrement_mesures = 0


    temperature_actuelle = None

    humidite_actuelle = None


    modifier_etat(

        phase="SURVEILLANCE",

        systeme="ACTIF"
    )


    ajouter_evenement(

        "SYSTEME",

        "INFO",

        "SURVEILLANCE",

        "Surveillance capteurs active"
    )


    print()
    print(
        "================================"
    )
    print(
        " SURVEILLANCE CAPTEURS ACTIVE"
    )
    print(
        "================================"
    )
    print()


    while True:

        try:

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


            maintenant_timestamp = (
                time.time()
            )


            # ==================================================
            # TEMPERATURE
            # ==================================================

            if (
                "Temperature :"
                in ligne
            ):

                try:

                    valeur = float(

                        ligne
                        .split(":")[1]
                        .replace(
                            "C",
                            ""
                        )
                        .strip()
                    )


                    temperature_actuelle = (
                        valeur
                    )


                    modifier_etat(
                        temperature=valeur
                    )


                    # ==========================================
                    # ALERTE TEMPERATURE
                    # ==========================================

                    if (
                        valeur
                        > SEUIL_TEMPERATURE
                    ):

                        if (

                            maintenant_timestamp

                            - derniere_alerte_temperature

                            >= DELAI_ALERTE_TEMPERATURE

                        ):

                            derniere_alerte_temperature = (
                                maintenant_timestamp
                            )


                            ajouter_evenement(

                                "ALERTE_TEMPERATURE",

                                "CRITIQUE",

                                f"{valeur} C",

                                (
                                    "Temperature "
                                    "superieure au seuil"
                                )
                            )


                            modifier_etat(

                                dernier_evenement=
                                    (
                                        "Temperature elevee : "
                                        f"{valeur} C"
                                    )
                            )


                            jouer_alarme()


                except ValueError:

                    pass


            # ==================================================
            # HUMIDITE
            # ==================================================

            elif (
                "Humidite :"
                in ligne
            ):

                try:

                    valeur = float(

                        ligne
                        .split(":")[1]
                        .replace(
                            "%",
                            ""
                        )
                        .strip()
                    )


                    humidite_actuelle = (
                        valeur
                    )


                    modifier_etat(
                        humidite=valeur
                    )


                    # ==========================================
                    # ALERTE HUMIDITE
                    # ==========================================

                    if (
                        valeur
                        > SEUIL_HUMIDITE
                    ):

                        if (

                            maintenant_timestamp

                            - derniere_alerte_humidite

                            >= DELAI_ALERTE_HUMIDITE

                        ):

                            derniere_alerte_humidite = (
                                maintenant_timestamp
                            )


                            ajouter_evenement(

                                "ALERTE_HUMIDITE",

                                "CRITIQUE",

                                f"{valeur} %",

                                (
                                    "Humidite "
                                    "superieure au seuil"
                                )
                            )


                            modifier_etat(

                                dernier_evenement=
                                    (
                                        "Humidite elevee : "
                                        f"{valeur} %"
                                    )
                            )


                            jouer_alarme()


                except ValueError:

                    pass


            # ==================================================
            # MODE MOUVEMENT ACTIVE
            # ==================================================

            elif (
                "MODE_MOUVEMENT : ACTIF"
                in ligne
            ):

                modifier_etat(

                    mouvement_actif=True,

                    mouvement_detecte=False,

                    dernier_evenement=
                        "Detection mouvement active"
                )


            # ==================================================
            # MODE MOUVEMENT DESACTIVE
            # ==================================================

            elif (
                "MODE_MOUVEMENT : DESACTIVE"
                in ligne
            ):

                modifier_etat(

                    mouvement_actif=False,

                    mouvement_detecte=False,

                    dernier_evenement=
                        "Detection mouvement desactivee"
                )


            # ==================================================
            # MOUVEMENT DETECTE
            # ==================================================

            elif (
                "ALERTE_MOUVEMENT"
                in ligne
            ):

                modifier_etat(

                    mouvement_detecte=True,

                    dernier_evenement=
                        "Mouvement detecte"
                )


                if (

                    maintenant_timestamp

                    - dernier_mouvement

                    >= DELAI_ALERTE_MOUVEMENT

                ):

                    dernier_mouvement = (
                        maintenant_timestamp
                    )


                    ajouter_evenement(

                        "MOUVEMENT",

                        "ALERTE",

                        "DETECTE",

                        (
                            "Mouvement detecte "
                            "par HC-SR04"
                        )
                    )


                    jouer_alarme()


            # ==================================================
            # PAS DE MOUVEMENT
            # ==================================================

            elif (
                "Mouvement : NON"
                in ligne
            ):

                modifier_etat(
                    mouvement_detecte=False
                )


            # ==================================================
            # ENREGISTREMENT SQL
            # ==================================================

            if (

                temperature_actuelle
                is not None

                and

                humidite_actuelle
                is not None

            ):

                if (

                    maintenant_timestamp

                    - dernier_enregistrement_mesures

                    >= INTERVALLE_MESURES

                ):

                    ajouter_mesure(

                        temperature_actuelle,

                        humidite_actuelle
                    )


                    dernier_enregistrement_mesures = (
                        maintenant_timestamp
                    )


        except serial.SerialException as erreur:

            print(
                "Erreur port serie :",
                erreur
            )


            modifier_etat(

                systeme="ERREUR ESP",

                dernier_evenement=
                    "Connexion ESP8266 perdue"
            )


            ajouter_evenement(

                "ERREUR",

                "CRITIQUE",

                "ESP8266",

                str(erreur)
            )


            break


        except Exception as erreur:

            print(
                "Erreur surveillance :",
                erreur
            )


            modifier_etat(

                systeme="ERREUR",

                dernier_evenement=
                    "Erreur surveillance capteurs"
            )


            ajouter_evenement(

                "ERREUR",

                "CRITIQUE",

                "CAPTEURS",

                str(erreur)
            )


            time.sleep(
                1
            )


# ==========================================================
# MOTEUR PRINCIPAL SENTINEL-X
# ==========================================================

def moteur_sentinel():

    # ======================================================
    # BASE SQL
    # ======================================================

    initialiser_db()


    ajouter_evenement(

        "SYSTEME",

        "INFO",

        "DEMARRAGE",

        "SENTINEL-X demarre"
    )


    print()
    print(
        "================================"
    )
    print(
        "       SENTINEL-X ENGINE"
    )
    print(
        "================================"
    )
    print()


    modifier_etat(

        systeme="CONNEXION ESP",

        dernier_evenement=
            "Connexion ESP8266"
    )


    # ======================================================
    # CONNEXION ESP8266
    # ======================================================

    try:

        esp = serial.Serial(

            PORT,

            VITESSE,

            timeout=1
        )


    except serial.SerialException as erreur:

        print()
        print(
            "Impossible de connecter ESP8266 :"
        )
        print(
            erreur
        )
        print()


        modifier_etat(

            systeme="ERREUR ESP",

            dernier_evenement=
                "ESP8266 non connecte"
        )


        ajouter_evenement(

            "ERREUR",

            "CRITIQUE",

            "ESP8266",

            str(erreur)
        )


        return


    # Attend redémarrage ESP
    time.sleep(
        2
    )


    esp.reset_input_buffer()


    modifier_etat(
        systeme="CONNECTE"
    )


    ajouter_evenement(

        "ESP8266",

        "INFO",

        "CONNECTE",

        f"Connexion serie {PORT}"
    )


    print(
        f"ESP8266 connecte sur {PORT}"
    )


    # ======================================================
    # 1 - RECONNAISSANCE FACIALE
    # ======================================================

    personne_autorisee = (
        identification()
    )


    # ======================================================
    # 2 - DECISION MOUVEMENT
    # ======================================================

    if personne_autorisee:

        print()
        print(
            "Personne autorisee"
        )
        print(
            "Detection mouvement : OFF"
        )
        print()


        esp.write(
            b"DESACTIVER_MOUVEMENT\n"
        )


        modifier_etat(

            mouvement_actif=False,

            mouvement_detecte=False,

            dernier_evenement=
                "Mouvement desactive"
        )


        ajouter_evenement(

            "MOUVEMENT",

            "INFO",

            "DESACTIVE",

            "Personne autorisee reconnue"
        )


    else:

        print()
        print(
            "Personne non autorisee"
        )
        print(
            "Detection mouvement : ACTIVE"
        )
        print()


        esp.write(
            b"ACTIVER_MOUVEMENT\n"
        )


        modifier_etat(

            mouvement_actif=True,

            mouvement_detecte=False,

            dernier_evenement=
                "Surveillance mouvement active"
        )


        ajouter_evenement(

            "MOUVEMENT",

            "ATTENTION",

            "ACTIF",

            "Personne non autorisee"
        )


    time.sleep(
        1
    )


    # Enlève les anciennes lignes accumulées
    # pendant la reconnaissance.
    esp.reset_input_buffer()


    # ======================================================
    # 3 - SURVEILLANCE PERMANENTE
    # ======================================================

    surveiller_capteurs(
        esp
    )


# ==========================================================
# DEMARRAGE EN THREAD
# ==========================================================

def demarrer_sentinel():

    thread = threading.Thread(

        target=moteur_sentinel,

        daemon=True,

        name="SentinelEngine"
    )


    thread.start()


    return thread