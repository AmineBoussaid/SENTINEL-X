from flask import (
    Flask,
    render_template,
    jsonify,
    request
)

from datetime import datetime
import math
import statistics


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
    lire_evenements_depuis
)


app = Flask(
    __name__
)


# ==========================================================
# RISQUE SENTINEL-X
# ==========================================================

def calculer_risque(etat):

    score = 0

    raisons = []


    if etat.get(
        "autorisee"
    ) is False:

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
            "Mouvement détecté"
        )


    temperature = etat.get(
        "temperature"
    )


    if (
        temperature
        is not None
    ):

        if temperature > 40:

            score += 20

            raisons.append(
                "Température critique"
            )

        elif temperature > 35:

            score += 8

            raisons.append(
                "Température élevée"
            )


    humidite = etat.get(
        "humidite"
    )


    if (
        humidite
        is not None
    ):

        if humidite > 70:

            score += 15

            raisons.append(
                "Humidité critique"
            )

        elif humidite > 65:

            score += 5

            raisons.append(
                "Humidité élevée"
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


    moyenne_x = statistics.mean(
        x
    )

    moyenne_y = statistics.mean(
        y
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


    denominateur_x = sum(
        (
            a - moyenne_x
        ) ** 2
        for a in x
    )


    denominateur_y = sum(
        (
            b - moyenne_y
        ) ** 2
        for b in y
    )


    denominateur = math.sqrt(
        denominateur_x
        *
        denominateur_y
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
# PAGES
# ==========================================================

@app.route("/")
def dashboard():

    return render_template(
        "dashboard.html"
    )


@app.route("/architecture")
def architecture():

    return render_template(
        "architecture.html"
    )


@app.route("/cablage")
def cablage():

    return render_template(
        "cablage.html"
    )


@app.route("/alertes")
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


@app.route("/parametres")
def parametres():

    return render_template(
        "parametres.html"
    )


# ==========================================================
# API STATUS
# ==========================================================

@app.route("/api/status")
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
# API DATA ANALYTICS
# ==========================================================

@app.route("/api/analytics")
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


    mesures = lire_mesures_depuis(
        heures
    )


    evenements = (
        lire_evenements_depuis(
            heures
        )
    )


    temperatures = [

        float(
            m["temperature"]
        )

        for m in mesures

        if m["temperature"]
        is not None
    ]


    humidites = [

        float(
            m["humidite"]
        )

        for m in mesures

        if m["humidite"]
        is not None
    ]


    def statistiques(
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

            "moyenne": round(
                statistics.mean(
                    valeurs
                ),
                2
            ),

            "minimum": round(
                min(
                    valeurs
                ),
                2
            ),

            "maximum": round(
                max(
                    valeurs
                ),
                2
            ),

            "ecart_type": (
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
            )
        }


    repartition = {

        "Reconnaissance": 0,

        "Mouvement": 0,

        "Température": 0,

        "Humidité": 0,

        "Système": 0
    }


    mouvements = 0

    alertes = 0

    reconnaissances_ok = 0

    reconnaissances_echec = 0


    for event in evenements:

        type_event = event[
            "type"
        ]


        niveau = event[
            "niveau"
        ]


        if (
            type_event
            in (
                "RECONNAISSANCE",
                "ALERTE_RECONNAISSANCE"
            )
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
                "Température"
            ] += 1


        elif type_event == "ALERTE_HUMIDITE":

            repartition[
                "Humidité"
            ] += 1


        else:

            repartition[
                "Système"
            ] += 1


        if (
            type_event
            == "MOUVEMENT"
            and event.get(
                "valeur"
            ) == "DETECTE"
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
            and niveau == "INFO"
            and event.get(
                "valeur"
            )
            not in (
                "DEMARRAGE",
                "ANNULEE"
            )
        ):

            reconnaissances_ok += 1


        if (
            type_event
            == "RECONNAISSANCE"
            and niveau
            == "ATTENTION"
        ):

            reconnaissances_echec += 1


    total_reconnaissance = (
        reconnaissances_ok
        +
        reconnaissances_echec
    )


    if total_reconnaissance:

        taux_reconnaissance = round(

            (
                reconnaissances_ok
                /
                total_reconnaissance
            )
            *
            100,

            1
        )

    else:

        taux_reconnaissance = 0


    return jsonify({

        "periode_heures":
            heures,

        "mesures":
            mesures,

        "statistiques": {

            "temperature":
                statistiques(
                    temperatures
                ),

            "humidite":
                statistiques(
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
                reconnaissances_ok,

            "reconnaissances_echec":
                reconnaissances_echec,

            "taux_reconnaissance":
                taux_reconnaissance
        }

    })


# ==========================================================
# ALARME ON / OFF
# ==========================================================

@app.route(
    "/api/alarme",
    methods=["POST"]
)
def alarme_api():

    donnees = (
        request.get_json(
            silent=True
        )
        or {}
    )


    active = bool(
        donnees.get(
            "active",
            True
        )
    )


    regler_alarme(
        active
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
def alarme_test():

    tester_alarme()


    return jsonify({

        "success": True
    })


# ==========================================================
# HISTORIQUE
# ==========================================================

@app.route(
    "/api/historique"
)
def historique_api():

    return jsonify({

        "evenements":
            lire_evenements(
                200
            ),

        "mesures":
            lire_mesures(
                200
            )
    })


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
        " SENTINEL-X SECURITY DATA CENTER"
    )
    print(
        "================================"
    )
    print()

    print(
        "http://127.0.0.1:5000"
    )

    print()


    demarrer_sentinel()


    app.run(

        host="127.0.0.1",

        port=5000,

        debug=False,

        use_reloader=False
    )