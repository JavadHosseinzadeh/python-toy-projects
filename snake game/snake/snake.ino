// Pin definitions
const int SW_PIN = A0;  // The analog pin connected to the Keyes KY-023

// Threshold values for the SW positions
const int SW1_THRESHOLD = 100;  // Left
const int SW2_THRESHOLD = 300;  // Up
const int SW3_THRESHOLD = 500;  // Down
const int SW4_THRESHOLD = 700;  // Right
const int SW5_THRESHOLD = 900;  // Center (press)

void setup() {
  Serial.begin(9600);  // Initialize serial communication
  pinMode(SW_PIN, INPUT);  // Set SW_PIN as input
}

void loop() {
  int sw_value = analogRead(SW_PIN);  // Read the analog value

  // Determine which position the joystick is in and send the corresponding character
  if (sw_value < SW1_THRESHOLD) {
    Serial.print("A\r\n");  // SW1: Left
  } else if (sw_value < SW2_THRESHOLD) {
    Serial.print("W\r\n");  // SW2: Up
  } else if (sw_value < SW3_THRESHOLD) {
    Serial.print("S\r\n");  // SW3: Down
  } else if (sw_value < SW4_THRESHOLD) {
    Serial.print("D\r\n");  // SW4: Right
  } else if (sw_value < SW5_THRESHOLD) {
    Serial.print("Z\r\n");  // SW5: Center press (acts like space key)
  }

  delay(100);  // Add a small delay to avoid overwhelming the serial communication
}
