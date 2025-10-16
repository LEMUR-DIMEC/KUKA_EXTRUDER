#include <AccelStepper.h>
long currentMillis; // Current milliseconds
long retractionMillis; // Retraction milliseconds
long retractionTime = 600; // Time of retraction
int STEP = 4; // Pulse pin
int DIR  = 5; // Direction pin
int ENA = 6; // Enable pin
int BUTTON = 2; // Button pin
long RPM = 800; 
long SPR = 400; // Steps per revolution
long SPS; // Steps per second, used in setSpeed()
bool counter; // Counter used for changing direction
AccelStepper stepper(1, STEP, DIR); // Construct a stepper in driver mode (1)

void setup()
{  
  stepper.setEnablePin(ENA);
  stepper.setPinsInverted(0, 0, 1);
  stepper.enableOutputs();

  stepper.setAcceleration(SPS/3);
  SPS = ((RPM * SPR) / 60);
  stepper.setMaxSpeed(SPS);	
  stepper.setSpeed(SPS);

  attachInterrupt(digitalPinToInterrupt(BUTTON), retraction, FALLING);
  counter = 1;
}

void loop()
{ 
  currentMillis = millis(); 
  if ((currentMillis - retractionMillis) <= retractionTime && digitalRead(BUTTON)==LOW){
    stepper.runSpeed();
  }
  else {
  if (counter == 0) {
    stepper.setSpeed(SPS);
    counter = 1;
    }
  }
  while (digitalRead(BUTTON)==HIGH){
    currentMillis = millis();
    stepper.runSpeed();
  }
}

void retraction() {
  retractionMillis = currentMillis;
  stepper.setSpeed(-SPS);
  counter = 0;
}