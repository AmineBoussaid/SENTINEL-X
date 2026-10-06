#include <Arduino.h>
#include <DHT.h>
#include <math.h>

#define DHT_PIN D5
#define DHT_TYPE DHT22

#define TRIG_PIN D1
#define ECHO_PIN D2

#define SEUIL_MOUVEMENT 15.0

DHT dht(DHT_PIN, DHT_TYPE);

float ancienneDistance = -1;

float lireDistance() {

  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);

  digitalWrite(TRIG_PIN, LOW);

  long duree = pulseIn(ECHO_PIN, HIGH, 30000);

  if (duree == 0) {
    return -1;
  }

  float distance = duree * 0.0343 / 2.0;

  if (distance < 2 || distance > 400) {
    return -1;
  }

  return distance;
}

void setup() {

  Serial.begin(115200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  dht.begin();

  delay(2000);

  Serial.println("SENTINEL-X DEMARRE");
}

void loop() {

  float temperature = dht.readTemperature();
  float humidite = dht.readHumidity();

  float distance = lireDistance();

  Serial.println("---------------------");

  if (!isnan(temperature)) {
    Serial.print("Temperature : ");
    Serial.print(temperature);
    Serial.println(" C");
  }

  if (!isnan(humidite)) {
    Serial.print("Humidite : ");
    Serial.print(humidite);
    Serial.println(" %");
  }

  if (distance > 0) {

    Serial.print("Distance : ");
    Serial.print(distance);
    Serial.println(" cm");

    if (ancienneDistance > 0) {

      float difference = fabs(distance - ancienneDistance);

      if (difference >= SEUIL_MOUVEMENT) {

        Serial.println("Mouvement : OUI");

        // Python va détecter exactement ce message
        Serial.println("ALERTE_MOUVEMENT");

      } else {

        Serial.println("Mouvement : NON");
      }
    }

    ancienneDistance = distance;

  } else {

    Serial.println("Distance : ERREUR");
  }

  delay(500);
}