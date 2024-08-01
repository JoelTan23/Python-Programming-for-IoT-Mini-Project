# Airconditioner system
#
##########################################################################################################
# Imports
import Adafruit_DHT
import RPi.GPIO as GPIO
from time import sleep
import time
import threading
import requests
import I2C_LCD_driver 
import json
import queue

from flask import Flask, render_template,request,url_for

from telegrambot import telegram_bot 

##########################################################################################################
# Set up
# Set up the DHT sensor
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 21  # GPIO pin where the DHT sensor is connected

# Set up for Keypad
LCD = I2C_LCD_driver.lcd()

# Website
app=Flask(__name__)

# Set up the GPIO for the LED
LED_PIN = 24
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.output(LED_PIN, GPIO.LOW)

BUZZER_PIN = 18

##########################################################################################################
# Variables 
# Define the humidity and temperature ranges
Minimum_Humidity = 30
Maximum_Humidity= 50
Minimuim_Temperature = 18
Maximum_Temperature = 26

elapsed_time = 0
ac_on_start_time = 0
system_status = 1 
usage_status = "Ok"
##########################################################################################################
# Website
@app.route('/')
def home():
    global system_status
    if system_status == 1:
        system_status_str ="on"
    else:
        system_status_str="off"

    if system_status == "on":
        url = "/system_off"
    else:
        url = "/system_on"

    # Code for testing
    url="/system_on"
    system_status_str="on"

    return render_template('index.html', system_status=system_status_str,url=url)

@app.route('/system_off')
def system_off():
    global system_status 
    system_status = 0
    message = "Airconditioner Switched On"
    telegram_bot(message)
    return render_template("system_off.html",elapsed_time=elapsed_time)

@app.route('/system_on')
def system_on():
    global system_status
    system_status = 1
    message = "Airconditioner Switched Off"
    telegram_bot(message)
    return render_template("system_on.html",elapsed_time=elapsed_time)

###########################################################################################################
# Functions

# Function to check if air conditioner is on
def is_air_conditioner_on(humidity, temperature):
    if Minimum_Humidity <= humidity <= Maximum_Humidity and Minimuim_Temperature <= temperature <= Maximum_Temperature == 1:
        return 1
    
def exceeded_useage():
    global usage_status
    usage_status = "Exceeded"
    message = "Airconditioner Usage Exceeded! Please turn off airconditioner as soon as possible. Turn off airconditioner via this link: 127.0.0.1:5500 "
    telegram_bot(message)
    while usage_status != 'Ok':
        GPIO(LED_PIN,GPIO.HIGH)
        GPIO(BUZZER_PIN,GPIO.HIGH)
        sleep(5)

# Keypad stuff
keypad_queue = queue.Queue()

def key_pressed(key):
    keypad_queue.put(key)

def get_key():
    MATRIX=[ [1,2,3],
            [4,5,6],
            [7,8,9],
            ['*',0,'#']] #layout of keys on keypad
    ROW=[6,20,19,13] #row pins
    COL=[12,5,16] #column pins

    #set column pins as outputs, and write default value of 1 to each
    for i in range(3):
        GPIO.setup(COL[i],GPIO.OUT)
        GPIO.output(COL[i],1)

    #set row pins as inputs, with pull up
    for j in range(4):
        GPIO.setup(ROW[j],GPIO.IN,pull_up_down=GPIO.PUD_UP)

    #scan keypad
    while (True):
        for i in range(3): #loop thru’ all columns
            GPIO.output(COL[i],0) #pull one column pin low
            for j in range(4): #check which row pin becomes low
                if GPIO.input(ROW[j])==0: #if a key is pressed
                    print (MATRIX[j][i]) #print the key pressed
                    while GPIO.input(ROW[j])==0: #debounce
                        sleep(0.1)
            GPIO.output(COL[i],1) #write back default value of 1


##########################################################################################################
# Threads
# Airconditioner_Timer_T
def airconditioner_timer():
    global elapsed_time
    global ac_on_start_time

    while system_status == 1:
        # Read humidity and temperature from the DHT sensor
        humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)

        # Checks if the DHT Sensor Successfully reads the Humidity and the Temperature
        if humidity is not None and temperature is not None:
            #Prints out the Humidity and the Temperature inside of the terminal / Serial Monitor
            print(f"Humidity: {humidity:.2f}%, Temperature: {temperature:.2f}°C")   
            upload_data()     

            #Calls on the function to check if the airconditioner is on
            if is_air_conditioner_on(humidity, temperature):
                #Checks that the start timer is 0
                if ac_on_start_time == 0:
                    ac_on_start_time = time.time()  # Start the timer
                else:
                    elapsed_time = time.time() - ac_on_start_time
                    print(f"Air conditioner has been on for {elapsed_time:.2f} seconds")  # Prints into terminal / Serial Monitor

                    # Checks if the airconditioner has been on for more than 60 Seconds (Shortened for testing sake)
                    if elapsed_time > 60:
                        GPIO.output(LED_PIN, GPIO.HIGH)  # Turn on the LED
                        print("LED ON: Air conditioner has been on for more than a minute")
                        exceeded_useage()
            else:
                ac_on_start_time = None  # Reset the timer
                GPIO.output(LED_PIN, GPIO.LOW)  # Turn off the LED

        else:
            print("Failed to retrieve data from humidity sensor")
        time.sleep(20)  # Wait for 20 seconds before the next reading

    elapsed_time = time.time() - ac_on_start_time
    LCD.lcd_display_string("Timer Stopped",1)
    LCD.lcd_clear()

# Upload_Data_Thread
def upload_data():
    # Upload data to thinkspeak
    humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)
    resp = requests.get("https://api.thingspeak.com/update?api_key=Q5WYV1VLWZQGPWBR&field1=0",format(temperature,humidity))
    # time.sleep(20) # Need to sleep for at least 20

# Keypad_Interrupt_Thread
def keypad_interupt():
    # Display initial message
        
    while True:
        LCD.lcd_display_string("Press 1 for elapsed time", 1)
        LCD.lcd_display_string("Press 2 for humidity and temperature", 2)
        sleep(5)
        LCD.lcd_display_string("Press 3 for On/OFF", 1)
        sleep(5)
        
        key = None
        while key not in [1, 2, 3]:
            key = keypad_queue.get()

        if key:
            if key == '1':
                LCD.lcd_display_string(str(elapsed_time,1))
            elif key == '2':
                # Shows previous readings
                resp=requests.get("https://api.thingspeak.com/channels/2591947/feeds.json?api_key=XUXD1E5DUX4K5W4T&results=2")  
                print(resp.text)
                previous_readings = json.loads(resp.text) # Converts the downloaded data from the cloud from json
                # Prints into the terminal / serial monitor
                for x in range(10):
                    print("Previous Reading ",x,": temperature =",previous_readings["feeds"][x]["field1"],", humidity =",previous_readings["feeds"][x]["field2"])

                    string = "Temperature " % x
                    LCD.lcd_display_string(string,1) # Lable the reading below
                    # string = str(previous_readings["feeds"][x]["field1"]) # creates string for LCD function
                    LCD.lcd_display_string(str(previous_readings["feeds"][x]["field1"]),2) # LCD dislays temperature
                    time.sleep(2)
                    LCD.lcd_clear()

                    string = "Humidity " % x
                    LCD.lcd_display_string(string,1) # Lable the reading below
                    # string = str(previous_readings["feeds"][x]["field2"])
                    LCD.lcd_display_string(str(previous_readings["feeds"][x]["field2"]),2) # LCD displays humidity
                    time.sleep(2)
                    LCD.lcd_clear()

            elif key == '3':                       # On / Off toggle button
                global system_status
                if system_status == 1:
                    system_status = 0
                    LCD.lcd_display_string("System OFF",1)
                    print("Turn the whole system off")
                elif system_status == 0:
                    system_status = 1
                    LCD.lcd_display_string("System ON",1)
                    print("Turn the whole system on")
                
##########################################################################################################
# Telegram Bot
# 7443228939:AAH1Yc_Zb4LpH_naJC1o2TbbKj_zCaBU-2I
# telegram_bot()
##########################################################################################################
# Main function that holds essentially all the code
def main():
    # if system_status == 1:
        # Declaring the Threads
        ac_timer_thread = threading.Thread(target=airconditioner_timer)  # Thread for the airconditioner_timer function
        keypad_interrupt_thread = threading.Thread(target=keypad_interupt)  # Thread for the keypad_interrupt function
        keypad_thread = threading.Thread(target=get_key)
        
        ac_timer_thread.start()
        keypad_interrupt_thread.start()
        keypad_thread.start()


##########################################################################################################

# Code Starts here
if __name__ == "__main__":
    flask_thread = threading.Thread(target=app.run, kwargs={'debug': True, 'host': '0.0.0.0'})
    flask_thread.start()
    main()

