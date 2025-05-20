#!/usr/bin/env python3
"""
Test script to play guitar chord tones for testing audio input.
"""
import numpy as np
import sounddevice as sd
import time

def generate_tone(freq, duration=2.0, sample_rate=44100):
    """Generate a simple sine wave tone."""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    tone = np.sin(2 * np.pi * freq * t) * 0.5
    return tone.astype(np.float32)

# Frequencies for D, A, G notes (in Hz)
NOTE_FREQUENCIES = {
    'D': 146.83,  # D3
    'A': 220.00,   # A3
    'G': 196.00    # G3
}

def play_chord_sequence(chords, chord_duration=2.0, pause_duration=1.0):
    """Play a sequence of chords with pauses in between."""
    for chord in chords:
        if chord in NOTE_FREQUENCIES:
            freq = NOTE_FREQUENCIES[chord]
            print(f"\nPlaying {chord} ({freq:.2f} Hz) for {chord_duration:.1f} seconds...")
            tone = generate_tone(freq, chord_duration)
            sd.play(tone, 44100)
            sd.wait()
            time.sleep(pause_duration)
        else:
            print(f"\nUnknown chord: {chord}")

if __name__ == "__main__":
    print("Guitar Chord Test")
    print("=" * 50)
    print("This will play D, A, G, D with 2 seconds each and 1 second pause.")
    print("Make sure your microphone is ready to capture these tones.")
    
    # Play the sequence: D, A, G, D
    sequence = ['D', 'A', 'G', 'D']
    
    try:
        while True:
            print("\nPlaying chord sequence...")
            play_chord_sequence(sequence)
            time.sleep(1)  # Pause between sequences
    except KeyboardInterrupt:
        print("\nTest finished.")
