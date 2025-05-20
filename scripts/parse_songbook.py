#!/usr/bin/env python3
"""
Script to parse the Jerry Garcia Song Book PDF and extract song information.
"""
import os
import re
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
import pdfplumber
from tqdm import tqdm

# Regular expressions for parsing song information
SONG_TITLE_PATTERN = re.compile(r'^\s*([A-Z][A-Za-z0-9\s\'"\-\(\)\&\,\.\!\?]+?)\s*$')
CHORD_PATTERN = re.compile(r'\b([A-G][#b]?(?:maj|min|m|add|dim|aug|sus)?[0-9]*(?:\/[A-G][#b]?)?\b)')
MEASURE_PATTERN = re.compile(r'\|([^|]*)\|')
REPEAT_PATTERN = re.compile(r'%')
SECTION_PATTERN = re.compile(r'^\s*(?:\[([^\]]+)\]|(Intro|Verse|Chorus|Bridge|Solo|Outro|Turnaround|Break|Tag|Ending)\s*\d*)\s*$', re.IGNORECASE)

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
        if not line or line.isdigit() or line.strip() == '%' or len(line.strip()) < 2:
            return
            
        # Check for section headers first (e.g., [Intro], [Verse 1], etc.)
        section_match = SECTION_PATTERN.match(line)
        if section_match:
            section_name = section_match.group(1) or section_match.group(2)
            if section_name:
                self._finalize_section()
                self.current_section = section_name.strip()
                return
        
        # Check if this is a song title (all caps or title case, not too long)
        is_title = (
            (line.isupper() or (line[0].isupper() and not line.isupper())) and 
            len(line) > 2 and 
            len(line) < 100 and
            not any(c in line for c in '|[](){}')
        )
        
        if is_title and not self.current_song:
            # Start a new song
            self.current_song = {
                'title': line.strip(),
                'artist': 'Jerry Garcia / Grateful Dead',
                'sections': [],
                'chords': set(),
                'source': 'Jerry Garcia Song Book v9',
                'raw_text': []
            }
            self.current_section = 'Verse 1'  # Default section
            self.current_lyrics = []
            self.current_chords = []
            return
            
        # If we're not in a song, skip
        if not self.current_song:
            return
            
        # Store raw text for debugging
        self.current_song['raw_text'] = self.current_song.get('raw_text', []) + [line]
            
        # Check for chord lines (contain chords or | symbols)
        has_chords = '|' in line or any(c in line for c in 'ABCDEFG#bm/')
        
        # Process chord and lyric lines
        if has_chords:
            self._process_chord_line(line)
        else:
            # This might be a section header or lyrics
            line_lower = line.lower().strip()
            if (line_lower.startswith(('verse', 'chorus', 'intro', 'bridge', 'solo', 'outro', 'tag')) 
                    and len(line.split()) <= 3):
                self._finalize_section()
                self.current_section = line.strip()
            else:
                self._process_lyric_line(line)
    
    def _process_chord_line(self, line: str):
        """Process a line containing chords."""
        # Clean the line
        line = line.strip()
        
        # Special case: If the line is just a repeat symbol, repeat the last chord
        if line.strip() == '%':
            if self.current_chords and self.current_chords[-1]:
                self.current_chords.append(self.current_chords[-1][-1:])
            return
            
        # Extract measures
        measures = MEASURE_PATTERN.findall(line)
        
        # If no measures found but line contains chords, treat the whole line as a measure
        if not measures and any(c in line for c in 'ABCDEFG#bm/'):
            measures = [line]
            
        chords_in_measure = []
        
        for measure in measures:
            # Clean the measure
            measure = measure.strip()
            
            # Handle repeat symbol
            if measure == '%':
                if self.current_chords and self.current_chords[-1]:
                    chords_in_measure.append(self.current_chords[-1][-1])
                continue
                
            # Handle slashes for chord repeats
            if '/' in measure and not any(c.isalpha() for c in measure.replace('/', '')):
                # This is a measure with just slashes, repeat the last chord
                if self.current_chords and self.current_chords[-1]:
                    repeat_count = measure.count('/') + 1
                    chords_in_measure.extend([self.current_chords[-1][-1]] * repeat_count)
                continue
                
            # Extract chords from the measure
            chords = CHORD_PATTERN.findall(measure)
            
            # If no chords found but there are slashes, it might be a continuation
            if not chords and '/' in measure:
                # Count the slashes and repeat the last chord
                if self.current_chords and self.current_chords[-1]:
                    repeat_count = measure.count('/') + 1
                    chords = [self.current_chords[-1][-1]] * repeat_count
            
            # Clean and validate chords
            cleaned_chords = []
            for chord in chords:
                cleaned = self._clean_chord(chord)
                if cleaned and (not cleaned_chords or cleaned != cleaned_chords[-1]):
                    cleaned_chords.append(cleaned)
            
            # Handle common chord patterns
            if not cleaned_chords and 'N.C.' in measure:
                # No chord played
                cleaned_chords.append('N.C.')
            
            chords_in_measure.extend(cleaned_chords)
        
        # Add the chords to the current progression
        if chords_in_measure:
            self.current_chords.append(chords_in_measure)
            # Add to the set of unique chords in the song
            self.current_song['chords'].update(chords_in_measure)
            
            # If this is the first chord line in a section, it might be the main progression
            if len(self.current_song.get('progression', [])) < 4 and len(chords_in_measure) >= 4:
                self.current_song['progression'] = chords_in_measure[:8]  # Store first 8 chords as the main progression
    
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
        
        # Convert chords set to list and filter out empty strings
        self.current_song['chords'] = [c for c in self.current_song['chords'] if c and c != 'N.C.']
        
        # Extract chord progressions from all sections
        all_chords = []
        for section in self.current_song['sections']:
            for chord_sequence in section.get('chords', []):
                if isinstance(chord_sequence, list):
                    all_chords.extend(chord_sequence)
                else:
                    all_chords.append(chord_sequence)
        
        # Remove consecutive duplicates
        unique_chords = []
        last_chord = None
        for chord in all_chords:
            if chord != last_chord:
                unique_chords.append(chord)
                last_chord = chord
        
        # If we have a progression already, use it, otherwise take the first 8 unique chords
        if 'progression' not in self.current_song or not self.current_song['progression']:
            self.current_song['progression'] = unique_chords[:8]
        
        # Add some metadata
        self.current_song['section_count'] = len(self.current_song.get('sections', []))
        self.current_song['chord_count'] = len(self.current_song['chords'])
        
        # Only add the song if it has chords
        if self.current_song['chords']:
            self.songs.append(self.current_song)
        
        self.current_song = None
    
    @staticmethod
    def _clean_chord(chord: str) -> str:
        """Clean and standardize chord notation."""
        if not chord or chord == 'N.C.':
            return chord
            
        # Basic cleaning
        chord = chord.strip().upper()
        
        # Handle common variations
        variations = {
            'MIN': 'M',
            'MINOR': 'M',
            'MAJ': '',
            'MAJOR': '',
            'SUS': 'SUS',
            'DIM': 'DIM',
            'AUG': 'AUG',
            'AD': 'ADD'
        }
        
        # Standardize chord types
        for orig, repl in variations.items():
            if orig in chord:
                chord = chord.replace(orig, repl)
        
        # Standardize minor chords (m, min, -)
        if 'M' in chord or 'MIN' in chord or '-' in chord:
            chord = chord.replace('MIN', 'M').replace('-', 'M')
            if 'M' not in chord:
                chord = chord[0] + 'M' + chord[1:]
        
        # Handle 7th chords
        if '7' in chord and 'M7' not in chord and 'M7' not in chord.upper():
            chord = chord.replace('7', '7')
            
        # Handle major 7th
        if 'MAJ7' in chord or 'MAJ7' in chord.upper():
            chord = chord.replace('MAJ7', 'M7').replace('maj7', 'M7')
        
        # Clean up any remaining spaces or special characters
        chord = ''.join(c for c in chord if c.isalnum() or c in '#b/')
        
        # Ensure the root note is valid
        if not chord or chord[0] not in 'ABCDEFG' or len(chord) > 1 and chord[1] not in '#b0123456789mM/':
            return ''
            
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
