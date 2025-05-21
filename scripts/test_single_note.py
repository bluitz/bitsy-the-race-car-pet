#!/usr/bin/env python3
"""
Test script for single note detection.
"""
import sys
import time
import numpy as np
import sounddevice as sd
from pathlib import Path
from unittest.mock import MagicMock

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

# Mock the OpenAI client before importing JerryInABox
import openai
openai.OpenAI = MagicMock()

from jerry_in_a_box.audio_processor import AudioProcessor

class SingleNoteTest:
    def __init__(self):
        self.sample_rate = 44100
        self.duration = 1.0  # seconds
        self.audio_processor = AudioProcessor(sample_rate=self.sample_rate)
        self.test_cases = [
            (196.00, 'G'),  # G3
            (261.63, 'C'),  # C4
            (329.63, 'E'),  # E4
            (392.00, 'G'),  # G4
            (523.25, 'C')   # C5
        ]
    
    def generate_sine_wave(self, freq, duration=None, volume=0.5):
        """Generate a simple sine wave."""
        if duration is None:
            duration = self.duration
        t = np.linspace(0, duration, int(self.sample_rate * duration), False)
        return volume * np.sin(2 * np.pi * freq * t)
    
    def test_single_note(self, freq, expected_note):
        """Test detection of a single note."""
        print(f"\nTesting note: {expected_note} ({freq:.2f} Hz)")
        
        # Generate the sine wave
        audio_data = self.generate_sine_wave(freq)
        
        # Process in chunks to simulate real-time
        chunk_size = 2048
        num_chunks = len(audio_data) // chunk_size
        
        detected_notes = set()
        
        for i in range(num_chunks):
            start = i * chunk_size
            end = start + chunk_size
            chunk = audio_data[start:end]
            
            # Convert to stereo for the audio processor
            chunk_stereo = np.column_stack((chunk, chunk))
            
            # Process the chunk
            note, confidence = self.audio_processor.detect_chord(chunk_stereo)
            
            if note != "Unknown" and confidence > 0.7:
                detected_notes.add(note)
            
            # Small delay to simulate real-time
            time.sleep(chunk_size / self.sample_rate)
        
        # Print results
        print(f"Expected: {expected_note}")
        print(f"Detected: {', '.join(detected_notes) if detected_notes else 'None'}")
        
        # Check if the expected note was detected
        success = expected_note in detected_notes
        print(f"Result: {'✅ PASS' if success else '❌ FAIL'}")
        
        return success
    
    def run_tests(self):
        """Run all test cases."""
        print("Starting single note detection tests...")
        print("=" * 50)
        
        total_tests = len(self.test_cases)
        passed_tests = 0
        
        for freq, expected_note in self.test_cases:
            if self.test_single_note(freq, expected_note):
                passed_tests += 1
        
        # Print summary
        print("\n" + "=" * 50)
        print(f"Test Summary: {passed_tests}/{total_tests} tests passed")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        return passed_tests == total_tests

def main():
    test = SingleNoteTest()
    success = test.run_tests()
    
    if not success:
        print("\nSome tests failed. Would you like to debug?")
        print("1. Run a specific test with debug output")
        print("2. Modify audio processor settings")
        print("3. Exit")
        
        choice = input("Enter your choice (1-3): ")
        
        if choice == '1':
            print("\nAvailable test cases:")
            for i, (freq, note) in enumerate(test.test_cases, 1):
                print(f"{i}. {note} ({freq:.2f} Hz)")
            
            test_idx = int(input("Enter test number: ")) - 1
            if 0 <= test_idx < len(test.test_cases):
                freq, note = test.test_cases[test_idx]
                test.test_single_note(freq, note)
        
        elif choice == '2':
            print("\nCurrent settings:")
            print(f"Sample rate: {test.sample_rate} Hz")
            print(f"Chunk size: {test.audio_processor.chunk_size} samples")
            print(f"Threshold: {test.audio_processor.threshold}")
            
            # Here you could add code to modify settings
            print("\nModify settings in the code and run the test again.")
    
    print("\nTest completed.")

if __name__ == "__main__":
    main()
