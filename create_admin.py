from getpass import getpass

from werkzeug.security import (
    generate_password_hash
)

from database import (
    initialiser_db,
    creer_admin
)


print()
print(
    "================================"
)
print(
    "    SENTINEL-X ADMIN SETUP"
)
print(
    "================================"
)
print()


initialiser_db()


username = input(
    "Nom administrateur [admin] : "
).strip()


if not username:

    username = "admin"


while True:

    password = getpass(
        "Mot de passe : "
    )


    if len(password) < 10:

        print(
            "Le mot de passe doit contenir "
            "au moins 10 caracteres."
        )

        continue


    confirmation = getpass(
        "Confirmer le mot de passe : "
    )


    if password != confirmation:

        print(
            "Les mots de passe ne correspondent pas."
        )

        continue


    break


password_hash = (
    generate_password_hash(
        password,
        method="scrypt"
    )
)


creer_admin(
    username,
    password_hash
)


print()
print(
    "================================"
)
print(
    " ADMIN SENTINEL-X CREE"
)
print(
    "================================"
)
print()

print(
    "Utilisateur :",
    username
)

print()