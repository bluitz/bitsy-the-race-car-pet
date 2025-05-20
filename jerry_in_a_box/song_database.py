import json
import os
from typing import List, Dict, Tuple
import re
from dataclasses import dataclass

@dataclass
class Song:
    title: str
    artist: str
    progression: List[str]
    all_chords: List[str] = None
    source: str = "Jerry Garcia Song Book"
    sections: Dict = None
    
    def __post_init__(self):
        if self.all_chords is None:
            self.all_chords = []
        if self.sections is None:
            self.sections = {}

class SongDatabase:
    def __init__(self):
        self.songs: Dict[str, Song] = {}
        self._load_songs()

    def _load_songs(self):
        """Load songs from a JSON file or initialize with sample data"""
        try:
            with open('jerry_in_a_box/data/songs.json', 'r') as f:
                songs_data = json.load(f)
                for song_data in songs_data:
                    self.songs[song_data['title'].lower()] = Song(**song_data)
        except FileNotFoundError:
            # Initialize with some sample data - in a real app, this would be populated from the PDF
            self._initialize_sample_songs()

    def _initialize_sample_songs(self):
        """Initialize with some sample Jerry Garcia songs"""
        sample_songs = [
            {
                "title": "Ripple",
                "artist": "Grateful Dead",
                "progression": ["G", "C", "G", "D", "G", "C", "G", "D", "C", "G", "D", "G"]
            },
            {
                "title": "Friend of the Devil",
                "artist": "Grateful Dead",
                "progression": ["Am", "C", "G", "D", "Am", "C", "G", "D", "F", "C", "G", "D"]
            },
            {
                "title": "Scarlet Begonias",
                "artist": "Grateful Dead",
                "progression": ["G", "C", "G", "D", "C", "G", "D", "G"]
            }
        ]
        
        for song_data in sample_songs:
            self.songs[song_data['title'].lower()] = Song(**song_data)
        
        # Save the sample data
        self._save_songs()

    def _save_songs(self):
        """Save songs to a JSON file"""
        os.makedirs('jerry_in_a_box/data', exist_ok=True)
        with open('jerry_in_a_box/data/songs.json', 'w') as f:
            songs_data = [
                {
                    'title': song.title,
                    'artist': song.artist,
                    'progression': song.progression,
                    'source': song.source
                }
                for song in self.songs.values()
            ]
            json.dump(songs_data, f, indent=2)

    def find_similar_progressions(self, current_progression: List[str], top_n: int = 5) -> List[Tuple[Song, float, List[str]]]:
        """
        Find songs with progressions similar to the current progression.
        Returns a list of tuples: (song, similarity_score, next_chords)
        """
        if not current_progression:
            return []
            
        results = []
        
        for song in self.songs.values():
            song_progression = song.progression
            
            # Try to find a matching segment in the song's progression
            best_match_length = 0
            best_match_index = -1
            
            # Look for the current progression in the song's progression
            for i in range(len(song_progression)):
                match_length = 0
                for j in range(min(len(current_progression), len(song_progression) - i)):
                    if song_progression[i + j].lower() == current_progression[j].lower():
                        match_length += 1
                    else:
                        break
                
                if match_length > best_match_length:
                    best_match_length = match_length
                    best_match_index = i
            
            if best_match_length > 0 and best_match_index + best_match_length < len(song_progression):
                # Calculate similarity score (0.0 to 1.0)
                similarity = best_match_length / len(current_progression)
                
                # Get the next few chords in the progression
                next_chord_index = best_match_index + best_match_length
                next_chords = song_progression[next_chord_index:next_chord_index + 5]
                
                results.append((song, similarity, next_chords))
        
        # Sort by similarity score (highest first) and return top N
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]

    def search_songs(self, query: str) -> List[Song]:
        """Search for songs by title or artist"""
        query = query.lower()
        return [
            song for song in self.songs.values()
            if query in song.title.lower() or query in song.artist.lower()
        ]

    def add_song(self, title: str, artist: str, progression: List[str], source: str = "Jerry Garcia Song Book"):
        """Add a new song to the database"""
        self.songs[title.lower()] = Song(title, artist, progression, source)
        self._save_songs()

    def parse_progression_from_text(self, text: str) -> List[str]:
        """Parse a chord progression from text with the format used in the song book"""
        # Remove any extra whitespace and split into tokens
        tokens = re.findall(r'[A-Ga-g][#b]?|[/%|]', text)
        
        progression = []
        i = 0
        
        while i < len(tokens):
            token = tokens[i]
            
            if token == '|':
                # Start of measure, skip for now
                i += 1
            elif token == '%':
                # Repeat the last chord in the progression
                if progression:
                    progression.append(progression[-1])
                i += 1
            elif token == '/':
                # Repeat the last chord
                if progression:
                    progression.append(progression[-1])
                i += 1
            else:
                # It's a chord
                progression.append(token.upper())
                i += 1
        
        return progression
