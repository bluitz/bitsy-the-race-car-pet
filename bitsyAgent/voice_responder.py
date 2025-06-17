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

These are already listed in requirements.txt except pyttsx3 – remember to
`pip install pyttsx3` or add it to your requirements file.
"""

from __future__ import annotations

import sys
import time
import subprocess
import logging
from typing import Optional, Tuple

import speech_recognition as sr

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

        # Calibrate for ambient noise once at start-up
        with self.microphone as source:
            logger.info("Calibrating microphone for ambient noise – please remain silent…")
            self.recogniser.adjust_for_ambient_noise(source, duration=1.5)
            logger.info("Calibration complete; energy threshold set to %s", self.recogniser.energy_threshold)

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------
    def run_forever(self) -> None:
        self.tts.say("Hello! I am listening.")
        logger.info("VoiceResponder started. Press Ctrl+C to exit.")
        try:
            while True:
                text, success = self._listen_once()
                response = self._build_response(text, heard=success)
                print(f"Assistant: {response}")
                self.tts.say(response)
                time.sleep(0.2)  # brief pause to avoid capturing our own speech
        except KeyboardInterrupt:
            logger.info("Shutting down at user request")
            self.tts.say("Goodbye!")

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
    def _build_response(self, transcript: str, heard: bool) -> str:
        if not heard or not transcript.strip():
            return "I didn't catch that. Please try again."

        tool = self._infer_tool(transcript)
        if tool == "unknown":
            return f"You said: '{transcript}'. I don't have a tool for that yet, but I'm learning!"
        else:
            return (
                f"You said: '{transcript}'. If the {tool} tool were ready, I would have used it now, "
                "but it's not implemented yet."
            )


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