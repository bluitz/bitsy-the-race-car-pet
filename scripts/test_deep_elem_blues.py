#!/usr/bin/env python3
"""
Test script to simulate the chord progression of Deep Elem Blues for testing.
Based on the Grateful Dead's version in the key of G.
"""
import numpy as np
import sounddevice as sd
import time

def generate_tone(freq, duration=1.0, sample_rate=44100, volume=0.3):
    """Generate a simple sine wave tone with harmonics to better simulate a guitar."""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # Add some harmonics to make it sound more like a guitar
    tone = (np.sin(2 * np.pi * freq * t) * 0.6 +
            np.sin(2 * np.pi * 2 * freq * t) * 0.3 +
            np.sin(2 * np.pi * 3 * freq * t) * 0.1) * volume
    return tone.astype(np.float32)

# Frequencies for the I, IV, and V chords in the key of G (Deep Elem Blues is in G)
CHORD_NOTES = {
    'G': [392.00, 493.88, 587.33],  # G, B, D (G major)
    'C': [523.25, 659.25, 783.99],  # C, E, G (C major)
    'D': [293.66, 369.99, 440.00],  # D, F#, A (D major - played lower for better sound)
    'G7': [392.00, 493.88, 587.33, 698.46],  # G, B, D, F (G7)
    'C7': [523.25, 659.25, 783.99, 622.25],  # C, E, G, Bb (C7)
    'D7': [293.66, 369.99, 440.00, 554.37]  # D, F#, A, C (D7)
}

def play_chord(chord_name, duration=2.0):
    """Play a chord for the specified duration."""
    if chord_name not in CHORD_NOTES:
        print(f"Unknown chord: {chord_name}")
        return
    
    print(f"Playing {chord_name} chord for {duration:.1f} seconds...")
    
    # Generate and mix the tones for each note in the chord
    mixed = np.zeros(int(44100 * duration), dtype=np.float32)
    for freq in CHORD_NOTES[chord_name]:
        tone = generate_tone(freq, duration)
        mixed = mixed + tone[:len(mixed)]
    
    # Normalize to prevent clipping
    if np.max(np.abs(mixed)) > 0:
        mixed = mixed / np.max(np.abs(mixed)) * 0.8
    
    sd.play(mixed, 44100)
    sd.wait()

def play_12_bar_blues():
    """Play a 12-bar blues progression in G."""
    # 12-bar blues progression for Deep Elem Blues
    progression = [
        ('G', 4), ('G', 4), ('G', 4), ('G', 4),  # 4 bars of G
        ('C', 4), ('C', 4), ('G', 4), ('G', 4),  # 2 bars C, 2 bars G
        ('D7', 2), ('C', 2), ('G', 2), ('D7', 2)  # Turnaround: D7, C, G, D7
    ]
    
    for chord, duration in progression:
        play_chord(chord, duration)
        time.sleep(0.2)  # Small pause between chords

def main():
    print("Deep Elem Blues - Chord Progression Test")
    print("=" * 50)
    print("This will play the chord progression for Deep Elem Blues.")
    print("Make sure your microphone is ready to capture these chords.")
    
    try:
        while True:
            print("\nPlaying Deep Elem Blues progression...")
            play_12_bar_blues()
            print("\nLooping... (Press Ctrl+C to stop)")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nTest finished.")

if __name__ == "__main__":
    main()
