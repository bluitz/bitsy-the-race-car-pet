import argparse
import time
import logging
from typing import List, Optional
from pathlib import Path
import sys

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

from jerry_in_a_box.audio_processor import AudioProcessor
from jerry_in_a_box.song_database import SongDatabase
from jerry_in_a_box.voice_commands import VoiceCommandProcessor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('jerry_in_a_box.log')
    ]
)
logger = logging.getLogger(__name__)

class JerryInABox:
    def __init__(self):
        self.audio_processor = AudioProcessor()
        self.song_db = SongDatabase()
        self.voice_processor = VoiceCommandProcessor(self.song_db)
        self.current_progression = []
        self.last_chord_time = 0
        self.chord_timeout = 5  # seconds of silence before resetting progression
        self.running = False

    def audio_callback(self, indata, frames, time_info, status):
        """Callback function for audio processing"""
        if status:
            logger.warning(f"Audio status: {status}")
        
        # Process the audio data to detect chords
        current_time = time.time()
        
        # Only process audio if we have enough data
        if len(indata) > 0:
            try:
                # Detect the chord from the audio
                chord, confidence = AudioProcessor.detect_chord(indata[:, 0])
                
                # Only consider chords with sufficient confidence
                if confidence > 0.7:  # Adjust threshold as needed
                    # If it's been a while since the last chord, reset the progression
                    if current_time - self.last_chord_time > self.chord_timeout:
                        self.current_progression = []
                    
                    # Add the chord to the current progression if it's different from the last one
                    if not self.current_progression or self.current_progression[-1] != chord:
                        self.current_progression.append(chord)
                        self.last_chord_time = current_time
                        self._process_progression()
            
            except Exception as e:
                logger.error(f"Error processing audio: {e}")

    def _process_progression(self):
        """Process the current chord progression and find matching songs"""
        if not self.current_progression:
            return
        
        print(f"\nCurrent progression: {' -> '.join(self.current_progression)}")
        
        # Find similar progressions in the database
        matches = self.song_db.find_similar_progressions(self.current_progression)
        
        if matches:
            print("\nPossible matches:")
            print("-" * 50)
            
            for i, (song, score, next_chords) in enumerate(matches, 1):
                # Calculate percentage match
                percentage = min(int(score * 100), 100)
                
                print(f"{i}. {song.title} - {song.artist} ({percentage}% match)")
                print(f"   Next likely chords: {' -> '.join(next_chords) if next_chords else 'End of progression'}")
                print(f"   Source: {song.source}")
                print("-" * 50)
        else:
            print("No matching progressions found in the database.")
    
    def start(self):
        """Start the application"""
        self.running = True
        
        try:
            # Start the voice command processor in a separate thread
            import threading
            voice_thread = threading.Thread(target=self.voice_processor.start_listening, daemon=True)
            voice_thread.start()
            
            print("Jerry in a Box - Chord Recognition System")
            print("=" * 50)
            print("Playing a song? I'll try to identify it!")
            print("Say 'find a song' to search for a song's chords")
            print("Press Ctrl+C to quit\n")
            
            # Start the audio processing
            self.audio_processor.start_stream(self.audio_callback)
            
            # Keep the main thread alive
            while self.running:
                try:
                    time.sleep(1)
                except KeyboardInterrupt:
                    print("\nShutting down...")
                    self.running = False
        
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            self.running = False
        
        finally:
            self.stop()
    
    def stop(self):
        """Stop the application"""
        self.running = False
        self.audio_processor.stop_stream()
        self.voice_processor.stop_listening()
        print("\nThanks for using Jerry in a Box!")

def main():
    parser = argparse.ArgumentParser(description='Jerry in a Box - Guitar Chord Recognition System')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        app = JerryInABox()
        app.start()
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
