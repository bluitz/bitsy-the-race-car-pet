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
        self.last_chords = []  # Store last 5 chords
        self.max_chord_history = 5  # Number of chords to keep in history
        self.last_processed_progression = None  # Store the last processed progression

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
                chord, confidence = self.audio_processor.detect_chord(indata[:, 0])
                
                # Only consider chords with sufficient confidence
                if confidence > 0.7:  # Adjust threshold as needed
                    # If it's been a while since the last chord, reset the progression
                    if current_time - self.last_chord_time > self.chord_timeout:
                        self.current_progression = []
                        self.last_chords = []
                    
                    # Update last chord time
                    self.last_chord_time = current_time
                    
                    # Add chord to history if it's different from the last one
                    if not self.current_progression or self.current_progression[-1] != chord:
                        self.current_progression.append(chord)
                        self.last_chords.append(chord)
                        
                        # Keep only the last N chords
                        if len(self.last_chords) > self.max_chord_history:
                            self.last_chords = self.last_chords[-self.max_chord_history:]
                        
                        # Only process progression if we have at least 2 chords
                        if len(self.last_chords) >= 2:
                            # Only process if the progression has changed since last time
                            if tuple(self.last_chords) != self.last_processed_progression:
                                self.last_processed_progression = tuple(self.last_chords)
                                self._process_progression()
                        
                        # Always update the display when a new chord is detected
                        self._display_current_state()
                        
            except Exception as e:
                logger.error(f"Error processing audio: {e}")
    
    def _display_current_state(self):
        """Display the current state of chord detection and matches"""
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("Jerry in a Box - Chord Recognition")
        print("=" * 80)
        
        # Show current chord and last 5 chords
        print(f"Current chord: {self.current_progression[-1] if self.current_progression else 'None'}")
        print(f"Last {self.max_chord_history} chords: {' -> '.join(self.last_chords) if self.last_chords else 'None'}")
        print(f"Full progression: {' -> '.join(self.current_progression) if self.current_progression else 'None'}")
        print("\nListening for chords... (Press Ctrl+C to quit)\n")
        
        # Show recent matches if we have any
        if hasattr(self, 'last_matches') and self.last_matches:
            print("\nPossible Matches:")
            print("-" * 80)
            
            for i, (song, score, next_chords) in enumerate(self.last_matches[:5], 1):
                percentage = min(int(score * 100), 100)
                print(f"{i}. {song.title} - {song.artist} ({percentage}% match)")
                print(f"   Next likely chords: {' -> '.join(next_chords) if next_chords else 'End of progression'}")
                print(f"   Source: {song.source}")
                print("-" * 80)
    
    def _process_progression(self):
        """Process the current chord progression and find matching songs"""
        if not self.last_chords or len(self.last_chords) < 2:
            return
        
        # Use the last 5 chords for matching
        progression_to_match = self.last_chords
        
        # Find similar progressions in the database
        self.last_matches = self.song_db.find_similar_progressions(progression_to_match)
        
        # Update the display
        self._display_current_state()
    
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
