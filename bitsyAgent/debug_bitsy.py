#!/usr/bin/env python3
"""
Debug script for Bitsy to test individual components
"""

import sys
import os
import time
import logging
import signal

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add Freenove library path (same logic as main script)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_candidate_paths = [
    # 1) Within this repo (as when running in dev environment)
    os.path.join(PROJECT_ROOT, "Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi-master", "Code", "Server"),
    # 2) A sibling directory to bitsyAgent (common on the Pi)
    os.path.join(os.path.dirname(PROJECT_ROOT), "Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi-master", "Code", "Server"),
    # 3) Installed under home
    os.path.join(os.path.expanduser("~"), "Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi-master", "Code", "Server"),
    os.path.join(os.path.expanduser("~"), "Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi", "Code", "Server"),
]

for _path in _candidate_paths:
    if os.path.exists(os.path.join(_path, "servo.py")):
        sys.path.append(_path)
        logger.info(f"Found Freenove library at: {_path}")
        break
else:
    logger.error("Could not find Freenove library")

def signal_handler(sig, frame):
    logger.info("Received interrupt signal - forcing exit")
    os._exit(1)

# Handle Ctrl+C more aggressively
signal.signal(signal.SIGINT, signal_handler)

def test_servo_only():
    """Test servo operations in isolation"""
    logger.info("Testing servo operations...")
    try:
        from servo import Servo
        servo = Servo()
        
        logger.info("Moving to center position")
        servo.set_servo_pwm('0', 80)
        servo.set_servo_pwm('1', 115)
        time.sleep(1)
        
        logger.info("Testing listening position")
        servo.set_servo_pwm('0', 75)
        servo.set_servo_pwm('1', 120)
        time.sleep(1)
        
        logger.info("Returning to center")
        servo.set_servo_pwm('0', 80)
        servo.set_servo_pwm('1', 115)
        
        logger.info("Servo test completed successfully")
        return True
    except Exception as e:
        logger.error(f"Servo test failed: {e}")
        return False

def test_microphone_only():
    """Test microphone operations in isolation"""
    logger.info("Testing microphone...")
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        
        # Try to find a microphone
        mics = sr.Microphone.list_microphone_names()
        logger.info(f"Available microphones: {mics}")
        
        mic = sr.Microphone()
        logger.info("Calibrating microphone...")
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
        
        logger.info("Testing microphone access...")
        with mic as source:
            logger.info("Listening for 3 seconds...")
            try:
                audio = recognizer.listen(source, timeout=3, phrase_time_limit=2)
                logger.info("Audio captured successfully")
            except sr.WaitTimeoutError:
                logger.info("No audio captured (timeout)")
        
        logger.info("Microphone test completed successfully")
        return True
    except Exception as e:
        logger.error(f"Microphone test failed: {e}")
        return False

def test_audio_playback():
    """Test audio playback"""
    logger.info("Testing audio playback...")
    try:
        # Create a simple test sound
        test_cmd = 'echo "Testing audio" | espeak 2>/dev/null'
        result = os.system(test_cmd)
        if result == 0:
            logger.info("Audio playback test completed successfully")
            return True
        else:
            logger.error(f"Audio playback failed with code {result}")
            return False
    except Exception as e:
        logger.error(f"Audio playback test failed: {e}")
        return False

def main():
    logger.info("Starting Bitsy component tests...")
    
    print("1. Testing servo operations...")
    servo_ok = test_servo_only()
    
    print("2. Testing microphone access...")
    mic_ok = test_microphone_only()
    
    print("3. Testing audio playback...")
    audio_ok = test_audio_playback()
    
    print(f"\nResults:")
    print(f"Servo: {'✅ OK' if servo_ok else '❌ FAILED'}")
    print(f"Microphone: {'✅ OK' if mic_ok else '❌ FAILED'}")
    print(f"Audio: {'✅ OK' if audio_ok else '❌ FAILED'}")
    
    if not all([servo_ok, mic_ok, audio_ok]):
        print("\n❌ Some components failed - check logs above")
        sys.exit(1)
    else:
        print("\n✅ All components working!")

if __name__ == "__main__":
    main() 