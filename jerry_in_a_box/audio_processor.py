import numpy as np
import sounddevice as sd
import time
from .yin_pitch import YINPitchDetector

class AudioProcessor:
    def __init__(self, sample_rate=44100, chunk_size=2048, threshold=0.1):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.threshold = threshold
        self.stream = None
        self.last_chord = None
        self.last_chord_time = 0
        self.last_note = None
        self.note_start_time = 0
        self.min_note_duration = 0.3  # Minimum duration to register a note (seconds)
        self.yin_detector = YINPitchDetector(sample_rate=sample_rate, buffer_size=chunk_size, threshold=threshold)

    def start_stream(self, callback):
        """Start the audio stream with the given callback"""
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            blocksize=self.chunk_size,
            callback=callback
        )
        self.stream.start()

    def stop_stream(self):
        """Stop the audio stream"""
        if self.stream:
            self.stream.stop()
            self.stream.close()

    @staticmethod
    def freq_to_note(freq):
        """Convert frequency to nearest note with better accuracy."""
        if freq <= 0:
            return None
            
        # Notes in one octave
        notes = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']
        
        # Calculate the note number from frequency (A4 = 440Hz = note 69)
        note_num = 12 * (np.log2(freq / 440.0)) + 69
        note_num_rounded = int(round(note_num))
        
        # Calculate cents offset from the nearest note
        cents = 100 * (note_num - note_num_rounded)
        
        # Only return a note if it's within ±30 cents of the nearest note
        if abs(cents) > 30:
            return None
            
        # Calculate octave and note name
        octave = (note_num_rounded // 12) - 1
        note_name = notes[note_num_rounded % 12]
        
        return f"{note_name}"
    
    def freq_to_note(self, freq):
        """Convert frequency to nearest note with a 3 half-step correction."""
        if freq <= 0:
            return None
            
        # Notes in one octave
        notes = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']
        
        # Calculate the note number from frequency (A4 = 440Hz = note 69)
        note_num = 12 * (np.log2(freq / 440.0)) + 69
        
        # Apply 3 half-step correction (add 3 to shift up)
        note_num += 3
        
        note_num_rounded = int(round(note_num))
        
        # Calculate cents offset from the nearest note
        cents = 100 * (note_num - note_num_rounded)
        
        # Only return a note if it's within ±40 cents of the nearest note
        if abs(cents) > 40:
            return None
            
        # Calculate octave and note name
        octave = (note_num_rounded // 12) - 1
        note_name = notes[note_num_rounded % 12]
        
        # Only return notes that are in the shifted guitar range (G2 to G6)
        if octave < 2 or (octave == 2 and note_name in ['G', 'G#', 'A', 'A#', 'B']):
            return note_name
        elif 3 <= octave <= 5:
            return note_name
        elif octave == 6 and note_name in ['G', 'G#', 'A']:
            return note_name
            
        return None
    
    def detect_chord(self, audio_data, sample_rate=44100):
        """
        Analyze audio data to detect the most likely note being played.
        Returns the detected note and confidence level.
        """
        current_time = time.time()
        
        # Detect pitch using YIN algorithm
        pitch, confidence = self.yin_detector.get_pitch(audio_data)
        
        # Only process if we have a good confidence
        if confidence < 0.7 or pitch < 80 or pitch > 1000:  # Guitar range
            return "Unknown", 0.0
        
        # Convert frequency to note
        note = self.freq_to_note(pitch)
        
        if note:
            # Check if this is a new note or the same note held
            if note != self.last_note:
                # Only register the note if it's held for a minimum duration
                if current_time - self.note_start_time >= self.min_note_duration:
                    self.last_note = note
                    self.last_chord = note
                    self.last_chord_time = current_time
                    self.note_start_time = current_time
                    return note, min(confidence, 0.95)
                else:
                    # Reset the timer if the note changed too quickly
                    self.note_start_time = current_time
                    return "Unknown", 0.0
            else:
                # Same note, just update the time
                return note, min(confidence, 0.95)
        
        return "Unknown", 0.0

    @staticmethod
    def record_audio(duration=3, sample_rate=44100):
        """Record audio for a specified duration"""
        print(f"Recording for {duration} seconds...")
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype='float32'
        )
        sd.wait()  # Wait until recording is finished
        return recording.flatten()
