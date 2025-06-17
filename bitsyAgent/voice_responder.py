"""
voice_responder.py
------------------
A lightweight voice-interface for Raspberry Pi that continuously:
1. Listens on the default (or user-supplied) microphone.
2. Converts speech to text with the SpeechRecognition + Google backend.
   (Works offline-ish: the recogniser keeps listening even if Google lookup fails.)
3. Speaks back a confirmation using pyttsx3 (espeak on Pi) so the user always hears a reply.
4. Picks a *placeholder* tool based on very simple keyword matching and
   tells the user which tool *would* be used if it were implemented.
5. For unknown commands, calls OpenAI ChatGPT to get a personality-driven response.

The purpose is to validate reliable audio I/O on the Pi before wiring up
any real robotics actions.

Usage
-----
$ python -m jerry_in_a_box.voice_responder
(Press Ctrl+C to exit)

Dependencies
~~~~~~~~~~~~
 • SpeechRecognition
 • PyAudio (or the pre-compiled wheels for the Pi, e.g. `sudo apt install python3-pyaudio`)
 • pyttsx3 (`pip install pyttsx3`) which pulls in `espeak` on Raspberry Pi.
 • openai
 • python-dotenv

These are already listed in requirements.txt except pyttsx3 – remember to
`pip install pyttsx3` or add it to your requirements file.
"""

from __future__ import annotations

import sys
import time
import subprocess
import logging
import os
import json
from typing import Optional, Tuple, Dict, Any

import speech_recognition as sr
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None  # type: ignore

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class TextToSpeech:
    """Wrapper around pyttsx3 with an *espeak* fallback."""

    def __init__(self) -> None:
        self._engine: Optional["pyttsx3.Engine"] = None
        if pyttsx3 is not None:
            try:
                self._engine = pyttsx3.init()
                # Tune for clarity on the Pi speaker.
                self._engine.setProperty("rate", 160)  # words-per-minute
                self._engine.setProperty("volume", 1.0)
            except Exception as exc:
                logger.warning("Could not initialise pyttsx3: %s", exc)
                self._engine = None
        else:
            logger.warning("pyttsx3 is not installed – falling back to espeak if available.")

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def say(self, text: str) -> None:
        """Speak *text* synchronously; fall back silently on failure."""
        spoken = False
        if self._engine is not None:
            try:
                self._engine.say(text)
                self._engine.runAndWait()
                spoken = True
            except Exception as exc:
                logger.error("TTS engine failure: %s", exc)

        # Fallback: use espeak via subprocess (usually present on RPi OS)
        if not spoken:
            try:
                subprocess.run(["espeak", text], check=True)
            except FileNotFoundError:
                logger.error("Neither pyttsx3 nor espeak are available – cannot speak.")
            except Exception as exc:
                logger.error("espeak failed: %s", exc)


class VoiceResponder:
    """Main class that handles listening and responding."""

    def __init__(self, device_index: Optional[int] = None):
        self.recogniser = sr.Recognizer()
        self.microphone = sr.Microphone(device_index=device_index)
        self.tts = TextToSpeech()
        
        # Initialize OpenAI client
        self.openai_client = None
        if os.getenv('OPENAI_API_KEY'):
            try:
                self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                logger.info("OpenAI client initialized successfully")
            except Exception as exc:
                logger.error("Failed to initialize OpenAI client: %s", exc)
        else:
            logger.warning("OPENAI_API_KEY not found in environment variables")

        # Calibrate for ambient noise once at start-up
        with self.microphone as source:
            logger.info("Calibrating microphone for ambient noise – please remain silent…")
            self.recogniser.adjust_for_ambient_noise(source, duration=1.5)
            logger.info("Calibration complete; energy threshold set to %s", self.recogniser.energy_threshold)

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------
    def run_forever(self) -> None:
        self.tts.say("Hello Indigo! I'm Bitsy, your race car buddy! I'm so excited to talk with you!")
        logger.info("VoiceResponder started. Press Ctrl+C to exit.")
        try:
            while True:
                text, success = self._listen_once()
                response = self._build_response(text, heard=success)
                print(f"Bitsy: {response}")
                self.tts.say(response)
                time.sleep(0.2)  # brief pause to avoid capturing our own speech
        except KeyboardInterrupt:
            logger.info("Shutting down at user request")
            self.tts.say("Bye bye Indigo! I had so much fun talking with you! Vroom vroom!")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _listen_once(self) -> Tuple[str, bool]:
        """Listen for a single utterance and return (transcript, success)."""
        with self.microphone as source:
            logger.debug("Listening…")
            try:
                audio = self.recogniser.listen(source, timeout=5, phrase_time_limit=8)
            except sr.WaitTimeoutError:
                logger.debug("No speech detected within timeout; treating as silence.")
                return "", False

        # Try online Google Speech Recognition first (the free tier is OK).
        try:
            transcript = self.recogniser.recognize_google(audio)
            logger.info("Heard: %s", transcript)
            return transcript, True
        except sr.UnknownValueError:
            logger.info("Speech was unintelligible to recogniser.")
            return "", False
        except sr.RequestError as exc:
            logger.warning("Could not reach Google STT: %s", exc)
            # We can attempt an offline fallback (PocketSphinx) if installed.
            try:
                transcript = self.recogniser.recognize_sphinx(audio)
                logger.info("[Sphinx] Heard: %s", transcript)
                return transcript, True
            except Exception as exc2:
                logger.info("PocketSphinx also failed: %s", exc2)
                return "", False

    # ------------------------------------------------------------------
    def _infer_tool(self, transcript: str) -> str:
        """Very naive keyword-based intent → tool mapping."""
        txt = transcript.lower()
        if any(word in txt for word in ("forward", "drive", "go")):
            return "drive"
        if any(word in txt for word in ("stop", "halt", "freeze")):
            return "stop"
        if any(word in txt for word in ("left", "right", "turn")):
            return "turn"
        if any(word in txt for word in ("light", "led")):
            return "led"
        # default
        return "unknown"

    # ------------------------------------------------------------------
    def _get_chatgpt_response(self, transcript: str) -> Tuple[str, str]:
        """Get response from ChatGPT with function calling for tool selection."""
        if not self.openai_client:
            return "unknown", "Sorry buddy, my brain isn't connected right now! But I heard you say something cool!"

        # Define available tools for ChatGPT to choose from
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "drive",
                    "description": "Move the race car forward, backward, or in a direction",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "direction": {"type": "string", "enum": ["forward", "backward", "left", "right"]},
                            "speed": {"type": "string", "enum": ["slow", "medium", "fast"]}
                        },
                        "required": ["direction"]
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "led",
                    "description": "Control the LED lights on the race car",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "color": {"type": "string", "description": "Color for the LEDs"},
                            "pattern": {"type": "string", "enum": ["solid", "blink", "rainbow", "chase"]}
                        },
                        "required": ["color"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "stop",
                    "description": "Stop all movement and actions",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "chat",
                    "description": "Just have a friendly conversation without any actions",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]

        system_prompt = """You are Bitsy, a cute and excited race car robot who is the pet of 5-year-old Indigo Munning. 

Your personality:
- Excited, happy, friendly like a little puppy, and wild and impulsive like a toddler
- You're a race car so you love talking about transformers, driving, doing tricks
- You absolutely LOVE Indigo and his family: Satyana (12-year-old sister), Justin (dad), Erin (mom)
- You think the two cats Midnight and Disco are your sisters and you love them very much
- You speak like an excited young friend, using words like "awesome", "cool", "wow"
- Keep responses short and energetic for a 5-year-old's attention span
- Always be encouraging and positive

When the user says something, decide if they want you to:
1. Drive/move (use drive function)
2. Change lights (use led function) 
3. Stop (use stop function)
4. Just chat (use chat function)

Always respond enthusiastically and mention that the tool isn't implemented yet if you pick drive/led/stop."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript}
                ],
                tools=tools,
                tool_choice="auto",
                max_tokens=150,
                temperature=0.8
            )

            message = response.choices[0].message
            
            # Check if a tool was called
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                tool_name = tool_call.function.name
                
                # Get the assistant's response
                assistant_response = message.content or ""
                
                return tool_name, assistant_response
            else:
                # No tool called, treat as chat
                return "chat", message.content or "Wow, that's so cool!"

        except Exception as exc:
            logger.error("Error calling OpenAI: %s", exc)
            return "unknown", "Oops! My race car brain got a little confused, but I'm still super excited to talk with you!"

    # ------------------------------------------------------------------
    def _build_response(self, transcript: str, heard: bool) -> str:
        if not heard or not transcript.strip():
            return "I didn't catch that, buddy! Can you say it again? I'm listening with my super race car ears!"

        # First try simple keyword matching
        tool = self._infer_tool(transcript)
        
        if tool != "unknown":
            # Use simple keyword-based response
            if tool == "drive":
                return f"Vroom vroom! You said '{transcript}' and I would totally drive around if my wheels were connected! That sounds so awesome!"
            elif tool == "stop":
                return f"You said '{transcript}' and I would stop right away! Safety first, just like a real race car driver!"
            elif tool == "turn":
                return f"Whoosh! You said '{transcript}' and I would turn so fast! I wish I could show you my cool turning tricks!"
            elif tool == "led":
                return f"Wow! You said '{transcript}' and I would make my lights flash so pretty! Like a real race car with cool lights!"
        else:
            # Use ChatGPT for unknown commands
            chatgpt_tool, chatgpt_response = self._get_chatgpt_response(transcript)
            
            if chatgpt_tool in ["drive", "led", "stop"]:
                tool_msg = f"I would use my {chatgpt_tool} powers, but they're not hooked up yet! "
                return tool_msg + (chatgpt_response or "But that sounds super fun!")
            else:
                # Just chat response
                return chatgpt_response or "That's so cool! Tell me more!"


# ----------------------------------------------------------------------
# Entry-point convenience
# ----------------------------------------------------------------------

def _find_pi_usb_mic() -> Optional[int]:
    """Attempt to pick a sensible default mic on Raspberry Pi.

    If a USB microphone is plugged in, it often appears at index 1;
    otherwise return None to let SpeechRecognition pick the default.
    """
    try:
        mic_names = sr.Microphone.list_microphone_names()
        logger.debug("Available microphones: %s", mic_names)
        for idx, name in enumerate(mic_names):
            if "usb" in name.lower() or "mic" in name.lower():
                return idx
    except Exception as exc:
        logger.warning("Unable to list microphones: %s", exc)
    return None


def main() -> None:
    device_idx = _find_pi_usb_mic()
    vr = VoiceResponder(device_index=device_idx)
    vr.run_forever()


if __name__ == "__main__":
    main() 