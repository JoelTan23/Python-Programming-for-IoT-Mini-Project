# Airconditioner system
#
##########################################################################################################
# Imports
import Adafruit_DHT
import RPi.GPIO as GPIO
import time
import threading
import requests
import I2C_LCD_driver 
import json

from flask import Flask, render_template,request,url_for

from telegrambot import telegram_bot 


##########################################################################################################
# Set up
# Set up the DHT sensor
DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN = 4  # GPIO pin where the DHT sensor is connected

# Website
app=Flask(__name__)

# Set up the GPIO for the LED
LED_PIN = 27
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.output(LED_PIN, GPIO.LOW)

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
        system_status ="on"
    else:
        system_status="off"

    if system_status == "on":
        url = "/system_off"
    else:
        url = "/system_on"
    return render_template('index.html', system_status=system_status,url = url)
    
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
    

# Function for the main timer feature
# AC Timer Thread
def airconditioner_timer():
    global elapsed_time
    global ac_on_start_time

    while True:
        # Read humidity and temperature from the DHT sensor
        humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)

        # Checks if the DHT Sensor Successfully reads the Humidity and the Temperature
        if humidity is not None and temperature is not None:\
            #Prints out the Humidity and the Temperature inside of the terminal / Serial Monitor
            print(f"Humidity: {humidity:.2f}%, Temperature: {temperature:.2f}°C")        

            #Calls on the function to check if the airconditioner is on
            if is_air_conditioner_on(humidity, temperature):
                #Checks that the start timer is 0
                if ac_on_start_time is 0:
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
        time.sleep(2)  # Wait for 2 seconds before the next reading

# Keypad Interrupt Thread
def keypad_interrupt():
   # Place Holder Code
    print("hi")

# Upload_Data_Thread
def upload_data():
    # Upload data to thinkspeak
    while 1:
        humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)
        resp = requests.get("https://api.thingspeak.com/update?api_key=Q5WYV1VLWZQGPWBR&field1=0",format(temperature,humidity))
        time.sleep(20) # Need to sleep for at least 20

def display_lcd(string,pos1,pos2):
    LCD = I2C_LCD_driver.lcd() #instantiate an lcd object, call it LCD
    LCD.backlight(1) #turn backlight on
    LCD.lcd_display_string("String", pos1,pos2)

def clear_lcd():
    LCD = I2C_LCD_driver.lcd()
    LCD.lcd_clear()

##########################################################################################################
# Telegram Bot
# 7443228939:AAH1Yc_Zb4LpH_naJC1o2TbbKj_zCaBU-2I
# telegram_bot()

##########################################################################################################
# Main function that holds essentially all the code
def main():
    if system_status == 1:
        # Declaring the Threads
        ac_timer_thread = threading.Thread(target=airconditioner_timer)  # Thread for the airconditioner_timer function
        keypad_interrupt_thread = threading.Thread(target=keypad_interrupt)  # Thread for the keypad_interrupt function
        upload_data_thread = threading.Thread(target=upload_data)

        # Starting up the Threads
        ac_timer_thread.start()
        keypad_interrupt_thread.start()
        upload_data_thread.start()

    
    elif system_status == 0:
        global elapsed_time
        global ac_on_start_time
        
        # Stop the timer / System
        
        elapsed_time = time.time() - ac_on_start_time
        display_lcd("Timer Stopped",1,1)
        time.sleep(20)
        clear_lcd()


        # Shows previous readings
        resp=requests.get("https://api.thingspeak.com/channels/2591947/feeds.json?api_key=XUXD1E5DUX4K5W4T&results=2")  
        print(resp.text)
        previous_readings = json.loads(resp.text) # Converts the downloaded data from the cloud from json
        # Prints into the terminal / serial monitor
        for x in range(10):
            print("Previous Reading ",x,": temperature =",previous_readings["feeds"][x]["field1"],", humidity =",previous_readings["feeds"][x]["field2"])

            string = "Temperature " % x
            display_lcd(string,1,1) # Lable the reading below
            string = str(previous_readings["feeds"][x]["field1"]) # creates string for LCD function
            display_lcd(string,2,2) # LCD dislays temperature
            time.sleep(2)

            string = "Humidity " % x
            display_lcd(string,1,1) # Lable the reading below
            string = str(previous_readings["feeds"][x]["field2"])
            display_lcd(string,2,2) # LCD displays humidity
            time.sleep(2)

##########################################################################################################

# Code Starts here
if __name__ == "__main__":
    #app.run(debug=True,host='0.0.0.0') #0.0.0.0 -> Any device in the network can access the app
    flask_thread = threading.Thread(target=app.run, kwargs={'debug': True, 'host': '0.0.0.0'})
    flask_thread.start()
    main()

    