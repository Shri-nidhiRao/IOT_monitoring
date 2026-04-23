#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <RTClib.h>
#include <math.h>
#include <EEPROM.h>
#include <WiFi.h>
#include <esp_now.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ================= WIFI =================
const char* ssid = "Realme";
const char* password = "34567890";

// ================= API =================
const char* postServer = "https://iot-monitoring-8nc3.onrender.com/update";
const char* getServer  = "https://iot-monitoring-8nc3.onrender.com/schedule";

unsigned long lastSync = 0;

// ================= SYNC CONTROL =================
enum ChangeSource { FROM_NONE, FROM_API, FROM_HARDWARE };
ChangeSource lastSource = FROM_NONE;
unsigned long lastChangeTime = 0;
#define LOCK_TIME 5000   // 5 sec protection

// ================= FUNCTION DECLARATIONS =================
void runMotorLogic();
void handleButtons();
void displayMain(DateTime now);
void displaySetOn();
void displaySetOff();
void displayMorning();
void displayEvening();

// ================= ESP-NOW =================
typedef struct {
  float pressure;
  float temperature;
} SensorData;

SensorData receivedData;

// ================= EEPROM =================
#define EEPROM_SIZE 20
#define ADDR_ON_TIME  0
#define ADDR_OFF_TIME 8
#define ADDR_MORNING  12
#define ADDR_EVENING  16

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

// ================= PINS =================
#define RELAY_CW 18
#define RELAY_CCW 4
#define SWITCH1 33
#define SWITCH2 32
#define BTN_UP 16
#define BTN_DOWN 17
#define BTN_SET 5

// ================= SETTINGS =================
float onTime = 5.0;
float offTime = 10.0;

int morningHour=11;
int morningMin=0;

int eveningHour=18;
int eveningMin=0;

bool decimalMode=false;
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

// ================= ESP-NOW =================
void onReceive(const esp_now_recv_info_t *info, const uint8_t *incomingData, int len) {
  memcpy(&receivedData, incomingData, sizeof(receivedData));
}

void sendToAPI(){

  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(postServer);
  http.addHeader("Content-Type", "application/json");

  // ===== FORMAT TIMES =====
  char onBuf[6];
  char offBuf[6];
  sprintf(onBuf, "%02d:%02d", (int)onTime, (int)(round((onTime - (int)onTime) * 100)));
  sprintf(offBuf, "%02d:%02d", (int)offTime, (int)(round((offTime - (int)offTime) * 100)));
  String onStr = String(onBuf);
  String offStr = String(offBuf);

  String morningStr = String(morningHour) + ":" + String(morningMin);
  String eveningStr = String(eveningHour) + ":" + String(eveningMin);

  // ===== MOTOR STATUS =====
  String motorStatus = "WAIT";
  if (currentState == CW_MODE) motorStatus = "CW";
  else if (currentState == CCW_MODE) motorStatus = "CCW";

  // ===== JSON =====
  String json = "{";
  json += "\"mainid\":\"ESP32_001\",";
  json += "\"Device_name\":\"SolarTracker\",";
  json += "\"temperature\":" + String(receivedData.temperature,2) + ",";
  json += "\"pressure\":" + String(receivedData.pressure,2) + ",";
  json += "\"on_time\":\"" + onStr + "\",";
  json += "\"off_time\":\"" + offStr + "\",";
  json += "\"morning_time\":\"" + morningStr + "\",";
  json += "\"evening_time\":\"" + eveningStr + "\",";
  json += "\"motor_status\":\"" + motorStatus + "\"";
  json += "}";

  int code = http.POST(json);

  Serial.print("POST Response: ");
  Serial.println(code);

  http.end();
}

// ================= FETCH FROM API =================
void fetchFromAPI(){

  if (WiFi.status() != WL_CONNECTED) return;

  // 🔒 Prevent overwrite if recent hardware change
  if(millis() - lastChangeTime < LOCK_TIME) return;

  HTTPClient http;
  http.begin(getServer);

  if(http.GET()==200){

    StaticJsonDocument<256> doc;
    if(!deserializeJson(doc, http.getString())){

      String newOnStr = doc["on_time"] | "";
      String newOffStr = doc["off_time"] | "";
      
      float newOn = onTime;
      float newOff = offTime;

      // Parse incoming SS:MM properly into float
      if (newOnStr.length() > 0 && newOnStr != "--") {
          int colonIdx = newOnStr.indexOf(':');
          if (colonIdx != -1) {
              float sec = newOnStr.substring(0, colonIdx).toFloat();
              String msStr = newOnStr.substring(colonIdx + 1);
              float ms = msStr.toFloat();
              if(msStr.length() == 3) ms /= 1000.0;
              else ms /= 100.0;
              newOn = sec + ms;
          } else {
              newOn = newOnStr.toFloat();
          }
      }

      if (newOffStr.length() > 0 && newOffStr != "--") {
          int colonIdx = newOffStr.indexOf(':');
          if (colonIdx != -1) {
              float sec = newOffStr.substring(0, colonIdx).toFloat();
              String msStr = newOffStr.substring(colonIdx + 1);
              float ms = msStr.toFloat();
              if(msStr.length() == 3) ms /= 1000.0;
              else ms /= 100.0;
              newOff = sec + ms;
          } else {
              newOff = newOffStr.toFloat();
          }
      }

      String mStr = doc["morning_time"] | "";
      String eStr = doc["evening_time"] | "";

      int mh, mm, eh, em;

      if(sscanf(mStr.c_str(), "%d:%d", &mh, &mm)==2){
        if(mh!=morningHour || mm!=morningMin){
          morningHour=mh;
          morningMin=mm;
          saveFloat(ADDR_MORNING, mh + mm/100.0);
          lastSource = FROM_API;
          lastChangeTime = millis();
        }
      }

      if(sscanf(eStr.c_str(), "%d:%d", &eh, &em)==2){
        if(eh!=eveningHour || em!=eveningMin){
          eveningHour=eh;
          eveningMin=em;
          saveFloat(ADDR_EVENING, eh + em/100.0);
          lastSource = FROM_API;
          lastChangeTime = millis();
        }
      }

      if(newOn != onTime){
        onTime = newOn;
        saveFloat(ADDR_ON_TIME,onTime);
        lastSource = FROM_API;
        lastChangeTime = millis();
      }

      if(newOff != offTime){
        offTime = newOff;
        saveFloat(ADDR_OFF_TIME,offTime);
        lastSource = FROM_API;
        lastChangeTime = millis();
      }
    }
  }

  http.end();
}

// ================= SETUP =================
void setup(){

Serial.begin(115200);

Wire.begin(LCD_SDA,LCD_SCL);
Wire1.begin(RTC_SDA,RTC_SCL);

lcd.init();
lcd.backlight();

EEPROM.begin(EEPROM_SIZE);

// ===== RTC FIX =====
if(!rtc.begin(&Wire1)){
  lcd.print("RTC ERROR!");
  while(1);
}

if(!rtc.isrunning()){
  rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
}

// ================= PINS =================
pinMode(RELAY_CW,OUTPUT);
pinMode(RELAY_CCW,OUTPUT);
pinMode(SWITCH1,INPUT_PULLUP);
pinMode(SWITCH2,INPUT_PULLUP);
pinMode(BTN_UP,INPUT_PULLUP);
pinMode(BTN_DOWN,INPUT_PULLUP);
pinMode(BTN_SET,INPUT_PULLUP);

digitalWrite(RELAY_CW,HIGH);
digitalWrite(RELAY_CCW,HIGH);

// ================= WIFI =================
WiFi.mode(WIFI_STA);
WiFi.begin(ssid, password);

while (WiFi.status() != WL_CONNECTED) delay(500);

// ================= ESP-NOW =================
esp_now_init();
esp_now_register_recv_cb(onReceive);

lcd.clear();
}

// ================= LOOP =================
void loop(){

handleButtons();

if(menuPage==0){
runMotorLogic();
}

// ===== SYNC =====
if (millis() - lastSync > 15000) {
  // Call fetch first, then send. That way, any changes fetched from API
  // are immediately pushed back in the next send To confirm!
  fetchFromAPI();
  sendToAPI();
  lastSync = millis();
}

delay(50);
}

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
