import os
import math
import statistics
import sqlite3
import time

from datetime import (
    datetime,
    timedelta
)

from functools import wraps


from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    redirect,
    url_for,
    flash,
    session
)


from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)


from flask_wtf import (
    FlaskForm,
    CSRFProtect
)


from flask_limiter import (
    Limiter
)


from flask_limiter.util import (
    get_remote_address
)


from wtforms import (
    StringField,
    PasswordField,
    SelectField,
    MultipleFileField,
    SubmitField
)


from wtforms.validators import (
    DataRequired,
    Length,
    Regexp
)


from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)


from dotenv import (
    load_dotenv
)


from sentinel_engine import (
    obtenir_etat,
    demarrer_sentinel,
    regler_alarme,
    tester_alarme
)


from database import (
    initialiser_db,
    lire_evenements,
    lire_mesures,
    lire_mesures_depuis,
    lire_evenements_depuis,
    utilisateur_par_username,
    utilisateur_par_id,
    utilisateur_verrouille,
    enregistrer_echec_connexion,
    enregistrer_succes_connexion,
    ajouter_audit,
    lire_audits,
    creer_utilisateur,
    lire_utilisateurs
)


from face_auth import (
    FaceAuthError,
    profile_exists,
    remove_profile_folder,
    save_profile_images,
    verify_face
)


# ==========================================================
# ENVIRONNEMENT
# ==========================================================

load_dotenv()


SECRET_KEY = os.getenv(
    "SECRET_KEY"
)


if not SECRET_KEY:

    raise RuntimeError(
        "SECRET_KEY absente du fichier .env"
    )


# ==========================================================
# FLASK
# ==========================================================

app = Flask(
    __name__
)


app.config.update(

    SECRET_KEY=SECRET_KEY,

    SESSION_COOKIE_HTTPONLY=True,

    SESSION_COOKIE_SAMESITE="Lax",

    SESSION_COOKIE_SECURE=(
        os.getenv(
            "SESSION_COOKIE_SECURE",
            "0"
        )
        == "1"
    ),

    PERMANENT_SESSION_LIFETIME=
        timedelta(
            minutes=30
        )
)


# ==========================================================
# CSRF
# ==========================================================

csrf = CSRFProtect(
    app
)


# ==========================================================
# RATE LIMITING
# ==========================================================

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[]
)


# ==========================================================
# LOGIN MANAGER
# ==========================================================

login_manager = LoginManager()

login_manager.init_app(
    app
)

login_manager.login_view = (
    "login"
)

login_manager.login_message = (
    "Veuillez vous connecter."
)

login_manager.login_message_category = (
    "warning"
)


# ==========================================================
# USER CLASS
# ==========================================================

class AdminUser(
    UserMixin
):

    def __init__(
        self,
        data
    ):

        self.id = str(
            data["id"]
        )

        self.username = (
            data["username"]
        )

        self.role = (
            data["role"]
        )

        self.first_name = (
            data.get("first_name")
            or ""
        )

        self.last_name = (
            data.get("last_name")
            or ""
        )

        self.active = bool(
            data["is_active"]
        )


    @property
    def is_active(
        self
    ):

        return self.active


# ==========================================================
# ADMIN REQUIRED
# ==========================================================

def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if (
            not current_user.is_authenticated
            or current_user.role != "ADMIN"
        ):

            flash(
                "Accès réservé aux administrateurs.",
                "danger"
            )

            return redirect(
                url_for("dashboard")
            )

        return view(*args, **kwargs)

    return wrapped


# ==========================================================
# LOAD USER
# ==========================================================

@login_manager.user_loader
def load_user(
    user_id
):

    utilisateur = (
        utilisateur_par_id(
            user_id
        )
    )


    if utilisateur is None:

        return None


    return AdminUser(
        utilisateur
    )


# ==========================================================
# FORM LOGIN
# ==========================================================

class LoginForm(
    FlaskForm
):

    username = StringField(
        "Utilisateur",
        validators=[
            DataRequired(),
            Length(
                min=3,
                max=50
            )
        ]
    )


    password = PasswordField(
        "Mot de passe",
        validators=[
            DataRequired(),
            Length(
                min=1,
                max=200
            )
        ]
    )


    role = SelectField(
        "Type de compte",
        choices=[
            ("ADMIN", "Administrateur"),
            ("USER", "Utilisateur")
        ],
        validators=[
            DataRequired()
        ]
    )


    submit = SubmitField(
        "SE CONNECTER"
    )


class UserCreationForm(
    FlaskForm
):

    first_name = StringField(
        "Prénom",
        validators=[
            DataRequired(),
            Length(min=2, max=80)
        ]
    )

    last_name = StringField(
        "Nom",
        validators=[
            DataRequired(),
            Length(min=2, max=80)
        ]
    )

    role = SelectField(
        "Type de compte",
        choices=[
            ("USER", "Utilisateur"),
            ("ADMIN", "Administrateur")
        ],
        validators=[
            DataRequired()
        ]
    )

    username = StringField(
        "Login",
        validators=[
            DataRequired(),
            Length(min=3, max=50),
            Regexp(
                r"^[A-Za-z0-9_.-]+$",
                message=(
                    "Le login peut contenir uniquement "
                    "des lettres, chiffres, points, "
                    "tirets et underscores."
                )
            )
        ]
    )

    password = PasswordField(
        "Mot de passe",
        validators=[
            DataRequired(),
            Length(min=10, max=200)
        ]
    )

    photos = MultipleFileField(
        "Photos du visage (optionnelles)"
    )

    submit = SubmitField(
        "CRÉER L'UTILISATEUR"
    )


# ==========================================================
# LOGIN
# ==========================================================

@app.route(
    "/login",
    methods=[
        "GET",
        "POST"
    ]
)
@limiter.limit(
    "5 per minute"
)
def login():

    if current_user.is_authenticated:

        return redirect(
            url_for(
                "dashboard"
            )
        )


    form = LoginForm()


    if form.validate_on_submit():

        username = (
            form.username.data
            .strip()
        )


        password = (
            form.password.data
        )

        selected_role = (
            form.role.data
            .upper()
        )


        ip = (
            request.remote_addr
        )


        utilisateur = (
            utilisateur_par_username(
                username
            )
        )


        # ==============================================
        # UTILISATEUR INCONNU
        # ==============================================

        if utilisateur is None:

            ajouter_audit(
                username,
                "LOGIN_FAILED",
                "ECHEC",
                ip,
                "Utilisateur inconnu"
            )


            flash(
                "Identifiants incorrects.",
                "danger"
            )


            return render_template(
                "login.html",
                form=form
            )


        # ==============================================
        # TYPE DE COMPTE
        # ==============================================

        if (
            utilisateur["role"].upper()
            != selected_role
        ):

            ajouter_audit(
                username,
                "LOGIN_FAILED",
                "ECHEC",
                ip,
                "Type de compte incorrect"
            )


            flash(
                "Identifiants incorrects.",
                "danger"
            )


            return render_template(
                "login.html",
                form=form
            )


        # ==============================================
        # COMPTE DESACTIVE
        # ==============================================

        if not utilisateur[
            "is_active"
        ]:

            ajouter_audit(
                username,
                "LOGIN_FAILED",
                "ECHEC",
                ip,
                "Compte desactive"
            )


            flash(
                "Compte desactive.",
                "danger"
            )


            return render_template(
                "login.html",
                form=form
            )


        # ==============================================
        # VERROUILLAGE
        # ==============================================

        if utilisateur_verrouille(
            utilisateur
        ):

            ajouter_audit(
                username,
                "LOGIN_BLOCKED",
                "BLOQUE",
                ip,
                (
                    "Compte temporairement "
                    "verrouille"
                )
            )


            flash(
                (
                    "Compte temporairement "
                    "verrouille. Reessayez "
                    "dans quelques minutes."
                ),
                "danger"
            )


            return render_template(
                "login.html",
                form=form
            )


        # ==============================================
        # MOT DE PASSE CORRECT
        # ==============================================

        if check_password_hash(
            utilisateur[
                "password_hash"
            ],
            password
        ):

            if profile_exists(
                utilisateur.get(
                    "face_folder"
                )
            ):

                session[
                    "pending_face_user_id"
                ] = utilisateur["id"]

                session[
                    "pending_face_started"
                ] = int(time.time())

                session[
                    "pending_face_failures"
                ] = 0

                session[
                    "pending_face_matches"
                ] = 0


                ajouter_audit(
                    username,
                    "PASSWORD_SUCCESS",
                    "EN_ATTENTE",
                    ip,
                    "Vérification faciale requise"
                )


                return redirect(
                    url_for(
                        "face_verification"
                    )
                )


            # Compatibilité : un utilisateur sans image
            # conserve le login classique.
            enregistrer_succes_connexion(
                utilisateur["id"]
            )


            login_user(
                AdminUser(utilisateur),
                remember=False
            )


            session.permanent = True


            ajouter_audit(
                username,
                "LOGIN_SUCCESS",
                "SUCCES",
                ip,
                (
                    "Connexion sans profil facial - "
                    f"rôle {utilisateur['role']}"
                )
            )


            return redirect(
                url_for("dashboard")
            )


        # ==============================================
        # MOT DE PASSE INCORRECT
        # ==============================================

        tentatives, locked_until = (
            enregistrer_echec_connexion(
                utilisateur[
                    "id"
                ]
            )
        )


        details = (
            f"Echec {tentatives}/5"
        )


        if locked_until:

            details += (
                " - verrouillage jusqu'a "
                + locked_until
            )


        ajouter_audit(
            username,
            "LOGIN_FAILED",
            "ECHEC",
            ip,
            details
        )


        if locked_until:

            flash(
                (
                    "Trop de tentatives. "
                    "Compte verrouille "
                    "pendant 5 minutes."
                ),
                "danger"
            )

        else:

            flash(
                (
                    "Identifiants incorrects. "
                    f"Tentative {tentatives}/5."
                ),
                "danger"
            )


    return render_template(
        "login.html",
        form=form
    )


# ==========================================================
# VERIFICATION FACIALE DU LOGIN
# ==========================================================

def clear_pending_face():

    for key in (
        "pending_face_user_id",
        "pending_face_started",
        "pending_face_failures",
        "pending_face_matches"
    ):
        session.pop(
            key,
            None
        )


def pending_face_user():

    user_id = session.get(
        "pending_face_user_id"
    )
    started = session.get(
        "pending_face_started"
    )

    if not user_id or not started:
        return None

    if (
        time.time()
        - float(started)
        > 120
    ):
        clear_pending_face()
        return None

    return utilisateur_par_id(
        user_id
    )


@app.route(
    "/verification-faciale"
)
def face_verification():

    if current_user.is_authenticated:
        return redirect(
            url_for("dashboard")
        )

    utilisateur = pending_face_user()

    if utilisateur is None:
        flash(
            "La vérification a expiré. Reconnectez-vous.",
            "danger"
        )
        return redirect(
            url_for("login")
        )

    if not profile_exists(
        utilisateur.get("face_folder")
    ):
        clear_pending_face()
        flash(
            "Le profil facial est indisponible.",
            "danger"
        )
        return redirect(
            url_for("login")
        )

    return render_template(
        "face_verification.html",
        utilisateur=utilisateur
    )


@app.route(
    "/api/auth/face/verify",
    methods=["POST"]
)
@limiter.limit(
    "30 per minute"
)
def face_verify_api():

    utilisateur = pending_face_user()

    if utilisateur is None:
        return jsonify({
            "success": False,
            "expired": True,
            "redirect": url_for("login"),
            "message": "Session de vérification expirée."
        }), 401

    image = request.files.get(
        "image"
    )

    if image is None:
        return jsonify({
            "success": False,
            "retry": True,
            "message": "Image absente."
        }), 400

    try:
        matched, score = verify_face(
            image.read(),
            utilisateur["face_folder"]
        )
    except FaceAuthError as error:
        return jsonify({
            "success": False,
            "retry": True,
            "message": str(error)
        })

    if matched:
        matches = (
            int(
                session.get(
                    "pending_face_matches",
                    0
                )
            )
            + 1
        )
        session[
            "pending_face_matches"
        ] = matches

        if matches < 2:
            return jsonify({
                "success": False,
                "retry": True,
                "matched": True,
                "message": (
                    "Visage reconnu. "
                    "Confirmation en cours..."
                )
            })

        enregistrer_succes_connexion(
            utilisateur["id"]
        )

        clear_pending_face()

        login_user(
            AdminUser(utilisateur),
            remember=False
        )
        session.permanent = True

        ajouter_audit(
            utilisateur["username"],
            "FACE_LOGIN_SUCCESS",
            "SUCCES",
            request.remote_addr,
            f"Visage vérifié - score {score}"
        )

        return jsonify({
            "success": True,
            "redirect": url_for("dashboard"),
            "message": "Identité confirmée."
        })

    failures = (
        int(
            session.get(
                "pending_face_failures",
                0
            )
        )
        + 1
    )
    session[
        "pending_face_failures"
    ] = failures
    session[
        "pending_face_matches"
    ] = 0

    tentatives, locked_until = (
        enregistrer_echec_connexion(
            utilisateur["id"]
        )
    )

    ajouter_audit(
        utilisateur["username"],
        "FACE_LOGIN_FAILED",
        "ECHEC",
        request.remote_addr,
        (
            f"Visage différent - score {score} - "
            f"échec {failures}/5"
        )
    )

    if failures >= 5 or locked_until:
        clear_pending_face()
        return jsonify({
            "success": False,
            "blocked": True,
            "redirect": url_for("login"),
            "message": (
                "Vérification refusée. "
                "Le compte est temporairement verrouillé."
            )
        }), 403

    return jsonify({
        "success": False,
        "retry": True,
        "message": (
            "Le visage ne correspond pas. "
            f"Tentative {failures}/5."
        )
    })


# ==========================================================
# LOGOUT
# ==========================================================

@app.route(
    "/logout",
    methods=[
        "POST"
    ]
)
@login_required
def logout():

    ajouter_audit(
        current_user.username,
        "LOGOUT",
        "SUCCES",
        request.remote_addr,
        "Deconnexion administrateur"
    )


    logout_user()


    flash(
        "Vous etes deconnecte.",
        "info"
    )


    return redirect(
        url_for(
            "login"
        )
    )


# ==========================================================
# DASHBOARD
# ==========================================================

@app.route("/")
@login_required
def dashboard():

    return render_template(
        "dashboard.html"
    )


# ==========================================================
# ARCHITECTURE
# ==========================================================

@app.route(
    "/architecture"
)
@login_required
def architecture():

    return render_template(
        "architecture.html"
    )


# ==========================================================
# CABLAGE
# ==========================================================

@app.route(
    "/cablage"
)
@login_required
def cablage():

    return render_template(
        "cablage.html"
    )


# ==========================================================
# PARAMETRES
# ==========================================================

@app.route(
    "/parametres"
)
@login_required
def parametres():

    return render_template(
        "parametres.html"
    )


# ==========================================================
# ALERTES
# ==========================================================

@app.route(
    "/alertes"
)
@login_required
def alertes():

    return render_template(

        "alertes.html",

        evenements=
            lire_evenements(
                200
            ),

        mesures=
            lire_mesures(
                100
            )
    )


# ==========================================================
# GESTION DES UTILISATEURS
# ==========================================================

@app.route(
    "/admin/utilisateurs",
    methods=[
        "GET",
        "POST"
    ]
)
@login_required
@admin_required
def admin_users():

    form = UserCreationForm()

    if form.validate_on_submit():
        username = (
            form.username.data
            .strip()
            .lower()
        )

        if utilisateur_par_username(
            username
        ):
            flash(
                "Ce login existe déjà.",
                "danger"
            )
        else:
            face_folder = None

            try:
                face_folder, photo_count = (
                    save_profile_images(
                        form.photos.data or [],
                        form.first_name.data.strip(),
                        form.last_name.data.strip()
                    )
                )

                creer_utilisateur(
                    form.first_name.data.strip(),
                    form.last_name.data.strip(),
                    username,
                    generate_password_hash(
                        form.password.data,
                        method="scrypt"
                    ),
                    form.role.data,
                    face_folder
                )

                ajouter_audit(
                    current_user.username,
                    "USER_CREATED",
                    "SUCCES",
                    request.remote_addr,
                    (
                        f"Compte {username} - "
                        f"rôle {form.role.data} - "
                        f"{photo_count} photo(s)"
                    )
                )

                flash(
                    (
                        f"Utilisateur {username} créé. "
                        + (
                            "La vérification faciale est active."
                            if photo_count
                            else
                            "Connexion par mot de passe uniquement."
                        )
                    ),
                    "info"
                )

                return redirect(
                    url_for("admin_users")
                )

            except (
                FaceAuthError,
                ValueError
            ) as error:
                remove_profile_folder(
                    face_folder
                )
                flash(
                    str(error),
                    "danger"
                )

            except sqlite3.IntegrityError:
                remove_profile_folder(
                    face_folder
                )
                flash(
                    "Ce login existe déjà.",
                    "danger"
                )

            except Exception:
                remove_profile_folder(
                    face_folder
                )
                app.logger.exception(
                    "Création utilisateur impossible"
                )
                flash(
                    "Impossible de créer l'utilisateur.",
                    "danger"
                )

    return render_template(
        "users.html",
        form=form,
        utilisateurs=lire_utilisateurs()
    )


# ==========================================================
# SECURITY CENTER
# ==========================================================

@app.route(
    "/security"
)
@login_required
@admin_required
def security():

    audits = lire_audits(
        200
    )


    utilisateur = (
        utilisateur_par_id(
            current_user.id
        )
    )


    return render_template(
        "security.html",
        audits=audits,
        utilisateur=utilisateur
    )


# ==========================================================
# CALCUL RISQUE
# ==========================================================

def calculer_risque(
    etat
):

    score = 0
    raisons = []


    if (
        etat.get(
            "autorisee"
        )
        is False
    ):

        score += 35

        raisons.append(
            "Personne inconnue"
        )


    if (
        etat.get(
            "mouvement_actif"
        )
        and
        etat.get(
            "mouvement_detecte"
        )
    ):

        score += 30

        raisons.append(
            "Mouvement detecte"
        )


    temperature = etat.get(
        "temperature"
    )


    if temperature is not None:

        if temperature > 40:

            score += 20

            raisons.append(
                "Temperature critique"
            )

        elif temperature > 35:

            score += 8

            raisons.append(
                "Temperature elevee"
            )


    humidite = etat.get(
        "humidite"
    )


    if humidite is not None:

        if humidite > 70:

            score += 15

            raisons.append(
                "Humidite critique"
            )


    score = min(
        score,
        100
    )


    if score < 25:

        niveau = "NORMAL"

    elif score < 50:

        niveau = "VIGILANCE"

    elif score < 75:

        niveau = "DANGER"

    else:

        niveau = "CRITIQUE"


    return {
        "score": score,
        "niveau": niveau,
        "raisons": raisons
    }


# ==========================================================
# CORRELATION
# ==========================================================

def correlation(
    x,
    y
):

    if (
        len(x) < 2
        or len(y) < 2
    ):

        return None


    moyenne_x = (
        statistics.mean(
            x
        )
    )


    moyenne_y = (
        statistics.mean(
            y
        )
    )


    numerateur = sum(
        (
            a - moyenne_x
        )
        *
        (
            b - moyenne_y
        )

        for a, b
        in zip(
            x,
            y
        )
    )


    dx = sum(
        (
            a - moyenne_x
        ) ** 2
        for a in x
    )


    dy = sum(
        (
            b - moyenne_y
        ) ** 2
        for b in y
    )


    denominateur = math.sqrt(
        dx * dy
    )


    if denominateur == 0:

        return None


    return round(
        numerateur
        /
        denominateur,
        3
    )


# ==========================================================
# API STATUS
# ==========================================================

@app.route(
    "/api/status"
)
@login_required
def api_status():

    donnees = obtenir_etat()


    donnees["heure"] = (
        datetime.now().strftime(
            "%H:%M:%S"
        )
    )


    donnees["risque"] = (
        calculer_risque(
            donnees
        )
    )


    return jsonify(
        donnees
    )


# ==========================================================
# API ANALYTICS
# ==========================================================

@app.route(
    "/api/analytics"
)
@login_required
def analytics():

    try:

        heures = int(
            request.args.get(
                "heures",
                24
            )
        )

    except ValueError:

        heures = 24


    heures = max(
        1,
        min(
            heures,
            168
        )
    )


    mesures = (
        lire_mesures_depuis(
            heures
        )
    )


    evenements = (
        lire_evenements_depuis(
            heures
        )
    )


    temperatures = [
        float(
            x["temperature"]
        )
        for x in mesures
        if x["temperature"]
        is not None
    ]


    humidites = [
        float(
            x["humidite"]
        )
        for x in mesures
        if x["humidite"]
        is not None
    ]


    def stats(
        valeurs
    ):

        if not valeurs:

            return {
                "moyenne": None,
                "minimum": None,
                "maximum": None,
                "ecart_type": None
            }


        return {

            "moyenne":
                round(
                    statistics.mean(
                        valeurs
                    ),
                    2
                ),

            "minimum":
                round(
                    min(
                        valeurs
                    ),
                    2
                ),

            "maximum":
                round(
                    max(
                        valeurs
                    ),
                    2
                ),

            "ecart_type":
                round(
                    statistics.pstdev(
                        valeurs
                    ),
                    2
                )
                if len(
                    valeurs
                ) > 1
                else 0
        }


    repartition = {

        "Reconnaissance": 0,

        "Mouvement": 0,

        "Temperature": 0,

        "Humidite": 0,

        "Systeme": 0
    }


    mouvements = 0
    alertes = 0
    ok = 0
    echecs = 0


    for event in evenements:

        type_event = event[
            "type"
        ]

        niveau = event[
            "niveau"
        ]


        if type_event in (
            "RECONNAISSANCE",
            "ALERTE_RECONNAISSANCE"
        ):

            repartition[
                "Reconnaissance"
            ] += 1


        elif type_event == "MOUVEMENT":

            repartition[
                "Mouvement"
            ] += 1


        elif type_event == "ALERTE_TEMPERATURE":

            repartition[
                "Temperature"
            ] += 1


        elif type_event == "ALERTE_HUMIDITE":

            repartition[
                "Humidite"
            ] += 1


        else:

            repartition[
                "Systeme"
            ] += 1


        if (
            type_event
            == "MOUVEMENT"
            and
            event.get(
                "valeur"
            )
            == "DETECTE"
        ):

            mouvements += 1


        if niveau in (
            "ALERTE",
            "CRITIQUE"
        ):

            alertes += 1


        if (
            type_event
            == "RECONNAISSANCE"
            and
            niveau == "INFO"
            and
            event.get(
                "valeur"
            )
            not in (
                "DEMARRAGE",
                "ANNULEE"
            )
        ):

            ok += 1


        if (
            type_event
            == "RECONNAISSANCE"
            and
            niveau
            == "ATTENTION"
        ):

            echecs += 1


    total = (
        ok + echecs
    )


    taux = (
        round(
            ok / total * 100,
            1
        )
        if total > 0
        else 0
    )


    return jsonify({

        "mesures": mesures,

        "statistiques": {

            "temperature":
                stats(
                    temperatures
                ),

            "humidite":
                stats(
                    humidites
                ),

            "correlation":
                correlation(
                    temperatures,
                    humidites
                )
        },

        "repartition":
            repartition,

        "kpi": {

            "mouvements":
                mouvements,

            "alertes":
                alertes,

            "reconnaissances_ok":
                ok,

            "reconnaissances_echec":
                echecs,

            "taux_reconnaissance":
                taux
        }
    })


# ==========================================================
# SIRENE ON/OFF
# ==========================================================

@app.route(
    "/api/alarme",
    methods=["POST"]
)
@login_required
def alarme_api():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    active = bool(
        data.get(
            "active",
            True
        )
    )


    regler_alarme(
        active
    )


    ajouter_audit(
        current_user.username,
        (
            "ALARM_ENABLE"
            if active
            else
            "ALARM_DISABLE"
        ),
        "SUCCES",
        request.remote_addr,
        "Commande depuis dashboard"
    )


    return jsonify({
        "success": True,
        "active": active
    })


# ==========================================================
# TEST ALARME
# ==========================================================

@app.route(
    "/api/alarme/test",
    methods=["POST"]
)
@login_required
def alarme_test():

    tester_alarme()


    ajouter_audit(
        current_user.username,
        "ALARM_TEST",
        "SUCCES",
        request.remote_addr,
        "Test manuel sirene"
    )


    return jsonify({
        "success": True
    })


# ==========================================================
# HEADERS SECURITE
# ==========================================================

@app.after_request
def security_headers(
    response
):

    response.headers[
        "X-Content-Type-Options"
    ] = "nosniff"


    response.headers[
        "X-Frame-Options"
    ] = "DENY"


    response.headers[
        "Referrer-Policy"
    ] = "same-origin"


    response.headers[
        "Permissions-Policy"
    ] = (
        "camera=(self), "
        "microphone=(), "
        "geolocation=()"
    )


    if current_user.is_authenticated:

        response.headers[
            "Cache-Control"
        ] = (
            "no-store, "
            "no-cache, "
            "must-revalidate"
        )


    return response


# ==========================================================
# RATE LIMIT ERROR
# ==========================================================

@app.errorhandler(429)
def ratelimit_error(
    erreur
):

    return (
        "Trop de tentatives. "
        "Reessayez dans une minute.",
        429
    )


# ==========================================================
# START
# ==========================================================

if __name__ == "__main__":

    initialiser_db()


    print()
    print(
        "================================"
    )
    print(
        " SENTINEL-X SECURE PLATFORM"
    )
    print(
        "================================"
    )
    print()


    print(
        "http://127.0.0.1:5000/login"
    )

    print()


    demarrer_sentinel()


    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )
