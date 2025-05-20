import numpy as np
import librosa
import sounddevice as sd
from scipy.signal import find_peaks
import numpy.fft as fft

class AudioProcessor:
    def __init__(self, sample_rate=44100, chunk_size=2048, threshold=0.05):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.threshold = threshold
        self.stream = None
        self.last_chord = None
        self.chord_change_threshold = 0.5  # Seconds before changing chord
        self.last_chord_time = 0

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
    
    def detect_chord(self, audio_data, sample_rate=44100):
        """
        Analyze audio data to detect the most likely chord being played.
        Returns the detected chord and confidence level.
        """
        import time
        from scipy.signal import spectrogram
        
        current_time = time.time()
        
        # Skip processing if we recently detected a chord
        if current_time - self.last_chord_time < self.chord_change_threshold and self.last_chord:
            return self.last_chord, 0.9
        
        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)
        
        # Apply pre-emphasis to boost high frequencies
        pre_emphasis = 0.97
        y = np.append(audio_data[0], audio_data[1:] - pre_emphasis * audio_data[:-1])
        
        # Apply windowing
        window = np.hanning(len(y))
        y = y * window
        
        # Compute FFT
        fft_result = np.abs(fft.fft(y))
        freqs = fft.fftfreq(len(fft_result), 1.0/sample_rate)
        
        # Keep only positive frequencies
        positive_freq_idx = (freqs > 80) & (freqs < 1000)  # Guitar range
        freqs = freqs[positive_freq_idx]
        fft_result = fft_result[positive_freq_idx]
        
        # Find peaks in the frequency spectrum
        peaks, properties = find_peaks(fft_result, 
                                    height=np.max(fft_result)*0.2,  # Higher threshold
                                    distance=10,  # Closer peaks
                                    prominence=0.2,  # More prominent peaks
                                    width=2)  # Minimum width of peaks
        
        if len(peaks) == 0:
            return "Unknown", 0.0
        
        # Get the frequencies and magnitudes of the peaks
        peak_freqs = freqs[peaks]
        peak_mags = fft_result[peaks]
        
        # Sort peaks by magnitude (loudest first)
        sorted_idx = np.argsort(peak_mags)[::-1]
        peak_freqs = peak_freqs[sorted_idx]
        peak_mags = peak_mags[sorted_idx]
        
        # Get the fundamental frequency (loudest peak)
        fundamental_freq = peak_freqs[0]
        
        # Convert to note
        note = self.freq_to_note(fundamental_freq)
        
        if note:
            # Only update if we have a new chord
            if not self.last_chord or self.last_chord != note:
                self.last_chord = note
                self.last_chord_time = current_time
                return note, 0.95  # Higher confidence
            return self.last_chord, 0.9
        
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
