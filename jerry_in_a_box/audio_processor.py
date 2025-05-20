import numpy as np
import librosa
import sounddevice as sd
from scipy.signal import find_peaks
import numpy.fft as fft

class AudioProcessor:
    def __init__(self, sample_rate=44100, chunk_size=1024, threshold=0.03):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.threshold = threshold
        self.stream = None

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
    def detect_chord(audio_data, sample_rate=44100):
        """
        Analyze audio data to detect the most likely chord being played.
        Returns the detected chord and confidence level.
        """
        # Simple FFT-based chord detection
        y = audio_data.astype(float)
        y = y - np.mean(y)  # Remove DC offset
        
        # Apply a window function
        window = np.hanning(len(y))
        y = y * window
        
        # Perform FFT
        fft_result = np.abs(fft.fft(y))
        freqs = fft.fftfreq(len(fft_result), 1.0/sample_rate)
        
        # Find peaks in the frequency spectrum
        peaks, _ = find_peaks(fft_result, height=np.max(fft_result)*0.1, distance=50)
        
        # Get the frequencies of the peaks
        peak_freqs = freqs[peaks]
        
        # Simple chord detection based on peak frequencies
        # This is a simplified version - a real implementation would be more sophisticated
        if len(peak_freqs) < 3:
            return "Unknown", 0.0
            
        # Convert frequencies to notes and try to identify the chord
        # This is a placeholder - actual implementation would analyze the intervals
        return "G", 0.85  # Placeholder return

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
