#!/usr/bin/env python3
"""
Parse the Jerry Garcia Song Book CSV file and load songs into the database.
"""
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

class SongCSVParser:
    def __init__(self):
        self.songs: Dict[str, Dict] = {}
        self.chord_pattern = re.compile(r'([A-G][#b]?(?:m|maj|min|sus|dim|aug)?\d*(?:\/[A-G][#b]?)?)')
    
    def parse_measure(self, measure: str, prev_chord: Optional[str] = None) -> List[str]:
        """Parse a measure and return a list of chords."""
        if not measure or measure.strip() == '%':
            return [prev_chord] if prev_chord else []
            
        # Split by spaces and filter out empty strings
        parts = [p.strip() for p in measure.split() if p.strip()]
        
        # Handle empty measure
        if not parts:
            return [prev_chord] if prev_chord else []
            
        chords = []
        for part in parts:
            if part == '/':
                # Repeat the last chord
                if chords:
                    chords.append(chords[-1])
                elif prev_chord:
                    chords.append(prev_chord)
            else:
                # Try to extract a chord
                chord_match = self.chord_pattern.match(part)
                if chord_match:
                    chord = chord_match.group(1)
                    chords.append(chord)
                
        return chords if chords else ([prev_chord] if prev_chord else [])
    
    def parse_progression(self, progression: str) -> List[str]:
        """Parse a chord progression string into a list of chords."""
        if not progression or not isinstance(progression, str):
            return []
            
        # Split into measures
        measures = [m.strip() for m in progression.split('|') if m.strip()]
        
        chords = []
        last_chord = None
        
        for measure in measures:
            measure_chords = self.parse_measure(measure, last_chord)
            if measure_chords:
                chords.extend(measure_chords)
                last_chord = measure_chords[-1]
        
        return chords
    
    def parse_csv(self, file_path: str) -> List[Dict]:
        """Parse the CSV file and return a list of songs."""
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            for row in reader:
                if len(row) < 3:
                    continue
                    
                title = row[0].strip()
                section = row[1].strip()
                progression = row[2].strip()
                
                # Skip header row if exists
                if title.lower() == 'title' and section.lower() == 'section':
                    continue
                
                # Create song if it doesn't exist
                if title not in self.songs:
                    self.songs[title] = {
                        'title': title,
                        'artist': 'Jerry Garcia / Grateful Dead',
                        'sections': {},
                        'all_chords': set(),
                        'progression': [],
                        'source': 'Jerry Garcia Song Book'
                    }
                
                # Parse the progression
                chords = self.parse_progression(progression)
                
                # Add to sections
                self.songs[title]['sections'][section] = {
                    'progression': progression,
                    'chords': chords
                }
                
                # Update all chords
                self.songs[title]['all_chords'].update(chords)
                
                # Set main progression if empty (use first section with chords)
                if not self.songs[title]['progression'] and chords:
                    self.songs[title]['progression'] = chords[:8]  # First 8 chords as main progression
        
        # Convert sets to lists for JSON serialization
        for song in self.songs.values():
            song['all_chords'] = list(song['all_chords'])
            
        return list(self.songs.values())

def save_to_json(songs: List[Dict], output_file: str):
    """Save songs to a JSON file."""
    # Create output directory if it doesn't exist
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to list of dicts
    songs_list = []
    for song in songs:
        song_data = {
            'title': song['title'],
            'artist': song['artist'],
            'progression': song['progression'],
            'all_chords': song['all_chords'],
            'source': song['source'],
            'sections': song['sections']
        }
        songs_list.append(song_data)
    
    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(songs_list, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(songs_list)} songs to {output_file}")
    return songs_list

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Parse Jerry Garcia Song Book CSV')
    parser.add_argument('--input', type=str, default='sources/jerry_song_book.csv',
                       help='Path to the CSV file')
    parser.add_argument('--output', type=str, default='jerry_in_a_box/data/songs.json',
                       help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Parse the CSV
    parser = SongCSVParser()
    songs = parser.parse_csv(args.input)
    
    if not songs:
        print("No songs were parsed from the CSV.")
        return
    
    # Save to JSON
    saved_songs = save_to_json(songs, args.output)
    
    # Print a summary
    print(f"\nSuccessfully parsed {len(saved_songs)} songs:")
    for i, song in enumerate(saved_songs[:10], 1):  # Show first 10 songs as a sample
        print(f"{i}. {song['title']} ({len(song.get('all_chords', []))} unique chords)")
    
    if len(saved_songs) > 10:
        print(f"... and {len(saved_songs) - 10} more")

if __name__ == "__main__":
    main()
