import os
import sqlite3

from datetime import (
    datetime,
    timedelta
)


# ==========================================================
# DATABASE
# ==========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DB_PATH = os.path.join(
    BASE_DIR,
    "sentinel.db"
)


# ==========================================================
# CONNEXION
# ==========================================================

def connexion():

    conn = sqlite3.connect(
        DB_PATH,
        timeout=10
    )

    conn.row_factory = sqlite3.Row

    return conn


# ==========================================================
# DATE
# ==========================================================

def maintenant():

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ==========================================================
# INITIALISATION
# ==========================================================

def initialiser_db():

    with connexion() as conn:

        # ==============================================
        # MESURES
        # ==============================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mesures (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                date_heure TEXT NOT NULL,

                temperature REAL,

                humidite REAL
            )
            """
        )


        # ==============================================
        # EVENEMENTS SENTINEL
        # ==============================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evenements (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                date_heure TEXT NOT NULL,

                type TEXT NOT NULL,

                niveau TEXT NOT NULL,

                valeur TEXT,

                details TEXT
            )
            """
        )


        # ==============================================
        # ADMIN
        # ==============================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                username TEXT NOT NULL UNIQUE,

                password_hash TEXT NOT NULL,

                role TEXT NOT NULL DEFAULT 'ADMIN',

                is_active INTEGER NOT NULL DEFAULT 1,

                failed_attempts INTEGER NOT NULL DEFAULT 0,

                locked_until TEXT,

                last_login TEXT,

                created_at TEXT NOT NULL
            )
            """
        )


        # Migration douce pour les bases déjà créées.
        colonnes_users = {
            ligne["name"]
            for ligne in conn.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }


        nouvelles_colonnes = {
            "first_name": "TEXT",
            "last_name": "TEXT",
            "face_folder": "TEXT"
        }


        for nom_colonne, definition in (
            nouvelles_colonnes.items()
        ):

            if nom_colonne not in colonnes_users:

                conn.execute(
                    f"ALTER TABLE users "
                    f"ADD COLUMN {nom_colonne} "
                    f"{definition}"
                )


        # ==============================================
        # AUDIT CYBERSECURITE
        # ==============================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS security_audit (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                date_heure TEXT NOT NULL,

                utilisateur TEXT,

                action TEXT NOT NULL,

                statut TEXT NOT NULL,

                adresse_ip TEXT,

                details TEXT
            )
            """
        )


        # ==============================================
        # INDEX
        # ==============================================

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_mesures_date
            ON mesures(date_heure)
            """
        )


        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_evenements_date
            ON evenements(date_heure)
            """
        )


        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_audit_date
            ON security_audit(date_heure)
            """
        )


        conn.commit()


# ==========================================================
# MESURES
# ==========================================================

def ajouter_mesure(
    temperature,
    humidite
):

    with connexion() as conn:

        conn.execute(
            """
            INSERT INTO mesures (
                date_heure,
                temperature,
                humidite
            )

            VALUES (?, ?, ?)
            """,
            (
                maintenant(),
                temperature,
                humidite
            )
        )

        conn.commit()


def lire_mesures(
    limite=200
):

    with connexion() as conn:

        lignes = conn.execute(
            """
            SELECT *

            FROM mesures

            ORDER BY id DESC

            LIMIT ?
            """,
            (
                limite,
            )
        ).fetchall()


    return [
        dict(ligne)
        for ligne in lignes
    ]


def lire_mesures_depuis(
    heures=24
):

    date_minimum = (
        datetime.now()
        - timedelta(
            hours=heures
        )
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    with connexion() as conn:

        lignes = conn.execute(
            """
            SELECT *

            FROM mesures

            WHERE date_heure >= ?

            ORDER BY id ASC
            """,
            (
                date_minimum,
            )
        ).fetchall()


    return [
        dict(ligne)
        for ligne in lignes
    ]


# ==========================================================
# EVENEMENTS
# ==========================================================

def ajouter_evenement(
    type_evenement,
    niveau="INFO",
    valeur=None,
    details=None
):

    with connexion() as conn:

        conn.execute(
            """
            INSERT INTO evenements (
                date_heure,
                type,
                niveau,
                valeur,
                details
            )

            VALUES (?, ?, ?, ?, ?)
            """,
            (
                maintenant(),
                type_evenement,
                niveau,
                valeur,
                details
            )
        )

        conn.commit()


def lire_evenements(
    limite=200
):

    with connexion() as conn:

        lignes = conn.execute(
            """
            SELECT *

            FROM evenements

            ORDER BY id DESC

            LIMIT ?
            """,
            (
                limite,
            )
        ).fetchall()


    return [
        dict(ligne)
        for ligne in lignes
    ]


def lire_evenements_depuis(
    heures=24
):

    date_minimum = (
        datetime.now()
        - timedelta(
            hours=heures
        )
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    with connexion() as conn:

        lignes = conn.execute(
            """
            SELECT *

            FROM evenements

            WHERE date_heure >= ?

            ORDER BY id ASC
            """,
            (
                date_minimum,
            )
        ).fetchall()


    return [
        dict(ligne)
        for ligne in lignes
    ]


# ==========================================================
# GESTION DES UTILISATEURS
# ==========================================================

def creer_utilisateur(
    first_name,
    last_name,
    username,
    password_hash,
    role,
    face_folder
):

    role = role.upper()


    if role not in (
        "ADMIN",
        "USER"
    ):

        raise ValueError(
            "Role utilisateur invalide"
        )


    with connexion() as conn:

        curseur = conn.execute(
            """
            INSERT INTO users (
                first_name,
                last_name,
                username,
                password_hash,
                role,
                face_folder,
                is_active,
                failed_attempts,
                created_at
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                first_name,
                last_name,
                username,
                password_hash,
                role,
                face_folder,
                1,
                0,
                maintenant()
            )
        )


        conn.commit()


        return curseur.lastrowid


def lire_utilisateurs():

    with connexion() as conn:

        lignes = conn.execute(
            """
            SELECT
                id,
                first_name,
                last_name,
                username,
                role,
                face_folder,
                is_active,
                failed_attempts,
                locked_until,
                last_login,
                created_at

            FROM users

            ORDER BY id DESC
            """
        ).fetchall()


    return [
        dict(ligne)
        for ligne in lignes
    ]


# ==========================================================
# ADMIN HISTORIQUE
# ==========================================================

def creer_admin(
    username,
    password_hash
):

    initialiser_db()


    with connexion() as conn:

        utilisateur = conn.execute(
            """
            SELECT id

            FROM users

            WHERE username = ?
            """,
            (
                username,
            )
        ).fetchone()


        if utilisateur:

            conn.execute(
                """
                UPDATE users

                SET
                    password_hash = ?,
                    role = 'ADMIN',
                    is_active = 1,
                    failed_attempts = 0,
                    locked_until = NULL

                WHERE username = ?
                """,
                (
                    password_hash,
                    username
                )
            )

        else:

            conn.execute(
                """
                INSERT INTO users (

                    username,
                    password_hash,
                    role,
                    is_active,
                    failed_attempts,
                    created_at

                )

                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    password_hash,
                    "ADMIN",
                    1,
                    0,
                    maintenant()
                )
            )


        conn.commit()


# ==========================================================
# RECHERCHE ADMIN
# ==========================================================

def utilisateur_par_username(
    username
):

    with connexion() as conn:

        ligne = conn.execute(
            """
            SELECT *

            FROM users

            WHERE username = ?
            """,
            (
                username,
            )
        ).fetchone()


    if ligne is None:

        return None


    return dict(
        ligne
    )


def utilisateur_par_id(
    user_id
):

    with connexion() as conn:

        ligne = conn.execute(
            """
            SELECT *

            FROM users

            WHERE id = ?
            """,
            (
                user_id,
            )
        ).fetchone()


    if ligne is None:

        return None


    return dict(
        ligne
    )


# ==========================================================
# VERROUILLAGE
# ==========================================================

def utilisateur_verrouille(
    utilisateur
):

    locked_until = utilisateur.get(
        "locked_until"
    )


    if not locked_until:

        return False


    try:

        date_verrouillage = (
            datetime.strptime(
                locked_until,
                "%Y-%m-%d %H:%M:%S"
            )
        )

    except ValueError:

        return False


    return (
        datetime.now()
        < date_verrouillage
    )


# ==========================================================
# ECHEC LOGIN
# ==========================================================

def enregistrer_echec_connexion(
    user_id
):

    with connexion() as conn:

        utilisateur = conn.execute(
            """
            SELECT failed_attempts

            FROM users

            WHERE id = ?
            """,
            (
                user_id,
            )
        ).fetchone()


        if utilisateur is None:

            return 0, None


        tentatives = (
            utilisateur[
                "failed_attempts"
            ]
            + 1
        )


        locked_until = None


        # 5 erreurs = verrouillage 5 minutes
        if tentatives >= 5:

            locked_until = (
                datetime.now()
                + timedelta(
                    minutes=5
                )
            ).strftime(
                "%Y-%m-%d %H:%M:%S"
            )


        conn.execute(
            """
            UPDATE users

            SET
                failed_attempts = ?,
                locked_until = ?

            WHERE id = ?
            """,
            (
                tentatives,
                locked_until,
                user_id
            )
        )


        conn.commit()


    return (
        tentatives,
        locked_until
    )


# ==========================================================
# SUCCES LOGIN
# ==========================================================

def enregistrer_succes_connexion(
    user_id
):

    with connexion() as conn:

        conn.execute(
            """
            UPDATE users

            SET
                failed_attempts = 0,
                locked_until = NULL,
                last_login = ?

            WHERE id = ?
            """,
            (
                maintenant(),
                user_id
            )
        )


        conn.commit()


# ==========================================================
# AUDIT SECURITE
# ==========================================================

def ajouter_audit(
    utilisateur,
    action,
    statut,
    adresse_ip=None,
    details=None
):

    with connexion() as conn:

        conn.execute(
            """
            INSERT INTO security_audit (

                date_heure,
                utilisateur,
                action,
                statut,
                adresse_ip,
                details

            )

            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                maintenant(),
                utilisateur,
                action,
                statut,
                adresse_ip,
                details
            )
        )


        conn.commit()


def lire_audits(
    limite=200
):

    with connexion() as conn:

        lignes = conn.execute(
            """
            SELECT *

            FROM security_audit

            ORDER BY id DESC

            LIMIT ?
            """,
            (
                limite,
            )
        ).fetchall()


    return [
        dict(ligne)
        for ligne in lignes
    ]


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    initialiser_db()

    print(
        "Base SENTINEL-X initialisee."
    )
