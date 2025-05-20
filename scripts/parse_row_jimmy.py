#!/usr/bin/env python3
"""
Parser for Row Jimmy song format.
"""
import re
from typing import List, Dict, Tuple, Optional

class SongParser:
    def __init__(self):
        self.chord_pattern = re.compile(r'\b([A-G][#b]?m?\d*)\b')
        self.measure_pattern = re.compile(r'\|([^|]*)\|')
    
    def parse_measure(self, measure: str) -> List[str]:
        """Parse a single measure and return the chord(s) in it."""
        # Clean the measure
        measure = measure.strip()
        if not measure or measure == '%':
            return []
            
        # Handle special case for Break section
        if 'Break' in measure:
            # Special handling for Break: A / Bm / | A / D / | A / G / | D / / / |
            if 'A / Bm /' in measure:
                return ['A', 'Bm']
            elif 'A / D /' in measure:
                return ['A', 'D']
            elif 'A / G /' in measure:
                return ['A', 'G']
            elif 'D / / /' in measure:
                return ['D']
        
        # Try to extract chords in order they appear
        chords = []
        parts = re.split(r'\s+/+\s*', measure)
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            # Look for chord at start of part
            chord_match = re.match(r'^([A-G][#b]?m?\d*)\b', part)
            if chord_match:
                chord = chord_match.group(1)
                if chord not in chords:  # Avoid duplicates
                    chords.append(chord)
        
        return chords
    
    def parse_line(self, line: str) -> Tuple[Optional[str], List[str]]:
        """Parse a line and return (section_name, chords)."""
        # Check for section headers
        section_match = re.match(r'^\s*(V\d+|Chorus|Intro|Break|Ending|Lead|Ch\.)(?:\s|:|\[|\||$)', line, re.IGNORECASE)
        if section_match:
            section = section_match.group(1)
            # Remove the section header from the line
            line = line[section_match.end():].strip()
        else:
            section = None
            
        # Extract measures
        measures = self.measure_pattern.findall(line)
        if not measures and '|' in line:  # Handle case where pattern matches but no content
            measures = [m for m in line.split('|') if m.strip()]
            
        # Parse each measure
        chords = []
        for measure in measures:
            chords.extend(self.parse_measure(measure))
            
        return section, chords
    
    def parse_song(self, file_path: str) -> Dict:
        """Parse a song file and return structured data."""
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        
        if not lines:
            return {}
            
        # First line is the title
        title = lines[0].split('(')[0].strip()
        
        # Process all chord progressions
        progressions = {}
        current_section = None
        
        for line in lines[1:]:
            # Skip lines that are obviously lyrics
            if (not any(c in line for c in '|[]{}()') and 
                not any(word in line.lower() for word in ['intro', 'verse', 'chorus', 'break', 'ending', 'lead'])):
                continue
                
            section, chords = self.parse_line(line)
            
            if section:
                current_section = section
                if current_section not in progressions:
                    progressions[current_section] = []
            
            if chords and current_section:
                progressions[current_section].extend(chords)
        
        # Get the main progression (usually from the first verse or chorus)
        main_progression = []
        for section in ['V1', 'Verse 1', 'Chorus', 'Intro']:
            if section in progressions:
                main_progression = progressions[section][:8]  # First 8 chords
                break
        
        # Get all unique chords
        all_chords = set()
        for section_chords in progressions.values():
            all_chords.update(section_chords)
        
        return {
            'title': title,
            'artist': 'Jerry Garcia / Grateful Dead',
            'progression': main_progression,
            'sections': progressions,
            'all_chords': sorted(list(all_chords)),
            'source': 'Jerry Garcia Song Book v9'
        }

def print_song_info(song_data: Dict):
    """Print song information in a readable format."""
    print(f"\n{'='*50}")
    print(f"Title: {song_data['title']}")
    print(f"Artist: {song_data['artist']}")
    print(f"Source: {song_data['source']}")
    
    print("\nMain Progression:")
    print(" -> ".join(song_data['progression']) if song_data['progression'] else "No progression found")
    
    print("\nAll Chords:")
    print(", ".join(song_data['all_chords']))
    
    print("\nSections:")
    for section, chords in song_data['sections'].items():
        print(f"\n{section}:")
        print(" -> ".join(chords) if chords else "No chords")
    
    print(f"\n{'='*50}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python parse_row_jimmy.py <song_file.txt>")
        sys.exit(1)
    
    parser = SongParser()
    song_data = parser.parse_song(sys.argv[1])
    print_song_info(song_data)
