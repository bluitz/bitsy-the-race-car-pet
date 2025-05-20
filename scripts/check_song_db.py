#!/usr/bin/env python3
"""
Check the song database for a specific song.
"""
import json
import sys

def load_songs(db_path: str) -> list:
    """Load songs from the JSON database."""
    with open(db_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def find_song(songs: list, title: str) -> dict:
    """Find a song by title (case-insensitive)."""
    title_lower = title.lower()
    for song in songs:
        if song['title'].lower() == title_lower:
            return song
    return None

def print_song(song: dict):
    """Print song information."""
    if not song:
        print("Song not found.")
        return
    
    print(f"\n{'='*50}")
    print(f"Title: {song['title']}")
    print(f"Artist: {song.get('artist', 'Unknown')}")
    print(f"Source: {song.get('source', 'Unknown')}")
    
    print("\nMain Progression:")
    print(" -> ".join(song['progression']) if song.get('progression') else "No progression")
    
    print("\nAll Chords:")
    print(", ".join(song.get('all_chords', [])))
    
    print("\nSections:")
    for section_name, section in song.get('sections', {}).items():
        print(f"\n{section_name}:")
        print(f"Original: {section.get('progression', '')}")
        print(f"Chords: {' -> '.join(section.get('chords', []))}")
    
    print(f"\n{'='*50}")

if __name__ == "__main__":
    db_path = "jerry_in_a_box/data/songs.json"
    
    # Load songs
    try:
        songs = load_songs(db_path)
    except FileNotFoundError:
        print(f"Error: Database file not found at {db_path}")
        sys.exit(1)
    
    # Get song title from command line or use default
    if len(sys.argv) > 1:
        title = " ".join(sys.argv[1:])
    else:
        title = "Row Jimmy"
    
    # Find and print the song
    song = find_song(songs, title)
    print_song(song)
