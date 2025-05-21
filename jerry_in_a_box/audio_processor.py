import numpy as np
import sounddevice as sd
import time
from collections import Counter
from scipy.fft import fft, fftfreq
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
        
        # Chord detection settings
        self.chord_history = []
        self.max_history = 5  # Number of frames to consider for chord detection
        self.chord_confidence_threshold = 0.6  # Minimum confidence to accept a chord
        self.min_chord_duration = 0.2  # Minimum duration to register a chord change (seconds)
        
        # Define chord templates (intervals in semitones from root)
        self.chord_templates = {
            'maj': [0, 4, 7],      # Major: root, major third, perfect fifth
            'min': [0, 3, 7],      # Minor: root, minor third, perfect fifth
            '7': [0, 4, 7, 10],    # Dominant 7th: major triad + minor 7th
            'maj7': [0, 4, 7, 11], # Major 7th: major triad + major 7th
            'm7': [0, 3, 7, 10],   # Minor 7th: minor triad + minor 7th
            '5': [0, 7]             # Power chord: root and fifth
        }

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
    
    def detect_notes_in_chord(self, audio_data, sample_rate=44100, num_peaks=6):
        """
        Detect multiple notes in a chord using FFT.
        Returns a list of detected notes and their relative strengths.
        """
        # Convert stereo to mono if needed
        if len(audio_data.shape) > 1 and audio_data.shape[1] == 2:
            audio_data = np.mean(audio_data, axis=1)  # Convert to mono by averaging channels
            
        # Apply a window function to reduce spectral leakage
        window = np.hanning(len(audio_data))
        y = audio_data * window
        
        # Compute FFT
        yf = fft(y)
        xf = fftfreq(len(y), 1.0/sample_rate)
        
        # Get magnitude spectrum (only positive frequencies)
        half_n = len(y) // 2
        magnitudes = 2.0/len(y) * np.abs(yf[:half_n])
        frequencies = xf[:half_n]
        
        # Find peaks in the magnitude spectrum
        peaks = []
        for i in range(1, len(magnitudes)-1):
            if magnitudes[i] > magnitudes[i-1] and magnitudes[i] > magnitudes[i+1]:
                if 80 <= frequencies[i] <= 1000:  # Guitar range
                    peaks.append((frequencies[i], magnitudes[i]))
        
        # Sort peaks by magnitude and take the top ones
        peaks.sort(key=lambda x: x[1], reverse=True)
        top_peaks = peaks[:num_peaks]
        
        # Convert frequencies to notes
        notes = []
        for freq, mag in top_peaks:
            note = self.freq_to_note(freq)
            if note and note not in [n[0] for n in notes]:
                notes.append((note, mag))
        
        return notes
    
    def identify_chord(self, notes):
        """
        Identify the most likely chord from a set of notes.
        Returns the chord name and confidence level.
        """
        if not notes:
            return "Unknown", 0.0
            
        # Count occurrences of each note
        note_counter = Counter(notes)
        
        # Find the root note (most frequent note)
        root_note = note_counter.most_common(1)[0][0]
        
        # Calculate intervals from root
        note_order = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']
        root_idx = note_order.index(root_note)
        
        intervals = []
        for note in set(notes):  # Remove duplicates
            note_idx = note_order.index(note)
            interval = (note_idx - root_idx) % 12
            if interval > 0:  # Don't include root (0) in intervals
                intervals.append(interval)
        
        # Match intervals to chord templates
        best_match = None
        best_score = 0
        
        for chord_name, template in self.chord_templates.items():
            # Check if all template intervals are present
            score = sum(1 for i in template[1:] if i in intervals)  # Skip root (0)
            
            # Normalize score
            if len(template) > 1:  # Avoid division by zero
                score = score / (len(template) - 1)
                
                if score > best_score:
                    best_score = score
                    best_match = chord_name
        
        if best_score >= 0.5:  # Minimum threshold
            chord_name = f"{root_note}{best_match if best_match != 'maj' else ''}"
            return chord_name, min(best_score, 0.95)
        
        # If no good match, return just the root note
        return root_note, 0.6
    
    def detect_chord(self, audio_data, sample_rate=44100):
        """
        Analyze audio data to detect the most likely chord being played.
        Returns the detected chord and confidence level.
        """
        current_time = time.time()
        
        # Detect multiple notes in the chord
        notes = self.detect_notes_in_chord(audio_data, sample_rate)
        
        if not notes:
            return "Unknown", 0.0
        
        # Extract just the note names
        note_names = [note[0] for note in notes]
        
        # Identify the chord
        chord, confidence = self.identify_chord(note_names)
        
        # Update chord history
        self.chord_history.append((chord, current_time))
        
        # Only keep recent history
        self.chord_history = [h for h in self.chord_history 
                            if current_time - h[1] < self.min_chord_duration * self.max_history]
        
        # Get the most frequent chord in the history
        if self.chord_history:
            chord_counter = Counter([h[0] for h in self.chord_history])
            most_common = chord_counter.most_common(1)[0]
            
            # Only update if we have enough confidence
            if most_common[1] / len(self.chord_history) >= self.chord_confidence_threshold:
                chord = most_common[0]
                confidence = min(confidence * 1.2, 0.95)  # Slight boost for consistent detection
        
        # Only update if we have a good confidence or if it's a new chord
        if confidence >= self.chord_confidence_threshold or chord != self.last_chord:
            self.last_chord = chord
            self.last_chord_time = current_time
            
        return chord, confidence

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
