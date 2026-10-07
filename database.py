import os
import sqlite3
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "sentinel.db")


def connexion():

    conn = sqlite3.connect(
        DB_PATH,
        timeout=10
    )

    conn.row_factory = sqlite3.Row

    return conn


def maintenant():

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def initialiser_db():

    with connexion() as conn:

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

        conn.commit()


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


from datetime import timedelta


def lire_mesures_depuis(heures=24):

    date_minimum = (
        datetime.now()
        - timedelta(hours=heures)
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


def lire_evenements_depuis(heures=24):

    date_minimum = (
        datetime.now()
        - timedelta(hours=heures)
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


if __name__ == "__main__":

    initialiser_db()

    print()
    print(
        "Base de donnees SENTINEL-X creee :"
    )

    print(
        DB_PATH
    )