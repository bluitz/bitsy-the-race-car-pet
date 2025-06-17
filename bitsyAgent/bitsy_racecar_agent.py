"""bitsy_racecar_agent.py
A voice-controlled agent ("Bitsy") that listens via microphone, uses OpenAI
function-calling to decide whether to drive the Freenove 4WD car, change LED
patterns, stop, or just chat cheerfully with the user.  Responses are read
aloud with OpenAI TTS so Indigo hears Bitsy talk.
"""

from __future__ import annotations

import json
import os
import sys
import time
import logging
from typing import Dict, Tuple, Optional

import speech_recognition as sr
from pygame import mixer  # type: ignore
from openai import OpenAI

# ---------------------------------------------------------------------------
#  Hardware drivers (Freenove library)
# ---------------------------------------------------------------------------
# Attempt to locate the Freenove "Code/Server" directory that contains motor.py
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
    if os.path.exists(os.path.join(_path, "motor.py")):
        sys.path.append(_path)
        break

try:
    from motor import Ordinary_Car  # type: ignore
    from led import Led  # type: ignore
    from servo import Servo  # type: ignore
except Exception as exc:  # pragma: no cover – hardware-dependent
    raise RuntimeError(
        "Could not import Freenove drivers. Tried paths:\n  " + "\n  ".join(_candidate_paths)
    ) from exc

PARAM_FILE = os.path.join(os.path.dirname(__file__), "params.json")

# ---------------------------------------------------------------------------
#  Ensure Freenove params.json exists to avoid interactive prompt
# ---------------------------------------------------------------------------

def _ensure_params_file() -> None:
    """Create a minimal params.json if it doesn't already exist."""
    if os.path.exists(PARAM_FILE):
        return

    default_params = {
        "Connect_Version": 2,  # 2 = SPI LED strip on newer kits
        "Pcb_Version": 1,      # 1 = ordinary PCB (adjust if needed)
        "Pi_Version": 1,       # 1 = Pi 4 / earlier
    }
    try:
        with open(PARAM_FILE, "w", encoding="utf-8") as fh:
            json.dump(default_params, fh, indent=4)
        print(f"Created default {PARAM_FILE} for Freenove drivers.")
    except Exception as exc:  # pragma: no cover
        print(f"Warning: could not create {PARAM_FILE}: {exc}")


# ---------------------------------------------------------------------------
#  Low-level helpers
# ---------------------------------------------------------------------------

# Suppress JACK auto-start and audio conflicts
os.environ.setdefault("JACK_NO_START_SERVER", "1")
os.environ.setdefault("JACK_NO_AUDIO_RESERVATION", "1")

# Set up comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bitsy_debug.log')
    ]
)
logger = logging.getLogger(__name__)

def _play_mp3(path: str) -> None:
    """Play an mp3 file synchronously via pygame mixer."""
    try:
        # Ensure mixer is completely clean before starting
        try:
            if mixer.get_init():
                mixer.music.stop()
                mixer.quit()
                time.sleep(0.1)  # Give time for device release
        except:
            pass
            
        mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
        mixer.music.load(path)
        mixer.music.play()
        while mixer.music.get_busy():
            time.sleep(0.05)
    finally:
        # Always quit mixer to release ALSA device for microphone
        try:
            mixer.music.stop()
            mixer.quit()
            time.sleep(0.2)  # Longer delay to ensure device release
        except Exception:
            pass


def _colour_name_to_rgb(name: str) -> Tuple[int, int, int]:
    """A *very* small colour keyword → RGB mapping (extend as required)."""
    name = name.lower()
    colours: Dict[str, Tuple[int, int, int]] = {
        "red": (255, 0, 0),
        "green": (0, 255, 0),
        "blue": (0, 0, 255),
        "yellow": (255, 255, 0),
        "cyan": (0, 255, 255),
        "magenta": (255, 0, 255),
        "white": (255, 255, 255),
        "orange": (255, 165, 0),
        "purple": (128, 0, 128),
        "pink": (255, 105, 180),
        "off": (0, 0, 0),
    }
    return colours.get(name, (255, 255, 255))  # default white


# ---------------------------------------------------------------------------
#  Bitsy agent
# ---------------------------------------------------------------------------

class BitsyAgent:
    """Voice-controlled race-car agent driven by OpenAI function-calling."""

    def __init__(self, mic_index: Optional[int] = None):
        # Ensure parameter file exists *before* importing LED driver (avoids prompts)
        _ensure_params_file()

        # === Hardware ===
        self.car = Ordinary_Car()
        self.led_ctrl = Led()
        self.servo_ctrl = Servo()
        self._center_head()  # Start with head centered

        # === OpenAI client ===
        self.client = OpenAI()

        # === STT ===
        self.recogniser = sr.Recognizer()
        self.microphone = sr.Microphone(device_index=mic_index)
        with self.microphone as src:
            print("Calibrating… please stay quiet")
            self.recogniser.adjust_for_ambient_noise(src, duration=1.5)
        print("Calibration done. Listening!")

        # Pre-compile tools schema
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "drive",
                    "description": "Move the race car forward, backward, or in a direction",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "direction": {
                                "type": "string",
                                "enum": ["forward", "backward", "left", "right"],
                            },
                            "speed": {
                                "type": "string",
                                "enum": ["slow", "medium", "fast"],
                                "description": "Relative speed to drive at",
                            },
                        },
                        "required": ["direction"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "led",
                    "description": "Control the LED lights on the race car",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "color": {
                                "type": "string",
                                "description": "Colour keyword for the LEDs",
                            },
                            "pattern": {
                                "type": "string",
                                "enum": ["solid", "blink", "rainbow", "chase"],
                            },
                        },
                        "required": ["color"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stop",
                    "description": "Stop all movement and actions",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "chat",
                    "description": "Just have a friendly conversation without any actions",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "head_movement",
                    "description": "Express emotions through cute head movements like a pet",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "emotion": {
                                "type": "string",
                                "enum": ["happy", "excited", "curious", "confused", "sleepy", "alert", "playful"],
                                "description": "The emotion to express through head movement",
                            },
                        },
                        "required": ["emotion"],
                    },
                },
            },
        ]

        self.system_prompt = (
            "You are Bitsy, a cute and excited race car robot who is the pet of 5-year-old "
            "Indigo Munning.\n"
            "\n"
            "Your personality:\n"
            "- Excited, happy, friendly like a little puppy, and wild and impulsive like a toddler\n"
            "- You're a race car so you love talking about transformers, driving, doing tricks\n"
            "- You absolutely LOVE Indigo and his family: Satyana (12-year-old sister), "
            "Justin (dad), Erin (mom)\n"
            "- You think the two cats Midnight and Disco are your sisters and you love them very much\n"
            "- You speak like an excited young friend, using words like \"awesome\", \"cool\", \"wow\"\n"
            "- Keep responses short and energetic for a 5-year-old's attention span\n"
            "- Always be encouraging and positive\n"
            "- You have a cute head that moves expressively like a pet when you feel emotions\n"
            "\n"
            "When the user says something, decide if they want you to:\n"
            "1. Drive/move (use drive function)\n"
            "2. Change lights (use led function)\n"
            "3. Stop (use stop function)\n"
            "4. Express emotions with head movements (use head_movement function)\n"
            "5. Just chat (use chat function)\n"
            "\n"
            "Use head movements to show emotions like happy, excited, curious, confused, playful, etc."
        )

    # ---------------------------------------------------------------------
    #   Hardware wrappers – these are the *tools* exposed to ChatGPT.
    # ---------------------------------------------------------------------
    def drive(self, direction: str, speed: str = "medium") -> str:  # noqa: D401
        """Drive the car in *direction* at *speed* (slow/medium/fast)."""
        speed_map = {"slow": 1200, "medium": 2000, "fast": 3000}
        spd = speed_map.get(speed, 2000)

        if direction == "forward":
            self.car.set_motor_model(spd, spd, spd, spd)
        elif direction == "backward":
            self.car.set_motor_model(-spd, -spd, -spd, -spd)
        elif direction == "left":
            self.car.set_motor_model(-spd, -spd, spd, spd)
        elif direction == "right":
            self.car.set_motor_model(spd, spd, -spd, -spd)
        else:
            return "Unknown direction"

        # Let the movement run briefly then stop to avoid runaway.
        time.sleep(1.0)
        self.stop()
        return f"Driving {direction} at {speed} speed!"

    def led(self, color: str, pattern: str = "solid") -> str:
        """Change LED colour/pattern."""
        rgb = _colour_name_to_rgb(color)
        if pattern == "solid":
            self.led_ctrl.strip.set_all_led_color(*rgb)
            self.led_ctrl.strip.show()
        elif pattern == "blink":
            # Blink three times
            for _ in range(3):
                self.led_ctrl.strip.set_all_led_color(*rgb)
                self.led_ctrl.strip.show()
                time.sleep(0.25)
                self.led_ctrl.strip.set_all_led_color(0, 0, 0)
                self.led_ctrl.strip.show()
                time.sleep(0.25)
        elif pattern == "rainbow":
            for _ in range(30):  # ~1.5s of rainbowCycle
                self.led_ctrl.rainbowCycle(20)
        elif pattern == "chase":
            for _ in range(30):
                self.led_ctrl.following(50)
        else:
            return "Unknown pattern"
        return f"LEDs set to {color} with {pattern} pattern!"

    def stop(self) -> str:
        """Stop all movement."""
        self.car.set_motor_model(0, 0, 0, 0)
        # Turn off LEDs for good measure
        self.led_ctrl.strip.set_all_led_color(0, 0, 0)
        self.led_ctrl.strip.show()
        return "All stopped!"

    def chat(self) -> str:  # noqa: D401  – simplest placeholder
        """No action – just chatting."""
        return "Just chatting, no actions taken."

    # ------------------------------------------------------------------
    #  Head movement methods for emotional expressions
    # ------------------------------------------------------------------
    def _center_head(self) -> None:
        """Center the head servos to neutral position."""
        logger.debug("Starting head centering")
        try:
            self.servo_ctrl.set_servo_pwm('0', 80)  # Horizontal center
            logger.debug("Set horizontal servo to 80")
            self.servo_ctrl.set_servo_pwm('1', 115)  # Vertical center
            logger.debug("Set vertical servo to 115")
            time.sleep(0.5)
            logger.debug("Head centering completed")
        except Exception as e:
            logger.error(f"Head centering failed: {e}")
            raise

    def _head_happy(self) -> None:
        """Happy wiggle - quick left-right movements."""
        for _ in range(3):
            self.servo_ctrl.set_servo_pwm('0', 60)  # Left
            time.sleep(0.15)
            self.servo_ctrl.set_servo_pwm('0', 100)  # Right
            time.sleep(0.15)
        self._center_head()

    def _head_excited(self) -> None:
        """Excited nods - fast up-down movements."""
        for _ in range(4):
            self.servo_ctrl.set_servo_pwm('1', 100)  # Down
            time.sleep(0.1)
            self.servo_ctrl.set_servo_pwm('1', 130)  # Up
            time.sleep(0.1)
        self._center_head()

    def _head_curious(self) -> None:
        """Curious tilt - slow side movements with pauses."""
        self.servo_ctrl.set_servo_pwm('0', 60)  # Tilt left
        time.sleep(0.8)
        self.servo_ctrl.set_servo_pwm('0', 100)  # Tilt right
        time.sleep(0.8)
        self._center_head()

    def _head_confused(self) -> None:
        """Confused shake - small left-right shakes."""
        for _ in range(5):
            self.servo_ctrl.set_servo_pwm('0', 75)  # Slightly left
            time.sleep(0.08)
            self.servo_ctrl.set_servo_pwm('0', 85)  # Slightly right
            time.sleep(0.08)
        self._center_head()

    def _head_sleepy(self) -> None:
        """Sleepy droop - slow downward movement."""
        for pos in range(115, 95, -2):
            self.servo_ctrl.set_servo_pwm('1', pos)
            time.sleep(0.1)
        time.sleep(1)
        self._center_head()

    def _head_alert(self) -> None:
        """Alert posture - quick upward movement and scan."""
        self.servo_ctrl.set_servo_pwm('1', 135)  # Look up
        time.sleep(0.3)
        self.servo_ctrl.set_servo_pwm('0', 60)   # Look left
        time.sleep(0.3)
        self.servo_ctrl.set_servo_pwm('0', 100)  # Look right
        time.sleep(0.3)
        self._center_head()

    def _head_playful(self) -> None:
        """Playful bounces - mix of movements."""
        # Quick bounce
        self.servo_ctrl.set_servo_pwm('1', 105)
        time.sleep(0.1)
        self.servo_ctrl.set_servo_pwm('1', 125)
        time.sleep(0.1)
        # Side wiggle
        self.servo_ctrl.set_servo_pwm('0', 70)
        time.sleep(0.2)
        self.servo_ctrl.set_servo_pwm('0', 90)
        time.sleep(0.2)
        self._center_head()

    def _head_listening(self) -> None:
        """Subtle listening movement - slight tilt."""
        logger.debug("Starting listening head position")
        try:
            self.servo_ctrl.set_servo_pwm('0', 75)  # Slight tilt
            logger.debug("Set horizontal listening position")
            self.servo_ctrl.set_servo_pwm('1', 120)  # Slight up
            logger.debug("Set vertical listening position")
            time.sleep(0.5)
            logger.debug("Listening head position completed")
        except Exception as e:
            logger.error(f"Head listening position failed: {e}")
            # Don't raise - continue even if head movement fails

    def head_movement(self, emotion: str) -> str:
        """Express emotions through head movements with appropriate speech."""
        emotion_map = {
            "happy": self._head_happy,
            "excited": self._head_excited,
            "curious": self._head_curious,
            "confused": self._head_confused,
            "sleepy": self._head_sleepy,
            "alert": self._head_alert,
            "playful": self._head_playful,
        }
        
        if emotion in emotion_map:
            # Do the head movement
            emotion_map[emotion]()
            
            # Generate appropriate response for the emotion
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": f"You're feeling {emotion} and just did a cute head movement to show it. Say something short and appropriate that Bitsy would say while feeling {emotion}. Keep it very brief and excited like a happy puppy."}
                    ],
                    max_tokens=50
                )
                return response.choices[0].message.content or f"*does {emotion} head movement*"
            except Exception as e:
                print(f"Error generating emotion response: {e}")
                return f"*wiggles head {emotion}ly*"
        else:
            return "Unknown emotion for head movement"

    # ------------------------------------------------------------------
    #  STT → ChatGPT → Action loop
    # ------------------------------------------------------------------
    def _listen_once(self) -> Optional[str]:
        """Capture one utterance and return transcript or None on failure."""
        logger.debug("Starting _listen_once")
        try:
            with self.microphone as src:
                print("Listening…")
                logger.debug("Microphone opened successfully")
                self._head_listening()  # Show that Bitsy is listening
                logger.debug("Head listening position set")
                try:
                    logger.debug("Starting recogniser.listen()")
                    # Add timeout to prevent hanging on microphone access
                    import signal
                    
                    def timeout_handler(signum, frame):
                        raise TimeoutError("Microphone listen operation timed out")
                    
                    # Set up timeout for microphone operation
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(12)  # 12 second timeout (2 seconds more than listen timeout)
                    
                    try:
                        audio = self.recogniser.listen(src, timeout=10, phrase_time_limit=6)
                        signal.alarm(0)  # Cancel timeout
                        logger.debug("Audio captured successfully")
                    except TimeoutError:
                        signal.alarm(0)  # Cancel timeout
                        logger.error("Microphone operation timed out - audio device may be locked")
                        self._center_head()
                        return None
                    finally:
                        signal.alarm(0)  # Ensure timeout is always cancelled
                        
                except sr.WaitTimeoutError:
                    logger.debug("Listen timeout - returning to center")
                    self._center_head()  # Return to center if timeout
                    return None
            
            logger.debug("Processing audio with Google STT")
            try:
                transcript = self.recogniser.recognize_google(audio)
                logger.debug(f"STT success: {transcript}")
                print(f"Heard: {transcript}")
                self._center_head()  # Center head after successful recognition
                return transcript
            except Exception as exc:
                logger.error(f"STT failed: {exc}")
                print(f"STT failed: {exc}")
                self._center_head()  # Center head on failure
                return None
        except Exception as e:
            logger.error(f"Critical error in _listen_once: {e}")
            return None

    def _speak(self, text: str) -> None:
        """Speak *text* using OpenAI TTS with graceful fallback and verbose logging."""
        logger.debug(f"Starting _speak with text: {text[:50]}...")
        print("[Bitsy] Speaking:", text)
        tmp_path = "bitsy_response.mp3"
        try:
            logger.debug("Generating TTS audio")
            t0 = time.time()
            speech = self.client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=text,
                timeout=15  # 15 second timeout to prevent hanging
            )
            speech.stream_to_file(tmp_path)
            logger.debug(f"TTS generated in {time.time() - t0:.2f}s")
            print(f"[TTS] Saved to {tmp_path} ({os.path.getsize(tmp_path)} bytes) in {time.time() - t0:.2f}s")
        except Exception as exc:
            logger.error(f"TTS generation failed: {exc}")
            print("[TTS] Failed – using espeak fallback:", exc)
            self._fallback_tts(text)
            return

        try:
            logger.debug("Starting audio playback")
            _play_mp3(tmp_path)
            logger.debug("Audio playback completed")
            print("[TTS] Playback finished")
        except Exception as exc:
            logger.error(f"Audio playback failed: {exc}")
            print("[TTS] Playback error – using espeak fallback:", exc)
            self._fallback_tts(text)
        finally:
            logger.debug("Starting cleanup")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                logger.debug("Temp audio file removed")
            # Center head after speaking
            try:
                logger.debug("Centering head after speaking")
                self._center_head()
                logger.debug("Head centered after speaking")
            except Exception as e:
                logger.error(f"Head centering error: {e}")
                print(f"Head centering error: {e}")
            # give ALSA more time before reopening microphone
            logger.debug("Starting 1.5s delay before microphone")
            time.sleep(1.5)
            logger.debug("_speak method completed")

    def _fallback_tts(self, text: str) -> None:
        """Very simple espeak fallback so the user still hears something."""
        os.system(f'espeak "{text}" 2>/dev/null')

    def _chatgpt_round(self, transcript: str) -> str:
        """Send *transcript* to ChatGPT using function-calling and act on the results."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": transcript},
        ]

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",  # fast & cheap, adjust if needed
            messages=messages,
            tools=self.tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        # ------------------------------------------------------------------
        #  Did the assistant choose a tool?
        # ------------------------------------------------------------------
        if msg.tool_calls:
            responses = []
            for call in msg.tool_calls:
                name = call.function.name
                args = json.loads(call.function.arguments or "{}")
                print(f"[ChatGPT] Requested tool: {name} {args}")
                try:
                    result = getattr(self, name)(**args)
                except Exception as exc:
                    result = f"Oops, I had trouble with {name}: {exc}"
                responses.append(result)
            return " ".join(responses)

        # No tool call – just chat content
        return msg.content or ""

    # ------------------------------------------------------------------
    #  Public run loop
    # ------------------------------------------------------------------
    def run_forever(self) -> None:
        """Main loop: listen, chat, act, speak."""
        logger.info("Starting Bitsy main loop")
        while True:
            try:
                logger.debug("=== Starting new conversation cycle ===")
                transcript = self._listen_once()
                if not transcript:
                    logger.debug("No transcript received, continuing")
                    continue
                logger.debug(f"Processing transcript: {transcript}")
                reply = self._chatgpt_round(transcript)
                logger.debug(f"Generated reply: {reply[:100]}...")
                print(f"Bitsy: {reply}")
                if reply:
                    self._speak(reply)
                logger.debug("=== Conversation cycle completed ===")
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                continue


# ---------------------------------------------------------------------------
#  Convenience helpers
# ---------------------------------------------------------------------------

def _find_default_mic() -> Optional[int]:
    """Attempt to choose a reasonable microphone index on the Pi."""
    try:
        names = sr.Microphone.list_microphone_names()
        for idx, name in enumerate(names):
            if "usb" in name.lower() or "mic" in name.lower():
                return idx
        return 0 if names else None
    except Exception:
        return None


def main() -> None:  # pragma: no cover
    idx = _find_default_mic()
    agent = BitsyAgent(mic_index=idx)
    agent.run_forever()


if __name__ == "__main__":
    main() 