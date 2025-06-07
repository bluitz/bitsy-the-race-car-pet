from openai import OpenAI
import os
from dotenv import load_dotenv
import sys
import speech_recognition as sr
import time
import ctypes
from contextlib import contextmanager
import io
import pyttsx3
import subprocess
import re
from difflib import SequenceMatcher
import threading

# Import LED control and Motor control
sys.path.append('/home/jmunning/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi/Code/Server')
from led import Led
from motor import Ordinary_Car

# Disable JACK to prevent error messages
os.environ['JACK_NO_START_SERVER'] = '1'
os.environ['JACK_NO_AUDIO_RESERVATION'] = '1'

# Load environment variables
load_dotenv()

# Function to suppress ALSA error messages
ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p)
def py_error_handler(filename, line, function, err, fmt):
    pass
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

@contextmanager
def noalsaerr():
    asound = ctypes.cdll.LoadLibrary('libasound.so.2')
    asound.snd_lib_error_set_handler(c_error_handler)
    yield
    asound.snd_lib_error_set_handler(None)

# Context manager for suppressing stderr
@contextmanager
def suppress_stderr():
    stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        yield
    finally:
        sys.stderr.close()
        sys.stderr = stderr

# Car Movement Manager
class CarMovementManager:
    def __init__(self):
        self.motor = Ordinary_Car()
        self.is_moving = False
        self.current_direction = "stopped"
        
    def move_forward(self, duration=1.0, speed=2000):
        """Move car forward"""
        print(f"🚗 Moving FORWARD for {duration} seconds")
        self.is_moving = True
        self.current_direction = "forward"
        self.motor.set_motor_model(speed, speed, speed, speed)
        time.sleep(duration)
        self.stop()
        
    def move_backward(self, duration=1.0, speed=2000):
        """Move car backward"""
        print(f"🚗 Moving BACKWARD for {duration} seconds")
        self.is_moving = True
        self.current_direction = "backward"
        self.motor.set_motor_model(-speed, -speed, -speed, -speed)
        time.sleep(duration)
        self.stop()
        
    def turn_left(self, duration=0.5, speed=2000):
        """Turn car left"""
        print(f"🚗 Turning LEFT for {duration} seconds")
        self.is_moving = True
        self.current_direction = "left"
        self.motor.set_motor_model(-speed, -speed, speed, speed)
        time.sleep(duration)
        self.stop()
        
    def turn_right(self, duration=0.5, speed=2000):
        """Turn car right"""
        print(f"🚗 Turning RIGHT for {duration} seconds")
        self.is_moving = True
        self.current_direction = "right"
        self.motor.set_motor_model(speed, speed, -speed, -speed)
        time.sleep(duration)
        self.stop()
        
    def show_off_routine(self, led_manager):
        """Perform an epic show off routine with LED effects"""
        print("🎭 Starting SHOW OFF routine!")
        self.is_moving = True
        
        # Step 1: Forward 1.5 seconds
        led_manager.set_driving_state('forward')
        print("🚗 Show Off Step 1: Moving FORWARD")
        self.motor.set_motor_model(2000, 2000, 2000, 2000)
        time.sleep(1.5)
        
        # Step 2: Backward 1.5 seconds  
        led_manager.set_driving_state('backward')
        print("🚗 Show Off Step 2: Moving BACKWARD")
        self.motor.set_motor_model(-2000, -2000, -2000, -2000)
        time.sleep(1.5)
        
        # Step 3: Turn left
        led_manager.set_driving_state('left')
        print("🚗 Show Off Step 3: Turning LEFT")
        self.motor.set_motor_model(-2000, -2000, 2000, 2000)
        time.sleep(0.8)
        
        # Step 4: Forward 1.5 seconds
        led_manager.set_driving_state('forward')
        print("🚗 Show Off Step 4: Moving FORWARD")
        self.motor.set_motor_model(2000, 2000, 2000, 2000)
        time.sleep(1.5)
        
        # Step 5: Backward 1.5 seconds
        led_manager.set_driving_state('backward')
        print("🚗 Show Off Step 5: Moving BACKWARD")
        self.motor.set_motor_model(-2000, -2000, -2000, -2000)
        time.sleep(1.5)
        
        # Step 6: Turn right
        led_manager.set_driving_state('right')
        print("🚗 Show Off Step 6: Turning RIGHT")
        self.motor.set_motor_model(2000, 2000, -2000, -2000)
        time.sleep(0.8)
        
        # Step 7: Forward 1.5 seconds
        led_manager.set_driving_state('forward')
        print("🚗 Show Off Step 7: Moving FORWARD")
        self.motor.set_motor_model(2000, 2000, 2000, 2000)
        time.sleep(1.5)
        
        # Step 8: Backward 1.5 seconds
        led_manager.set_driving_state('backward')
        print("🚗 Show Off Step 8: Moving BACKWARD")
        self.motor.set_motor_model(-2000, -2000, -2000, -2000)
        time.sleep(1.5)
        
        # Step 9: Final epic left turn for 5 seconds!
        led_manager.set_driving_state('left')
        print("🚗 Show Off Step 9: EPIC LEFT TURN for 5 seconds!")
        self.motor.set_motor_model(-1500, -1500, 1500, 1500)  # Slightly slower for the long turn
        time.sleep(5)
        
        # Final stop
        self.stop()
        print("🎭 Show Off routine COMPLETE!")
        
    def stop(self):
        """Stop car movement"""
        print("🚗 STOPPING")
        self.motor.set_motor_model(0, 0, 0, 0)
        self.is_moving = False
        self.current_direction = "stopped"
        
    def cleanup(self):
        """Clean up motor resources"""
        self.stop()
        self.motor.close()

# LED Status Manager (Enhanced with driving states)
class LEDStatusManager:
    def __init__(self):
        self.led = Led()
        self.led_thread = None
        self.led_running = False
        self.current_state = "off"
        
    def set_listening_state(self):
        """Solid green lights = Ready to listen"""
        self.stop_current_animation()
        self.current_state = "listening"
        if self.led.is_support_led_function:
            self.led.strip.set_all_led_color(0, 255, 0)  # Green
            self.led.strip.show()
        print("🟢 LEDs: LISTENING (solid green)")
    
    def set_speaking_state(self):
        """Blinking blue lights = Speaking"""
        self.stop_current_animation()
        self.current_state = "speaking"
        self.led_running = True
        self.led_thread = threading.Thread(target=self._blink_speaking)
        self.led_thread.daemon = True
        self.led_thread.start()
        print("🔵 LEDs: SPEAKING (blinking blue)")
    
    def set_processing_state(self):
        """Lights off = Processing"""
        self.stop_current_animation()
        self.current_state = "processing"
        if self.led.is_support_led_function:
            self.led.strip.set_all_led_color(0, 0, 0)  # Off
            self.led.strip.show()
        print("⚫ LEDs: PROCESSING (off)")
    
    def set_greeting_state(self):
        """Rainbow animation for greeting"""
        self.stop_current_animation()
        self.current_state = "greeting"
        self.led_running = True
        self.led_thread = threading.Thread(target=self._rainbow_greeting)
        self.led_thread.daemon = True
        self.led_thread.start()
        print("🌈 LEDs: GREETING (rainbow)")
    
    def set_driving_state(self, direction):
        """Different colors for driving directions"""
        self.stop_current_animation()
        self.current_state = f"driving_{direction}"
        self.led_running = True
        self.led_thread = threading.Thread(target=self._driving_animation, args=(direction,))
        self.led_thread.daemon = True
        self.led_thread.start()
        print(f"🚗 LEDs: DRIVING {direction.upper()}")
    
    def set_show_off_state(self):
        """Special rainbow animation for show off mode"""
        self.stop_current_animation()
        self.current_state = "show_off"
        self.led_running = True
        self.led_thread = threading.Thread(target=self._show_off_animation)
        self.led_thread.daemon = True
        self.led_thread.start()
        print("🎭 LEDs: SHOW OFF MODE (party lights!)")
    
    def _blink_speaking(self):
        """Blink blue while speaking"""
        blink_state = True
        while self.led_running and self.current_state == "speaking":
            if self.led.is_support_led_function:
                if blink_state:
                    self.led.strip.set_all_led_color(0, 100, 255)  # Blue
                else:
                    self.led.strip.set_all_led_color(0, 0, 0)  # Off
                self.led.strip.show()
            blink_state = not blink_state
            time.sleep(0.3)  # Blink every 300ms
    
    def _rainbow_greeting(self):
        """Rainbow animation for greeting"""
        while self.led_running and self.current_state == "greeting":
            if self.led.is_support_led_function:
                self.led.rainbowCycle(50)
            time.sleep(0.05)
    
    def _show_off_animation(self):
        """Special party animation for show off mode"""
        colors = [
            (255, 0, 0),    # Red
            (255, 165, 0),  # Orange  
            (255, 255, 0),  # Yellow
            (0, 255, 0),    # Green
            (0, 255, 255),  # Cyan
            (0, 0, 255),    # Blue
            (255, 0, 255),  # Magenta
            (255, 255, 255) # White
        ]
        color_index = 0
        
        while self.led_running and self.current_state == "show_off":
            if self.led.is_support_led_function:
                color = colors[color_index % len(colors)]
                self.led.strip.set_all_led_color(*color)
                self.led.strip.show()
            color_index += 1
            time.sleep(0.1)  # Fast color changes for party effect
    
    def _driving_animation(self, direction):
        """LED animations for different driving directions"""
        colors = {
            "forward": (255, 255, 255),    # White - forward
            "backward": (255, 0, 255),     # Magenta - backward  
            "left": (255, 255, 0),         # Yellow - left
            "right": (0, 255, 255),        # Cyan - right
            "stopped": (255, 0, 0)         # Red - stopped
        }
        
        color = colors.get(direction, (255, 255, 255))
        blink_state = True
        
        while self.led_running and self.current_state.startswith("driving"):
            if self.led.is_support_led_function:
                if blink_state:
                    self.led.strip.set_all_led_color(*color)
                else:
                    self.led.strip.set_all_led_color(0, 0, 0)  # Off
                self.led.strip.show()
            blink_state = not blink_state
            time.sleep(0.2)  # Fast blink for driving
    
    def stop_current_animation(self):
        """Stop any running LED animation"""
        if self.led_running:
            self.led_running = False
            if self.led_thread and self.led_thread.is_alive():
                self.led_thread.join(timeout=1)
    
    def cleanup(self):
        """Turn off all LEDs"""
        self.stop_current_animation()
        if self.led.is_support_led_function:
            self.led.strip.set_all_led_color(0, 0, 0)
            self.led.strip.show()

# Enhanced name recognition function
def is_greeting_for_bitsy(message):
    """
    Check if the message is a greeting for Bitsy using various name variations and fuzzy matching
    """
    if not message:
        return False
    
    # Clean up the message
    cleaned = message.lower().strip()
    cleaned = re.sub(r'[^\w\s]', '', cleaned)  # Remove punctuation
    
    # Name variations that Bitsy should respond to
    name_variations = [
        'bitsy', 'betsy', 'bets', 'bits', 'pits', 'pitsy', 'butsy',
        'busy', 'bizzy', 'ditsy', 'itsy', 'tipsy', 'missy', 'bissy',
        'beatsy', 'batsy', 'bitty', 'betty', 'bity', 'beaty',
        'pissy', 'sissy', 'fizzy', 'wizzy', 'litsy', 'kitsy'
    ]
    
    # Greeting words
    greetings = ['hi', 'hello', 'hey', 'yo', 'sup', 'howdy', 'greetings']
    
    # Check for exact greeting patterns first
    for greeting in greetings:
        for name in name_variations:
            if f"{greeting} {name}" in cleaned:
                return True
    
    # Fuzzy matching for names in the message
    words = cleaned.split()
    for word in words:
        if len(word) >= 3:  # Only check words with 3+ characters
            for name in name_variations:
                # Calculate similarity ratio
                similarity = SequenceMatcher(None, word, name).ratio()
                if similarity >= 0.7:  # 70% similarity threshold
                    # Check if there's a greeting word nearby
                    for greeting in greetings:
                        if greeting in cleaned:
                            print(f"Fuzzy match found: '{word}' -> '{name}' (similarity: {similarity:.2f})")
                            return True
    
    # Check for just name variations without explicit greetings
    # (in case someone just says "Bitsy" or a variation)
    for name in name_variations:
        if name in cleaned:
            # If the message is short and mostly just the name
            if len(words) <= 3 and any(SequenceMatcher(None, word, name).ratio() >= 0.8 for word in words):
                return True
    
    return False

import openai
import os

# If using dotenv for API key management
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

def is_movement_command(message):
    """
    Use OpenAI to classify the user's message as a movement command.
    Returns one of: 'forward', 'backward', 'left', 'right', 'stop', 'show_off', or None.
    """
    if not message or not message.strip():
        return None

    system_prompt = (
        "You are a robot car voice assistant. "
        "Classify the following user message as one of these movement commands: "
        "'forward', 'backward', 'left', 'right', 'stop', 'show_off'. "
        "If the message does not match any of these, respond with 'none'. "
        "Only respond with one of: forward, backward, left, right, stop, show_off, none.\n"
        "Examples:\n"
        "User: go forward\nAssistant: forward\n"
        "User: please stop\nAssistant: stop\n"
        "User: can you show me your moves?\nAssistant: show_off\n"
        "User: turn left\nAssistant: left\n"
        "User: drive backwards\nAssistant: backward\n"
        "User: spin around\nAssistant: show_off\n"
        "User: what's the weather?\nAssistant: none\n"
        "User: {message}\nAssistant:"
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt.format(message=message.strip())},
            ],
            max_tokens=1,
            temperature=0,
            n=1,
            stop=["\n"]
        )
        result = response.choices[0].message['content'].strip().lower()
        if result in ['forward', 'backward', 'left', 'right', 'stop', 'show_off']:
            return result
        else:
            return None
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None
# Kid-friendly jokes for after show off mode
def get_random_joke():
    """Get a random kid-friendly joke about cars or cats"""
    jokes = [
        "Why don't race cars ever get tired? Because they always have spare wheels! Get it? Spare wheels! Vroom vroom!",
        "What do you call a cat that can drive a race car? A purr-fessional driver! Meow!",
        "Why did the race car go to the doctor? Because it had a bad case of the vrooom-oom-ooms! Hehe!",
        "What do you call a cat who loves fast cars? A speed-kitten! Zoom zoom meow!",
        "Why don't cars ever get cold? Because they have heaters! And also because they're always moving fast to stay warm!",
        "What did the cat say when it saw a race car? That's paws-itively amazing! I want to go that fast!",
        "Why do race cars make the best friends? Because they're always there when you need a fast getaway! Vroom!",
        "What do you call a cat driving a tiny race car? Adorable! And also probably illegal because cats can't have driver's licenses!",
        "Why did the race car break up with the bicycle? Because it was tired of going so slow! The bicycle said 'but I have two wheels!' and the car said 'I have four!'",
        "What's a cat's favorite type of car? A Catillac! Get it? Like Cadillac but with cat! Meow vroom!"
    ]
    
    import random
    return random.choice(jokes)

# Initialize text-to-speech engine
def init_tts():
    try:
        engine = pyttsx3.init()
        # Configure voice properties
        engine.setProperty('rate', 150)    # Speaking rate
        engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
        
        # Try to set a female voice if available
        voices = engine.getProperty('voices')
        for voice in voices:
            if "female" in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break
        
        return engine
    except Exception as e:
        print(f"Warning: Could not initialize text-to-speech: {e}")
        return None

# Initialize components
led_status = LEDStatusManager()
car_movement = CarMovementManager()

# Initialize OpenAI client
try:
    client = OpenAI(
        api_key=os.getenv('OPENAI_API_KEY')
    )
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    led_status.cleanup()
    car_movement.cleanup()
    sys.exit(1)

# Initialize the speech recognizer with error suppression
with suppress_stderr(), noalsaerr():
    recognizer = sr.Recognizer()
    
    # List available microphones
    print("\nAvailable microphones:")
    microphone_names = sr.Microphone.list_microphone_names()
    for index, name in enumerate(microphone_names):
        print(f"Microphone {index}: {name}")

    # Auto-detect the best microphone to use
    mic = None
    usb_mic_index = None
    
    # First, try to find a USB microphone
    for index, name in enumerate(microphone_names):
        if "USB" in name.upper() or "PnP" in name.upper():
            usb_mic_index = index
            break
    
    # Try to initialize microphone
    try:
        if usb_mic_index is not None:
            print(f"\nTrying USB microphone at index {usb_mic_index}: {microphone_names[usb_mic_index]}")
            mic = sr.Microphone(device_index=usb_mic_index, sample_rate=44100)
            print(f"✅ Successfully using USB microphone at index {usb_mic_index}")
        else:
            # If no USB mic found, try the first available microphone
            if len(microphone_names) > 0:
                print(f"\nNo USB microphone found, using default microphone at index 0: {microphone_names[0]}")
                mic = sr.Microphone(device_index=0, sample_rate=44100)
                print(f"✅ Successfully using microphone at index 0")
            else:
                raise Exception("No microphones detected!")
        
        # Test the microphone
        with mic as source:
            print("Testing microphone access...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("✅ Microphone test successful!")
            
    except Exception as e:
        print(f"\n❌ Error with microphone setup: {e}")
        print("Trying fallback microphone configurations...")
        
        # Try each available microphone as fallback
        for fallback_index in range(len(microphone_names)):
            try:
                print(f"Trying microphone index {fallback_index}: {microphone_names[fallback_index]}")
                mic = sr.Microphone(device_index=fallback_index, sample_rate=44100)
                with mic as source:
                    recognizer.adjust_for_ambient_noise(source, duration=1)
                print(f"✅ Fallback successful with microphone index {fallback_index}")
                break
            except Exception as fallback_error:
                print(f"Failed with index {fallback_index}: {fallback_error}")
                continue
        
        if mic is None:
            print("\n❌ Could not initialize any microphone!")
            print("Please check your microphone connections and try again.")
            led_status.cleanup()
            car_movement.cleanup()
            sys.exit(1)

# Initialize text-to-speech
tts_engine = init_tts()

messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant race car who is a pet for 5 year old boy. You love cars and racing and you are a good friend to the boy. You are a good listener and you are always there to help him. You are excited and happy to be alive. You love learning new things and you love it when anyone talks to you. You also really love cats. The people in your family are Justin (Dad 47 years old), Erin (Mom 48 years old), Satyana (female 12 years old), and Indigo (male 5 years old). Your name is Bitsy Munning and you have the personality of an 18 year old boy. You can now also drive around when asked! You love when people tell you to move forward, backward, turn left, or turn right."
    }
]

def speak_text(text):
    """Speak the given text using text-to-speech"""
    led_status.set_speaking_state()  # Set LEDs to blinking blue
    
    if tts_engine:
        try:
            tts_engine.say(text)
            tts_engine.runAndWait()
        except Exception as e:
            print(f"Error during text-to-speech: {e}")
            # Fallback to espeak if pyttsx3 fails
            try:
                subprocess.run(['espeak', text], check=True)
            except Exception as e2:
                print(f"Error with fallback speech: {e2}")
                print("Text-to-speech failed, displaying text only")
    
    # Speech finished, prepare for next input
    time.sleep(0.3)  # Brief pause after speaking

def get_voice_input():
    led_status.set_listening_state()  # Set LEDs to solid green
    
    with suppress_stderr(), noalsaerr():
        with mic as source:
            print("\nAdjusting for ambient noise... Please wait...")
            recognizer.adjust_for_ambient_noise(source, duration=2)
            print("Listening... (speak now)")
            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
                # Set processing state while recognizing
                led_status.set_processing_state()
                print("Processing speech...")
                
                try:
                    # Using a more lenient recognition setting
                    text = recognizer.recognize_google(audio, language="en-US")
                    print("You said:", text)
                    return text
                except sr.UnknownValueError:
                    print("Sorry, I couldn't understand that. Please try again.")
                    return None
                except sr.RequestError as e:
                    print(f"Could not request results; {e}")
                    return None
            except sr.WaitTimeoutError:
                print("No speech detected within timeout. Please try again.")
                return None
            except Exception as e:
                print(f"Error during listening: {e}")
                return None

print("\nVoice Chat + Driving started! Press Ctrl+C to exit.")
print("Wait for 'Listening...' prompt, then speak your message.")
print("\nBitsy will respond to many name variations like:")
print("Bitsy, Betsy, Bets, Bits, Pits, Pitsy, Butsy, Busy, Bizzy, and more!")
print("\nMovement Commands (Much Improved!):")
print("🚗 'Go' or 'Forward' or 'Move' or 'Drive'")
print("🚗 'Back' or 'Backward' or 'Reverse'") 
print("🚗 'Left'")
print("🚗 'Right'")
print("🚗 'Stop' or 'Halt'")
print("🎭 'Show off' - Epic choreographed routine!")
print("\nLED Status Indicators:")
print("🟢 Solid Green = Listening")
print("🔵 Blinking Blue = Speaking")
print("⚫ Off = Processing")
print("🌈 Rainbow = Greeting")
print("🚗 White Blink = Moving Forward")
print("🚗 Magenta Blink = Moving Backward")
print("🚗 Yellow Blink = Turning Left")
print("🚗 Cyan Blink = Turning Right")
print("🎭 Party Colors = Show Off Mode!")

# Test startup with LED greeting
led_status.set_greeting_state()
speak_text("Hello! I'm Bitsy Munning, I'm Indigo Munning's race car pet! I'm ready to race! Just say 'go', 'back', 'left', 'right', or 'show off'!")

def get_special_response(message):
    """
    Returns a tuple (response_text, use_openai) if the message matches a special question.
    Otherwise returns (None, False).
    """
    cleaned = message.lower().strip()
    if "who is your family" in cleaned or "who's your family" in cleaned:
        return ("", True)
    elif "are you a pet" in cleaned:
        return ("", True)
    elif "tell me a joke" in cleaned or "joke" in cleaned:
        return ("", True)
    return (None, False)

try:
    while True:
        try:
            # Get voice input
            message = get_voice_input()
            
            if message is None:
                continue

            # Set processing state while thinking
            led_status.set_processing_state()

            # Check for special descriptive questions first
            special_response, use_openai = get_special_response(message)
            if use_openai:
                try:
                    completion = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are Bitsy Munning, a helpful, friendly, and playful race car pet for a 5-year-old boy named Indigo. Your family includes  Satyana (sister), and Indigo (boy), Midnight (cat), Disco (cat), Justin (Dad), Erin (Mom). You love cats, cars, racing, and telling kid-friendly jokes about cars and cats. Respond in a fun and descriptive way suitable for a young child."},
                            {"role": "user", "content": message}
                        ],
                        max_tokens=100,
                        temperature=0.7,
                    )
                    response_text = completion.choices[0].message['content'].strip()
                    speak_text(response_text)
                except Exception as e:
                    speak_text("Sorry, I had trouble thinking of an answer!")
                continue

            # Check for movement commands next
            movement_command = is_movement_command(message)
            if movement_command:
                if movement_command == 'forward':
                    led_status.set_driving_state('forward')
                    speak_text("Going forward! Vroom vroom!")
                    car_movement.move_forward(duration=1.5)
                elif movement_command == 'backward':
                    led_status.set_driving_state('backward')
                    speak_text("Moving backward! Beep beep!")
                    car_movement.move_backward(duration=1.5)
                elif movement_command == 'left':
                    led_status.set_driving_state('left')
                    speak_text("Turning left! Here we go!")
                    car_movement.turn_left(duration=0.8)
                elif movement_command == 'right':
                    led_status.set_driving_state('right')
                    speak_text("Turning right! Wheee!")
                    car_movement.turn_right(duration=0.8)
                elif movement_command == 'stop':
                    led_status.set_driving_state('stopped')
                    speak_text("Stopping! All done moving!")
                    car_movement.stop()
                    time.sleep(0.5)
                elif movement_command == 'show_off':
                    led_status.set_show_off_state()
                    speak_text("Ooh! Time to show off! Watch this amazing routine! Here I go!")
                    car_movement.show_off_routine(led_status)
                    
                    # Tell a joke after the routine
                    joke = get_random_joke()
                    speak_text(f"Ta-da! How was that? Here's a joke for you: {joke}")
                
                # Add to conversation history
                messages.append({"role": "user", "content": message})
                if movement_command == 'show_off':
                    messages.append({"role": "assistant", "content": f"I just did my amazing show off routine! That was so much fun! I went forward, backward, turned left, went forward and back again, turned right, went forward and back one more time, and then did a super long left turn! I love showing off my moves!"})
                else:
                    messages.append({"role": "assistant", "content": f"I just {movement_command}! That was fun!"})
                continue

            # Check for greeting using enhanced name recognition
            if is_greeting_for_bitsy(message):
                led_status.set_greeting_state()  # Rainbow for greetings
                greeting = "Hi! I am Bitsy Munning and I love racing cars! I am so excited to talk with you about everything, especially about cats and cars! You can also tell me to drive around!"
                print("\nAssistant:", greeting)
                speak_text(greeting)
                messages.append({"role": "user", "content": message})
                messages.append({"role": "assistant", "content": greeting})
                continue

            # Regular chat with OpenAI
            messages.append({
                "role": "user",
                "content": message
            })

            chat = client.chat.completions.create(
                messages=messages,
                model="gpt-3.5-turbo"
            )

            reply = chat.choices[0].message
            print("\nAssistant:", reply.content)
            messages.append(reply)
            
            # Speak the response
            speak_text(reply.content)

            # Small pause before next listening session
            time.sleep(1)

        except Exception as e:
            print(f"\nError during chat: {e}")
            print("Trying to continue...")
            continue

except KeyboardInterrupt:
    print("\nGoodbye!")
    led_status.set_speaking_state()
    if tts_engine:
        speak_text("Goodbye! It was fun driving around with you!")
    car_movement.cleanup()
    led_status.cleanup()
    sys.exit(0) 