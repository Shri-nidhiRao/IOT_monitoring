#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <RTClib.h>
#include <math.h>
#include <EEPROM.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>  // REQUIRED: Install "ArduinoJson" from Arduino Library Manager
#include "max6675.h"

// ================= WIFI =================
const char* ssid = "Realme";
const char* password = "34567890";

// ================= CUSTOM BACKEND =================
// REPLACE THIS with your Render application URL or Local IP
const char* serverUrl = "http://your-render-app.onrender.com"; 

// ================= PRESSURE SENSOR =================
#define PRESSURE_PIN 34
float resistor = 180.0;
float vRef = 3.3;
float adcMax = 4095.0;

// ================= MAX6675 =================
int thermoDO = 12;
int thermoCS = 13;
int thermoCLK = 14;
MAX6675 thermocouple(thermoCLK, thermoCS, thermoDO);

// ================= FUNCTION DECLARATIONS =================
void runMotorLogic();
void handleButtons();
void displayMain(DateTime now);
void displaySetOn();
void displaySetOff();
void displayMorning();
void displayEvening();
void syncWithBackend(float pressure, float temperature);

// ================= EEPROM =================
#define EEPROM_SIZE 20
#define ADDR_ON_TIME  0
#define ADDR_OFF_TIME 8
#define ADDR_MORNING   12
#define ADDR_EVENING   16

void saveFloat(int addr, float value){
  EEPROM.writeBytes(addr, (byte*)&value, sizeof(float));
  EEPROM.commit();
}

float readFloat(int addr){
  float value;
  EEPROM.readBytes(addr, (byte*)&value, sizeof(float));
  return value;
}

// ================= I2C =================
#define LCD_SDA 21
#define LCD_SCL 22
#define RTC_SDA 19
#define RTC_SCL 23

LiquidCrystal_I2C lcd(0x27,16,2);
RTC_DS1307 rtc;

#define SET_RTC_TIME true

// ================= MOTOR =================
#define RELAY_CW 18
#define RELAY_CCW 4

// ================= LIMIT SWITCHES =================
#define SWITCH1 33
#define SWITCH2 32

// ================= BUTTONS =================
#define BTN_UP 16
#define BTN_DOWN 17
#define BTN_SET 5

// ================= SETTINGS =================
float onTime = 5.0;
float offTime = 10.0;

bool decimalMode = false;

int morningHour=11;
int morningMin=0;

int eveningHour=18;
int eveningMin=0;

bool editMinute=false;
int menuPage=0;

bool lastSW1=LOW;
bool lastSW2=LOW;

// ================= STATES =================
enum MotorState{
WAIT_MODE,
CW_MODE,
CCW_MODE
};

MotorState currentState=WAIT_MODE;

// ================= TIMER =================
unsigned long lastSyncTime = 0;

// ================= SETUP =================
void setup(){

  Serial.begin(115200);

  Wire.begin(LCD_SDA,LCD_SCL);
  Wire1.begin(RTC_SDA,RTC_SCL);

  lcd.init();
  lcd.backlight();

  EEPROM.begin(EEPROM_SIZE);

  onTime = readFloat(ADDR_ON_TIME);
  offTime = readFloat(ADDR_OFF_TIME);

  float morningSaved = readFloat(ADDR_MORNING);
  float eveningSaved = readFloat(ADDR_EVENING);

  if(!isnan(morningSaved) && morningSaved > 0 && morningSaved < 24){
    morningHour = (int)morningSaved;
    morningMin  = (morningSaved - morningHour) * 100;
  }

  if(!isnan(eveningSaved) && eveningSaved > 0 && eveningSaved < 24){
    eveningHour = (int)eveningSaved;
    eveningMin  = (eveningSaved - eveningHour) * 100;
  }

  if(isnan(onTime) || onTime<=0 || onTime>100) onTime = 5.0;
  if(isnan(offTime) || offTime<=0 || offTime>100) offTime = 10.0;

  if(!rtc.begin(&Wire1)){
  lcd.print("RTC ERROR!");
  while(1);
  }

  if(SET_RTC_TIME){
  rtc.adjust(DateTime(__DATE__, __TIME__));
  }

  pinMode(RELAY_CW,OUTPUT);
  pinMode(RELAY_CCW,OUTPUT);

  pinMode(SWITCH1,INPUT_PULLUP);
  pinMode(SWITCH2,INPUT_PULLUP);

  pinMode(BTN_UP,INPUT_PULLUP);
  pinMode(BTN_DOWN,INPUT_PULLUP);
  pinMode(BTN_SET,INPUT_PULLUP);

  digitalWrite(RELAY_CW,HIGH);
  digitalWrite(RELAY_CCW,HIGH);

  // ===== ADC SETUP =====
  analogReadResolution(12);
  analogSetPinAttenuation(PRESSURE_PIN, ADC_11db);

  // ===== WIFI =====
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }

  lcd.clear();
}

// ================= LOOP =================
void loop(){

  handleButtons();

  if(menuPage==0){
    runMotorLogic();
  }

  // ===== TWO-WAY SYNC (EVERY 15 SECONDS) =====
  if(millis() - lastSyncTime > 15000){

    // Calculate PRESSURE
    long sum = 0;
    for(int i=0;i<10;i++){
      sum += analogRead(PRESSURE_PIN);
      delay(5);
    }
    float adcValue = sum/10.0;
    float voltage = (adcValue/adcMax)*vRef;
    float current_mA = (voltage/resistor)*1000.0;
    float pressure = ((current_mA - 4.0)*250.0)/16.0;

    if(pressure<0) pressure=0;
    if(pressure>250) pressure=250;

    // Calculate TEMPERATURE
    float temperature = thermocouple.readCelsius();

    Serial.print("Pressure: "); Serial.print(pressure);
    Serial.print(" bar | Temp: "); Serial.println(temperature);

    // Communicate with Custom Python Backend
    syncWithBackend(pressure, temperature);

    lastSyncTime = millis();
  }

  delay(50);
}

// ================= TWO WAY SYNC FUNCTION =================
void syncWithBackend(float pressure, float temperature){
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  HTTPClient http;

  // --------------------------------------------------------
  // 1. FETCH SCHEDULE (GET /schedule)
  // --------------------------------------------------------
  String scheduleUrl = String(serverUrl) + "/schedule";
  http.begin(scheduleUrl);
  int httpCode = http.GET();
  
  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();
    
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, payload);
    
    if (!error) {
      // Decode and apply updates if available
      String newOnTimeStr = doc["on_time"] | "";
      String newOffTimeStr = doc["off_time"] | "";
      String newMorningStr = doc["morning_time"] | "";
      String newEveningStr = doc["evening_time"] | "";

      if(newOnTimeStr != "--" && newOnTimeStr.length() > 0) {
         float incomingOnTime = newOnTimeStr.toFloat();
         if(incomingOnTime > 0 && incomingOnTime != onTime) {
            onTime = incomingOnTime;
            saveFloat(ADDR_ON_TIME, onTime);
         }
      }

      if(newOffTimeStr != "--" && newOffTimeStr.length() > 0) {
         float incomingOffTime = newOffTimeStr.toFloat();
         if(incomingOffTime > 0 && incomingOffTime != offTime) {
            offTime = incomingOffTime;
            saveFloat(ADDR_OFF_TIME, offTime);
         }
      }

      // Parse HH:MM into Integers
      if(newMorningStr != "--:--" && newMorningStr.length() >= 5) {
        int inMHour = newMorningStr.substring(0,2).toInt();
        int inMMin = newMorningStr.substring(3,5).toInt();
        if(inMHour != morningHour || inMMin != morningMin){
           morningHour = inMHour; morningMin = inMMin;
           float val = morningHour + (morningMin/100.0);
           saveFloat(ADDR_MORNING, val);
        }
      }

      if(newEveningStr != "--:--" && newEveningStr.length() >= 5) {
        int inEHour = newEveningStr.substring(0,2).toInt();
        int inEMin = newEveningStr.substring(3,5).toInt();
        if(inEHour != eveningHour || inEMin != eveningMin){
           eveningHour = inEHour; eveningMin = inEMin;
           float val = eveningHour + (eveningMin/100.0);
           saveFloat(ADDR_EVENING, val);
        }
      }
    }
  }
  http.end();


  // --------------------------------------------------------
  // 2. SEND TELEMETRY (POST /update)
  // --------------------------------------------------------
  String updateUrl = String(serverUrl) + "/update";
  http.begin(updateUrl);
  http.addHeader("Content-Type", "application/json");

  // Construct formatted Strings
  char mornBuf[6];
  sprintf(mornBuf, "%02d:%02d", morningHour, morningMin);
  char eveBuf[6];
  sprintf(eveBuf, "%02d:%02d", eveningHour, eveningMin);

  String motStatus = "WAIT";
  if(currentState == CW_MODE) motStatus = "CW";
  if(currentState == CCW_MODE) motStatus = "CCW";

  StaticJsonDocument<512> postDoc;
  postDoc["mainid"] = "ESP32_Device_1";
  postDoc["device_name"] = "Main Controller";
  postDoc["temperature"] = temperature;
  postDoc["pressure"] = pressure;
  postDoc["status"] = "OK";
  postDoc["limitA"] = !digitalRead(SWITCH1); // false if LOW based on INPUT_PULLUP logic
  postDoc["limitB"] = !digitalRead(SWITCH2);
  postDoc["on_time"] = String(onTime);
  postDoc["off_time"] = String(offTime);
  postDoc["morning_time"] = String(mornBuf);
  postDoc["evening_time"] = String(eveBuf);
  postDoc["motor_status"] = motStatus;

  String requestBody;
  serializeJson(postDoc, requestBody);

  http.POST(requestBody);
  http.end();
}

// ================= MOTOR LOGIC =================
void runMotorLogic(){

static bool waitLock = false;
static int lastNowMin = -1;

bool sw1 = digitalRead(SWITCH1);
bool sw2 = digitalRead(SWITCH2);

DateTime now = rtc.now();

int nowMin = now.hour()*60 + now.minute();
int morningMinTotal = morningHour*60 + morningMin;
int eveningMinTotal = eveningHour*60 + eveningMin;

static bool sunsetTriggered = false;

if(nowMin >= eveningMinTotal && !sunsetTriggered){
    currentState = CCW_MODE;
    sunsetTriggered = true;
}

if(nowMin < eveningMinTotal){
    sunsetTriggered = false;
}

if(sw2 == LOW && lastSW2 == HIGH){
    currentState = CCW_MODE;
}

if(currentState == CCW_MODE){
    if(sw1 == LOW && lastSW1 == HIGH){
        currentState = WAIT_MODE;
        waitLock = true;

        digitalWrite(RELAY_CCW, HIGH);

        lastSW1 = sw1;
        lastSW2 = sw2;
        displayMain(now);
        return;
    }
}

if(currentState == WAIT_MODE){
    waitLock = true;
}

if(waitLock){
    if(lastNowMin < morningMinTotal && nowMin >= morningMinTotal){
        waitLock = false;
        currentState = CW_MODE;
    }
}

lastNowMin = nowMin;

if(!waitLock){
    if(currentState != CCW_MODE && currentState != WAIT_MODE){
        if(nowMin >= morningMinTotal && nowMin < eveningMinTotal){
            currentState = CW_MODE;
        }
    }
}

static unsigned long previousMillis = 0;
static bool motorOn = false;

switch(currentState){

case WAIT_MODE:
    digitalWrite(RELAY_CW, HIGH);
    digitalWrite(RELAY_CCW, HIGH);
    break;

case CW_MODE:

    if(motorOn){
        if(millis() - previousMillis >= (unsigned long)(onTime * 1000)){
            motorOn = false;
            previousMillis = millis();
        }
    }
    else{
        if(millis() - previousMillis >= (unsigned long)(offTime * 1000)){
            motorOn = true;
            previousMillis = millis();
        }
    }

    digitalWrite(RELAY_CW, motorOn ? LOW : HIGH);
    digitalWrite(RELAY_CCW, HIGH);
    break;

case CCW_MODE:
    digitalWrite(RELAY_CW, HIGH);
    digitalWrite(RELAY_CCW, LOW);
    break;
}

lastSW1 = sw1;
lastSW2 = sw2;

displayMain(now);
}

// ================= BUTTON SYSTEM =================
void handleButtons(){

static unsigned long pressTime=0;
static bool btnPressed=false;

if(digitalRead(BTN_SET)==LOW){
if(!btnPressed){
btnPressed=true;
pressTime=millis();
}
}
else{
if(btnPressed){
unsigned long duration=millis()-pressTime;
btnPressed=false;

if(duration>800){
if(menuPage==1 || menuPage==2){
decimalMode=!decimalMode;
}
else if(menuPage==3 || menuPage==4){
editMinute=!editMinute;
}
}
else{
menuPage++;
if(menuPage>4){
menuPage=0;
editMinute=false;
lcd.clear();
}
}
}
}

// ON TIME
if(menuPage==1){
if(digitalRead(BTN_UP)==LOW){
if(decimalMode) onTime+=0.1;
else onTime+=1;
saveFloat(ADDR_ON_TIME, onTime);
delay(200);
}
if(digitalRead(BTN_DOWN)==LOW && onTime>0.1){
if(decimalMode) onTime-=0.1;
else onTime-=1;
saveFloat(ADDR_ON_TIME, onTime);
delay(200);
}
displaySetOn();
}

// OFF TIME
if(menuPage==2){
if(digitalRead(BTN_UP)==LOW){
if(decimalMode) offTime+=0.1;
else offTime+=1;
saveFloat(ADDR_OFF_TIME, offTime);
delay(200);
}
if(digitalRead(BTN_DOWN)==LOW && offTime>0.1){
if(decimalMode) offTime-=0.1;
else offTime-=1;
saveFloat(ADDR_OFF_TIME, offTime);
delay(200);
}
displaySetOff();
}

if(menuPage==3){

if(digitalRead(BTN_UP)==LOW){
if(!editMinute) morningHour=(morningHour+1)%24;
else morningMin=(morningMin+1)%60;

float val = morningHour + (morningMin/100.0);
saveFloat(ADDR_MORNING, val);

delay(200);
}

if(digitalRead(BTN_DOWN)==LOW){
if(!editMinute) morningHour=(morningHour+23)%24;
else morningMin=(morningMin+59)%60;

float val = morningHour + (morningMin/100.0);
saveFloat(ADDR_MORNING, val);

delay(200);
}

displayMorning();
}

if(menuPage==4){

if(digitalRead(BTN_UP)==LOW){
if(!editMinute) eveningHour=(eveningHour+1)%24;
else eveningMin=(eveningMin+1)%60;

float val = eveningHour + (eveningMin/100.0);
saveFloat(ADDR_EVENING, val);

delay(200);
}

if(digitalRead(BTN_DOWN)==LOW){
if(!editMinute) eveningHour=(eveningHour+23)%24;
else eveningMin=(eveningMin+59)%60;

float val = eveningHour + (eveningMin/100.0);
saveFloat(ADDR_EVENING, val);

delay(200);
}

displayEvening();
}
}


// ================= DISPLAY =================
void displayMain(DateTime now){
lcd.setCursor(0,0);

if(now.hour()<10)lcd.print("0");
lcd.print(now.hour());
lcd.print(":");

if(now.minute()<10)lcd.print("0");
lcd.print(now.minute());
lcd.print(":");

if(now.second()<10)lcd.print("0");
lcd.print(now.second());

lcd.print(" ");

if(currentState==WAIT_MODE)lcd.print("WAIT");
else if(currentState==CW_MODE)lcd.print("CW  ");
else lcd.print("CCW ");

lcd.setCursor(0,1);
lcd.print("ON:");
lcd.print(onTime, 1);
lcd.print(" OFF:");
lcd.print(offTime, 1);
lcd.print("   ");
}

// ================= DISPLAY FUNCTIONS =================
void displaySetOn(){
lcd.setCursor(0,0);
lcd.print("Set ON Time     ");
lcd.setCursor(0,1);
lcd.print("Seconds: ");
lcd.print(onTime, 1);
lcd.print("      ");
}

void displaySetOff(){
lcd.setCursor(0,0);
lcd.print("Set OFF Time    ");
lcd.setCursor(0,1);
lcd.print("Seconds: ");
lcd.print(offTime, 1);
lcd.print("      ");
}

void displayMorning(){
lcd.setCursor(0,0);
lcd.print("Set Morning Time");
lcd.setCursor(0,1);

if(morningHour<10) lcd.print("0");
lcd.print(morningHour);
lcd.print(":");

if(morningMin<10) lcd.print("0");
lcd.print(morningMin);

lcd.print(editMinute ? " MIN " : " HOUR");
lcd.print("   ");
}

void displayEvening(){
lcd.setCursor(0,0);
lcd.print("Set Evening Time");
lcd.setCursor(0,1);

if(eveningHour<10) lcd.print("0");
lcd.print(eveningHour);
lcd.print(":");

if(eveningMin<10) lcd.print("0");
lcd.print(eveningMin);

lcd.print(editMinute ? " MIN " : " HOUR");
lcd.print("   ");
}
