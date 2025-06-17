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
from typing import Dict, Tuple, Optional

import speech_recognition as sr
from pygame import mixer  # type: ignore
from openai import OpenAI

# ---------------------------------------------------------------------------
#  Hardware drivers (Freenove library)
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FREENOVE_PATH = os.path.join(
    PROJECT_ROOT, "Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi-master", "Code", "Server"
)
sys.path.append(FREENOVE_PATH)

try:
    from motor import Ordinary_Car  # pylint: disable=import-error
    from led import Led  # pylint: disable=import-error
except Exception as exc:  # pragma: no cover – hardware-dependent
    raise RuntimeError(
        "Could not import Freenove drivers. Ensure they are installed and the path is correct."
    ) from exc


# ---------------------------------------------------------------------------
#  Low-level helpers
# ---------------------------------------------------------------------------

def _play_mp3(path: str) -> None:
    """Play an mp3 file synchronously via pygame mixer."""
    mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
    mixer.music.load(path)
    mixer.music.play()
    while mixer.music.get_busy():
        time.sleep(0.05)


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
        # === Hardware ===
        self.car = Ordinary_Car()
        self.led_ctrl = Led()

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
            "\n"
            "When the user says something, decide if they want you to:\n"
            "1. Drive/move (use drive function)\n"
            "2. Change lights (use led function)\n"
            "3. Stop (use stop function)\n"
            "4. Just chat (use chat function)"
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
    #  STT → ChatGPT → Action loop
    # ------------------------------------------------------------------
    def _listen_once(self) -> Optional[str]:
        """Capture one utterance and return transcript or None on failure."""
        with self.microphone as src:
            print("Listening…")
            try:
                audio = self.recogniser.listen(src, timeout=10, phrase_time_limit=6)
            except sr.WaitTimeoutError:
                return None
        try:
            transcript = self.recogniser.recognize_google(audio)
            print(f"Heard: {transcript}")
            return transcript
        except Exception as exc:
            print(f"STT failed: {exc}")
            return None

    def _speak(self, text: str) -> None:
        """Use OpenAI TTS to speak *text* aloud."""
        t0 = time.time()
        response = self.client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text,
        )
        tmp_path = "bitsy_response.mp3"
        response.stream_to_file(tmp_path)
        print(f"[TTS] Synthesised in {time.time() - t0:.2f}s – playing…")
        _play_mp3(tmp_path)
        os.remove(tmp_path)

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
        while True:
            transcript = self._listen_once()
            if not transcript:
                continue
            reply = self._chatgpt_round(transcript)
            print(f"Bitsy: {reply}")
            if reply:
                self._speak(reply)


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