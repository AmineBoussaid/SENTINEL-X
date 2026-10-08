function getCsrfToken() {

    return document
        .querySelector(
            'meta[name="csrf-token"]'
        )
        .getAttribute(
            "content"
        );
}

let environmentChart = null;
let eventsChart = null;
let correlationChart = null;

let alarmEnabled = true;


// ==========================================================
// ETAT TEMPS REEL
// ==========================================================

async function actualiserEtat() {

    try {

        const response =
            await fetch(
                "/api/status"
            );

        const data =
            await response.json();


        // ==========================================
        // TEMPERATURE
        // ==========================================

        document
            .getElementById(
                "temperature"
            )
            .textContent =
            data.temperature === null
                ? "-- °C"
                : `${data.temperature} °C`;


        // ==========================================
        // HUMIDITE
        // ==========================================

        document
            .getElementById(
                "humidite"
            )
            .textContent =
            data.humidite === null
                ? "-- %"
                : `${data.humidite} %`;


        // ==========================================
        // PERSONNE
        // ==========================================

        document
            .getElementById(
                "personne"
            )
            .textContent =
            data.personne;


        document
            .getElementById(
                "heure"
            )
            .textContent =
            data.heure;


        document
            .getElementById(
                "event-text"
            )
            .textContent =
            data.dernier_evenement;


        // ==========================================
        // RECONNAISSANCE
        // ==========================================

        const auth =
            document.getElementById(
                "autorisation"
            );

        const face =
            document.getElementById(
                "face-status"
            );


        if (
            data.autorisee === true
        ) {

            auth.textContent =
                "AUTORISÉ";

            auth.className =
                "status-success";

            face.textContent =
                `${data.personne} ✓`;

        }

        else if (
            data.autorisee === false
        ) {

            auth.textContent =
                "NON AUTORISÉ";

            auth.className =
                "status-danger";

            face.textContent =
                "INCONNU";

        }

        else {

            auth.textContent =
                "IDENTIFICATION";

            auth.className =
                "status-warning";

            face.textContent =
                "EN COURS";
        }


        // ==========================================
        // MOUVEMENT
        // ==========================================

        const motion =
            document.getElementById(
                "motion-status"
            );


        if (
            data.mouvement_actif
        ) {

            motion.textContent =
                data.mouvement_detecte
                    ? "DÉTECTÉ"
                    : "ACTIF";

        }

        else {

            motion.textContent =
                "OFF";
        }


        // ==========================================
        // THREAT SCORE
        // ==========================================

        const risque =
            data.risque;


        document
            .getElementById(
                "risk-score"
            )
            .textContent =
            risque.score;


        document
            .getElementById(
                "risk-circle-value"
            )
            .textContent =
            risque.score;


        const level =
            document.getElementById(
                "risk-level"
            );


        level.textContent =
            risque.niveau;


        level.className =
            "risk-level "
            +
            risque.niveau.toLowerCase();


        const reasons =
            document.getElementById(
                "risk-reasons"
            );


        if (
            risque.raisons.length === 0
        ) {

            reasons.innerHTML =
                "✓ Aucun facteur de risque";

        }

        else {

            reasons.innerHTML =
                risque.raisons
                    .map(
                        reason =>
                            `<div>• ${reason}</div>`
                    )
                    .join("");
        }


        // ==========================================
        // GLOBAL STATUS
        // ==========================================

        const security =
            document.getElementById(
                "security-status"
            );


        if (
            data.alarme
        ) {

            security.textContent =
                "ALERTE EN COURS";

        }

        else if (
            data.phase
            === "RECONNAISSANCE"
        ) {

            security.textContent =
                "IDENTIFICATION";

        }

        else {

            security.textContent =
                "SYSTÈME OPÉRATIONNEL";
        }


        // ==========================================
        // ALARM BUTTON
        // ==========================================

        alarmEnabled =
            data.alarme_active;


        updateAlarmButton();

    }

    catch (error) {

        console.error(
            "SENTINEL-X:",
            error
        );
    }
}


// ==========================================================
// DATA ANALYTICS
// ==========================================================

async function chargerAnalytics() {

    const heures =
        document
            .getElementById(
                "periode"
            )
            .value;


    const response =
        await fetch(
            `/api/analytics?heures=${heures}`
        );


    const data =
        await response.json();


    // ==========================================
    // STATS
    // ==========================================

    const temp =
        data.statistiques.temperature;

    const hum =
        data.statistiques.humidite;


    setText(
        "temp-moyenne",
        temp.moyenne === null
            ? "--"
            : `${temp.moyenne} °C`
    );


    setText(
        "hum-moyenne",
        hum.moyenne === null
            ? "--"
            : `${hum.moyenne} %`
    );


    setText(
        "stat-temp-mean",
        temp.moyenne === null
            ? "--"
            : `${temp.moyenne} °C`
    );


    setText(
        "stat-temp-std",
        temp.ecart_type === null
            ? "--"
            : temp.ecart_type
    );


    setText(
        "stat-hum-mean",
        hum.moyenne === null
            ? "--"
            : `${hum.moyenne} %`
    );


    setText(
        "stat-hum-std",
        hum.ecart_type === null
            ? "--"
            : hum.ecart_type
    );


    setText(
        "stat-correlation",
        data.statistiques.correlation
        ?? "--"
    );


    setText(
        "stat-recognition",
        `${data.kpi.taux_reconnaissance} %`
    );


    setText(
        "stat-movements",
        data.kpi.mouvements
    );


    setText(
        "stat-alerts",
        data.kpi.alertes
    );


    // ==========================================
    // TIME SERIES
    // ==========================================

    const labels =
        data.mesures.map(
            item =>
                formatTime(
                    item.date_heure
                )
        );


    const temperatures =
        data.mesures.map(
            item =>
                item.temperature
        );


    const humidites =
        data.mesures.map(
            item =>
                item.humidite
        );


    if (
        environmentChart
    ) {

        environmentChart.destroy();
    }


    environmentChart =
        new Chart(
            document.getElementById(
                "environmentChart"
            ),
            {

                type: "line",

                data: {

                    labels: labels,

                    datasets: [

                        {

                            label:
                                "Température °C",

                            data:
                                temperatures,

                            borderWidth: 2,

                            tension: 0.35,

                            pointRadius: 1,

                            yAxisID:
                                "yTemperature"
                        },

                        {

                            label:
                                "Humidité %",

                            data:
                                humidites,

                            borderWidth: 2,

                            tension: 0.35,

                            pointRadius: 1,

                            yAxisID:
                                "yHumidite"
                        }

                    ]
                },


                options: {

                    responsive: true,

                    maintainAspectRatio:
                        false,

                    interaction: {

                        intersect:
                            false,

                        mode:
                            "index"
                    },

                    plugins: {

                        legend: {

                            labels: {

                                color:
                                    "#aeb9ca"
                            }
                        }
                    },

                    scales: {

                        x: {

                            ticks: {

                                color:
                                    "#6f7d91",

                                maxTicksLimit:
                                    8
                            },

                            grid: {

                                color:
                                    "rgba(255,255,255,.04)"
                            }
                        },

                        yTemperature: {

                            position:
                                "left",

                            ticks: {

                                color:
                                    "#8c99ac"
                            },

                            grid: {

                                color:
                                    "rgba(255,255,255,.05)"
                            }
                        },

                        yHumidite: {

                            position:
                                "right",

                            ticks: {

                                color:
                                    "#8c99ac"
                            },

                            grid: {

                                drawOnChartArea:
                                    false
                            }
                        }
                    }
                }
            }
        );


    // ==========================================
    // EVENTS
    // ==========================================

    if (
        eventsChart
    ) {

        eventsChart.destroy();
    }


    eventsChart =
        new Chart(
            document.getElementById(
                "eventsChart"
            ),
            {

                type: "doughnut",

                data: {

                    labels:
                        Object.keys(
                            data.repartition
                        ),

                    datasets: [

                        {

                            data:
                                Object.values(
                                    data.repartition
                                )
                        }
                    ]
                },


                options: {

                    responsive:
                        true,

                    maintainAspectRatio:
                        false,

                    plugins: {

                        legend: {

                            position:
                                "bottom",

                            labels: {

                                color:
                                    "#aeb9ca"
                            }
                        }
                    }
                }
            }
        );


    // ==========================================
    // CORRELATION SCATTER
    // ==========================================

    if (
        correlationChart
    ) {

        correlationChart.destroy();
    }


    const scatterData =
        data.mesures.map(
            item => ({

                x:
                    item.temperature,

                y:
                    item.humidite
            })
        );


    correlationChart =
        new Chart(
            document.getElementById(
                "correlationChart"
            ),
            {

                type:
                    "scatter",

                data: {

                    datasets: [

                        {

                            label:
                                "Mesures",

                            data:
                                scatterData,

                            pointRadius:
                                4
                        }
                    ]
                },


                options: {

                    responsive:
                        true,

                    maintainAspectRatio:
                        false,

                    plugins: {

                        legend: {

                            labels: {

                                color:
                                    "#aeb9ca"
                            }
                        }
                    },

                    scales: {

                        x: {

                            title: {

                                display:
                                    true,

                                text:
                                    "Température °C",

                                color:
                                    "#8190a5"
                            },

                            ticks: {

                                color:
                                    "#8190a5"
                            },

                            grid: {

                                color:
                                    "rgba(255,255,255,.05)"
                            }
                        },

                        y: {

                            title: {

                                display:
                                    true,

                                text:
                                    "Humidité %",

                                color:
                                    "#8190a5"
                            },

                            ticks: {

                                color:
                                    "#8190a5"
                            },

                            grid: {

                                color:
                                    "rgba(255,255,255,.05)"
                            }
                        }
                    }
                }
            }
        );
}


// ==========================================================
// ALARME
// ==========================================================

function updateAlarmButton() {

    const button =
        document.getElementById(
            "alarm-toggle"
        );


    if (
        alarmEnabled
    ) {

        button.textContent =
            "🔊 SIRÈNE ACTIVE";

        button.className =
            "control-button active";

    }

    else {

        button.textContent =
            "🔇 SIRÈNE DÉSACTIVÉE";

        button.className =
            "control-button disabled";
    }
}


async function toggleAlarm() {

    alarmEnabled =
        !alarmEnabled;


    await fetch(
        "/api/alarme",
        {

            method:
                "POST",

            headers: {

                "Content-Type":
                    "application/json",

                "X-CSRFToken":
                    getCsrfToken()
            },

            body:
                JSON.stringify({

                    active:
                        alarmEnabled
                })
        }
    );


    updateAlarmButton();
}


async function testAlarm() {

    await fetch(
        "/api/alarme/test",
        {

            method: "POST",

            headers: {

                "X-CSRFToken":
                    getCsrfToken()
            }
        }
    );
}


// ==========================================================
// HELPERS
// ==========================================================

function setText(
    id,
    value
) {

    document
        .getElementById(
            id
        )
        .textContent =
        value;
}


function formatTime(
    date
) {

    const morceaux =
        date.split(
            " "
        );


    if (
        morceaux.length < 2
    ) {

        return date;
    }


    return morceaux[1];
}


// ==========================================================
// EVENTS
// ==========================================================

document
    .getElementById(
        "periode"
    )
    .addEventListener(
        "change",
        chargerAnalytics
    );


document
    .getElementById(
        "alarm-toggle"
    )
    .addEventListener(
        "click",
        toggleAlarm
    );


document
    .getElementById(
        "alarm-test"
    )
    .addEventListener(
        "click",
        testAlarm
    );


// ==========================================================
// START
// ==========================================================

actualiserEtat();

chargerAnalytics();


setInterval(
    actualiserEtat,
    1000
);


setInterval(
    chargerAnalytics,
    10000
);