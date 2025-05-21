#!/usr/bin/env python3
"""
Test script to verify Deep Elem Blues chord detection.
This version includes realistic audio generation for testing chord detection.
"""
import sys
import os
import time
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock
from scipy import signal

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

# Mock the OpenAI client before importing JerryInABox
import openai
openai.OpenAI = MagicMock()

from jerry_in_a_box.main import JerryInABox
from jerry_in_a_box.audio_processor import AudioProcessor

class AudioGenerator:
    """Helper class to generate realistic audio signals for testing."""
    
    def __init__(self, sample_rate=44100, duration=0.5):
        self.sample_rate = sample_rate
        self.duration = duration
        self.t = np.linspace(0, duration, int(sample_rate * duration), False)
        
        # Guitar string harmonics (relative amplitudes)
        self.harmonics = [
            (1.0, 1.00),   # Fundamental
            (2.0, 0.50),   # 1st octave
            (3.0, 0.25),   # Perfect fifth + octave
            (4.0, 0.15),   # 2nd octave
            (5.0, 0.10),   # Major third + 2 octaves
            (6.0, 0.05)    # Perfect fifth + 2 octaves
        ]
    
    def generate_note(self, freq, volume=0.5):
        """Generate a guitar-like note with harmonics."""
        note = np.zeros_like(self.t)
        
        # Add harmonics
        for h_freq, h_amp in self.harmonics:
            note += (volume * h_amp * np.sin(2 * np.pi * freq * h_freq * self.t))
        
        # Apply a simple guitar-like ADSR envelope
        envelope = self._get_guitar_envelope()
        note = note * envelope
        
        # Add some noise to simulate string noise
        noise = np.random.normal(0, 0.01, len(note))
        return note + noise
    
    def generate_chord(self, root_note, chord_type='maj', volume=0.5):
        """Generate a chord with multiple notes."""
        # Define chord intervals (in semitones)
        if chord_type == 'maj':
            intervals = [0, 4, 7]  # Root, major third, perfect fifth
        elif chord_type == '7':
            intervals = [0, 4, 7, 10]  # Dominant 7th
        else:  # Default to major
            intervals = [0, 4, 7]
            
        # Generate notes for the chord
        chord = np.zeros_like(self.t)
        for interval in intervals:
            note_freq = root_note * (2 ** (interval/12))
            chord += self.generate_note(note_freq, volume=volume/len(intervals))
            
        return chord
    
    def _get_guitar_envelope(self):
        """Generate a simple ADSR envelope for guitar sound."""
        n = len(self.t)
        envelope = np.ones(n)
        
        # Attack (5% of duration)
        attack = int(0.05 * n)
        if attack > 0:
            envelope[:attack] = np.linspace(0, 1, attack)
        
        # Decay (15% of duration)
        decay = int(0.15 * n)
        if decay > 0:
            envelope[attack:attack+decay] = np.linspace(1, 0.7, decay)
        
        # Sustain (50% of duration)
        sustain_end = int(0.65 * n)
        if sustain_end > attack + decay:
            envelope[attack+decay:sustain_end] = 0.7
        
        # Release (35% of duration)
        release = n - sustain_end
        if release > 0:
            envelope[sustain_end:] = np.linspace(0.7, 0, release)
        
        return envelope

class TestDeepElemDetection:
    def __init__(self):
        self.app = JerryInABox()
        self.expected_progression = [
            'G', 'G', 'G', 'G',  # 4 bars of G
            'C', 'C', 'G', 'G',  # 2 bars C, 2 bars G
            'D7', 'C', 'G', 'D7'  # Turnaround
        ]
        self.audio_gen = AudioGenerator(duration=0.5)  # 500ms per chord
        
        # Define the actual frequencies for our chords
        self.chord_frequencies = {
            'G': (196.00, 'maj'),   # G3 (root of G major)
            'C': (261.63, 'maj'),   # C4 (root of C major)
            'D7': (293.66, '7')     # D4 (root of D7)
        }
    
    def simulate_audio_input(self, chords, duration=0.5):
        """Simulate audio input with realistic chord sounds and detect chords."""
        import sounddevice as sd
        
        for chord_name in chords:
            if chord_name not in self.chord_frequencies:
                print(f"Warning: Unknown chord {chord_name}, skipping...")
                continue
                
            # Get the root frequency and chord type
            root_freq, chord_type = self.chord_frequencies[chord_name]
            
            print(f"\nPlaying {chord_name} chord...")
            
            # Generate the chord audio
            audio_data = self.audio_gen.generate_chord(root_freq, chord_type)
            
            # Play the audio
            sd.play(audio_data, self.audio_gen.sample_rate)
            
            # Process the audio in chunks to simulate real-time processing
            chunk_size = 1024
            num_chunks = len(audio_data) // chunk_size
            
            for i in range(num_chunks):
                start = i * chunk_size
                end = start + chunk_size
                chunk = audio_data[start:end]
                
                # Convert to stereo for the callback
                chunk_stereo = np.column_stack((chunk, chunk))
                
                try:
                    # Process the audio chunk
                    self.app.audio_callback(
                        indata=chunk_stereo,
                        frames=len(chunk_stereo),
                        time_info=None,
                        status=None
                    )
                    
                    # Display detected chord if it's new
                    if hasattr(self.app.audio_processor, 'last_chord'):
                        current_chord = self.app.audio_processor.last_chord
                        if current_chord and (not hasattr(self, 'last_displayed_chord') or 
                                           current_chord != self.last_displayed_chord):
                            print(f"Detected: {current_chord}")
                            self.last_displayed_chord = current_chord
                    
                    # Small delay to simulate real-time
                    time.sleep(chunk_size / self.audio_gen.sample_rate)
                    
                except Exception as e:
                    print(f"Error in audio callback: {e}")
            
            # Wait for playback to finish
            sd.wait()
            time.sleep(0.2)  # Small pause between chords
    
    def run_test(self):
        print("Starting Deep Elem Blues detection test...")
        print("=" * 50)
        print("This test will generate and play realistic audio for each chord in the progression.")
        print("The audio will be processed by the audio callback to detect chords.")
        print("Make sure your speakers are on and volume is up!")
        
        # Initialize the app
        self.app.running = True
        
        # Print the expected progression
        print("\nExpected progression:")
        print("  " + " -> ".join(self.expected_progression))
        
        # Reset chord history
        if hasattr(self.app.audio_processor, 'chord_history'):
            self.app.audio_processor.chord_history = []
        
        # Give user a moment to read
        import time
        print("\nStarting in 2 seconds...")
        time.sleep(2)
        
        # Simulate the 12-bar blues progression with audio
        print("\nGenerating and processing audio...")
        self.simulate_audio_input(self.expected_progression)
        
        # Get the detected chords
        detected = []
        if hasattr(self.app, 'last_chords'):
            detected = self.app.last_chords[-len(self.expected_progression):]
        
        # Print the results
        print("\nTest Results:")
        print("-" * 50)
        print(f"Expected: {' -> '.join(self.expected_progression)}")
        print(f"Detected: {' -> '.join(detected) if detected else 'None'}")
        
        # Simple accuracy calculation
        if detected:
            correct = sum(1 for e, d in zip(self.expected_progression, detected) if e == d)
            accuracy = (correct / len(self.expected_progression)) * 100
            print(f"\nAccuracy: {accuracy:.1f}% ({correct}/{len(self.expected_progression)})")
        
        print("\n✅ Test completed.")
        print("Note: For better accuracy, ensure the audio processor")
        print("is properly configured for chord detection.")
        
        return True

def main():
    test = TestDeepElemDetection()
    test.run_test()

if __name__ == "__main__":
    main()
