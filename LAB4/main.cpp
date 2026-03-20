#include <Arduino.h>

// Pin assignments
const int xPin = A0;
const int yPin = A1;
const int buttonPin = 2;

const int upLed = 10;
const int downLed = 9;
const int leftLed = 11;
const int rightLed = 6;

void setup() {
  Serial.begin(9600);

  pinMode(buttonPin, INPUT_PULLUP);

  pinMode(upLed, OUTPUT);
  pinMode(downLed, OUTPUT);
  pinMode(leftLed, OUTPUT);
  pinMode(rightLed, OUTPUT);
}

void loop() {
  int xVal = analogRead(xPin);
  int yVal = analogRead(yPin);
  int buttonState = digitalRead(buttonPin);

  // ---- SEND DATA TO PC ----
  Serial.print(xVal);
  Serial.print(",");
  Serial.print(yVal);
  Serial.print(",");
  Serial.println(buttonState == LOW ? 1 : 0); //Arduino USB ilə kompüterə belə sətirlər göndərir:
   //self.ser = serial.Serial(port, 9600, timeout=0.1)
  // ---- LED LOGIC ----
  if (buttonState == LOW) {
    digitalWrite(upLed, HIGH);
    digitalWrite(downLed, HIGH);
    digitalWrite(leftLed, HIGH); 
    digitalWrite(rightLed, HIGH);
  } else {

    int upBrightness = map(yVal, 512, 0, 0, 255);
    int downBrightness = map(yVal, 512, 1023, 0, 255);
    int leftBrightness = map(xVal, 512, 0, 0, 255);
    int rightBrightness = map(xVal, 512, 1023, 0, 255);

    upBrightness = constrain(upBrightness, 0, 255);
    downBrightness = constrain(downBrightness, 0, 255);
    leftBrightness = constrain(leftBrightness, 0, 255);
    rightBrightness = constrain(rightBrightness, 0, 255);

    analogWrite(upLed, (yVal < 500) ? upBrightness : 0);
    analogWrite(downLed, (yVal > 500) ? downBrightness : 0);
    analogWrite(leftLed, (xVal < 500) ? leftBrightness : 0);
    analogWrite(rightLed, (xVal > 524) ? rightBrightness : 0);
  }

  delay(20);
}
