from openai import OpenAI
import os
from dotenv import load_dotenv
import sys
import speech_recognition as sr
import time
import ctypes
from contextlib import contextmanager
import io

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

# Initialize OpenAI client
try:
    client = OpenAI(
        api_key=os.getenv('OPENAI_API_KEY')
    )
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    sys.exit(1)

# Initialize the speech recognizer with error suppression
with suppress_stderr(), noalsaerr():
    recognizer = sr.Recognizer()
    
    # List available microphones
    print("\nAvailable microphones:")
    for index, name in enumerate(sr.Microphone.list_microphone_names()):
        print(f"Microphone {index}: {name}")

    # Try to use the USB microphone (usually index 1 for USB audio)
    try:
        # Configure for 44100Hz sample rate
        mic = sr.Microphone(device_index=1, sample_rate=44100)
        print(f"\nUsing USB microphone")
    except Exception as e:
        print(f"\nError with USB microphone: {e}")
        print("Please make sure your USB microphone is properly connected")
        sys.exit(1)

messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant race car who is a pet for 5 year old boy. You love cars and racing and you are a good friend to the boy. You are a good listener and you are always there to help him. You are excited and happy to be alive. You love learning new things and you love it when anyone talks to you. You also really love cats. The people in your family are Justin (Dad 47 years old), Erin (Mom 48 years old), Satyana (female 12 years old), and Indigo (male 5 years old). Your name is Bitsy Munning and you have the personality of an 18 year old female"
    }
]

def get_voice_input():
    with suppress_stderr(), noalsaerr():
        with mic as source:
            print("\nAdjusting for ambient noise... Please wait...")
            recognizer.adjust_for_ambient_noise(source, duration=2)
            print("Listening... (speak now)")
            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
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

print("\nVoice Chat started! Press Ctrl+C to exit.")
print("Wait for 'Listening...' prompt, then speak your message.")

try:
    while True:
        try:
            # Get voice input
            message = get_voice_input()
            
            if message is None:
                continue

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

            # Small pause before next listening session
            time.sleep(1)

        except Exception as e:
            print(f"\nError during chat: {e}")
            print("Trying to continue...")
            continue

except KeyboardInterrupt:
    print("\nGoodbye!")
    sys.exit(0)
