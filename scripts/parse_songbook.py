#!/usr/bin/env python3
"""
Script to parse the Jerry Garcia Song Book PDF and extract song information.
"""
import os
import re
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import pdfplumber
from tqdm import tqdm

# Regular expressions for parsing song information
SONG_TITLE_PATTERN = re.compile(r'^\s*([A-Z][A-Za-z0-9\s\'"\-\(\)\&\,\.\!\?]+?)\s*$')
CHORD_PATTERN = re.compile(r'([A-G][#b]?[0-9]*(?:sus|maj|min|m|add|dim|aug)?[0-9]*(?:\/[A-G][#b]?)?)')
MEASURE_PATTERN = re.compile(r'\|([^|]*)\|')
REPEAT_PATTERN = re.compile(r'%')

class SongParser:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.songs = []
        self.current_song = None
        self.current_section = None
        self.current_lyrics = []
        self.current_chords = []
        
    def parse(self) -> List[Dict]:
        """Parse the PDF and extract song information."""
        print(f"Parsing {self.pdf_path}...")
        
        with pdfplumber.open(self.pdf_path) as pdf:
            for i, page in enumerate(tqdm(pdf.pages, desc="Processing pages")):
                text = page.extract_text()
                if not text:
                    continue
                    
                # Process each line of the page
                for line in text.split('\n'):
                    self._process_line(line.strip())
        
        # Add the last song if it exists
        if self.current_song:
            self._finalize_song()
            
        return self.songs
    
    def _process_line(self, line: str):
        """Process a single line of text from the PDF."""
        # Skip empty lines and page numbers
        if not line or line.isdigit():
            return
            
        # Check if this is a song title (all caps or title case)
        if (line.isupper() or (line[0].isupper() and not line.isupper())) and len(line) > 2:
            # If we were processing a song, finalize it first
            if self.current_song:
                self._finalize_song()
                
            # Start a new song
            self.current_song = {
                'title': line.strip(),
                'artist': 'Jerry Garcia / Grateful Dead',
                'sections': [],
                'chords': set(),
                'source': 'Jerry Garcia Song Book v9'
            }
            self.current_section = None
            self.current_lyrics = []
            self.current_chords = []
            return
            
        # If we're not in a song, skip
        if not self.current_song:
            return
            
        # Check for section headers (e.g., "Intro", "Verse 1", "Chorus")
        if (line.istitle() or line.isupper()) and len(line) < 30 and ' ' in line:
            self._finalize_section()
            self.current_section = line.strip()
            return
            
        # Process chord and lyric lines
        if '|' in line:  # This line contains chords
            self._process_chord_line(line)
        else:  # This is a lyric line
            self._process_lyric_line(line)
    
    def _process_chord_line(self, line: str):
        """Process a line containing chords."""
        # Extract chords using the measure pattern
        measures = MEASURE_PATTERN.findall(line)
        if not measures:
            return
            
        chords_in_measure = []
        for measure in measures:
            # Split the measure into chord positions
            chords = CHORD_PATTERN.findall(measure)
            if not chords:
                # Check for repeat symbol
                if REPEAT_PATTERN.search(measure):
                    # Repeat the last chord if available
                    if self.current_chords and self.current_chords[-1]:
                        chords = [self.current_chords[-1][-1]]
            
            # Clean up chords
            chords = [self._clean_chord(c) for c in chords if c]
            
            # Handle repeats within the measure
            if '/' in measure and not chords:
                # Count the number of slashes to determine repeats
                slash_count = measure.count('/')
                if self.current_chords and self.current_chords[-1]:
                    chords = [self.current_chords[-1][-1]] * (slash_count + 1)
            
            chords_in_measure.extend(chords)
        
        if chords_in_measure:
            self.current_chords.append(chords_in_measure)
            # Add to the set of unique chords in the song
            self.current_song['chords'].update(chords_in_measure)
    
    def _process_lyric_line(self, line: str):
        """Process a line containing lyrics."""
        self.current_lyrics.append(line)
    
    def _finalize_section(self):
        """Finalize the current section and add it to the song."""
        if not self.current_section and (self.current_lyrics or self.current_chords):
            self.current_section = 'Verse 1'  # Default section name
            
        if self.current_section and (self.current_lyrics or self.current_chords):
            self.current_song['sections'].append({
                'name': self.current_section,
                'lyrics': self.current_lyrics,
                'chords': self.current_chords
            })
            
        self.current_section = None
        self.current_lyrics = []
        self.current_chords = []
    
    def _finalize_song(self):
        """Finalize the current song and add it to the list."""
        if not self.current_song:
            return
            
        # Finalize the last section
        if self.current_lyrics or self.current_chords:
            self._finalize_section()
        
        # Convert chords set to list
        self.current_song['chords'] = list(self.current_song['chords'])
        
        # Extract a simple chord progression (first few chords of the first section)
        progression = []
        for section in self.current_song['sections']:
            for chord_sequence in section.get('chords', []):
                progression.extend(chord_sequence)
                if len(progression) >= 8:  # Get first 8 chords for the progression
                    break
            if progression:
                break
                
        self.current_song['progression'] = progression[:8]  # Limit to first 8 chords
        
        # Add to songs list
        self.songs.append(self.current_song)
        self.current_song = None
    
    @staticmethod
    def _clean_chord(chord: str) -> str:
        """Clean and standardize chord notation."""
        # Basic cleaning - you might need to adjust this based on the PDF's format
        chord = chord.strip()
        
        # Standardize minor chords (sometimes written as 'm', 'min', or '-'
        chord = chord.replace('min', 'm').replace('-', 'm')
        
        # Standardize major 7th
        chord = chord.replace('maj7', 'M7')
        
        # Remove any extra spaces
        chord = ''.join(chord.split())
        
        return chord

def save_songs_to_json(songs: List[Dict], output_file: str):
    """Save the parsed songs to a JSON file."""
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Convert to a simpler format for the main application
    simplified_songs = []
    for song in songs:
        simplified_songs.append({
            'title': song['title'],
            'artist': song.get('artist', 'Jerry Garcia / Grateful Dead'),
            'progression': song.get('progression', []),
            'source': song.get('source', 'Jerry Garcia Song Book v9'),
            'all_chords': song.get('chords', [])
        })
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(simplified_songs, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(simplified_songs)} songs to {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Parse Jerry Garcia Song Book PDF')
    parser.add_argument('--input', type=str, default='jerry-garcia-song-book-ver-9-online.pdf',
                       help='Path to the PDF file')
    parser.add_argument('--output', type=str, default='jerry_in_a_box/data/songs.json',
                       help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found.")
        return
    
    # Parse the PDF
    parser = SongParser(args.input)
    songs = parser.parse()
    
    if not songs:
        print("No songs were parsed from the PDF.")
        return
    
    # Save the songs to a JSON file
    save_songs_to_json(songs, args.output)
    
    # Print a summary
    print(f"\nSuccessfully parsed {len(songs)} songs:")
    for i, song in enumerate(songs[:10], 1):  # Show first 10 songs as a sample
        print(f"{i}. {song['title']} ({len(song.get('chords', []))} unique chords)")
    
    if len(songs) > 10:
        print(f"... and {len(songs) - 10} more")

if __name__ == "__main__":
    main()
