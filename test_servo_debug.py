#!/usr/bin/env python3
import time
import sys
sys.path.append("/home/jmunning/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi/Code/Server")

print("Step 1: Importing PCA9685...")
from pca9685 import PCA9685

print("Step 2: Creating PCA9685 instance...")
try:
    pwm = PCA9685(0x40, debug=False)  # Turn off debug to avoid spam
    print("Step 3: PCA9685 created successfully!")
except Exception as e:
    print(f"Error creating PCA9685: {e}")
    exit(1)

print("Step 4: Setting PWM frequency...")
try:
    pwm.set_pwm_freq(50)
    print("Step 5: Frequency set successfully!")
except Exception as e:
    print(f"Error setting frequency: {e}")
    exit(1)

print("Step 6: Testing one servo pulse...")
try:
    pwm.set_servo_pulse(8, 1500)  # Channel 8, neutral position
    print("Step 7: Servo pulse set successfully!")
except Exception as e:
    print(f"Error setting servo pulse: {e}")
    exit(1)

print("All steps completed successfully!") 