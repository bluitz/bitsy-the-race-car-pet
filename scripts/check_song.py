#!/usr/bin/env python3
"""
Script to search for a song in the database and display its chords.
"""
import json
import sys
from pathlib import Path

def search_song(song_name):
    # Path to the songs database
    db_path = Path('jerry_in_a_box/data/songs.json')
    
    if not db_path.exists():
        print(f"Error: Database file not found at {db_path}")
        return
    
    try:
        # Load the songs database
        with open(db_path, 'r', encoding='utf-8') as f:
            songs = json.load(f)
        
        # Search for songs containing the search term (case-insensitive)
        matching_songs = [
            song for song in songs 
            if song_name.lower() in song.get('title', '').lower()
        ]
        
        if not matching_songs:
            print(f"No songs found containing '{song_name}'")
            return
        
        print(f"Found {len(matching_songs)} songs containing '{song_name}':\n")
        
        for song in matching_songs:
            title = song.get('title', 'Untitled')
            artist = song.get('artist', 'Unknown Artist')
            progression = song.get('progression', [])
            source = song.get('source', 'Unknown Source')
            
            print(f"Title: {title}")
            print(f"Artist: {artist}")
            print(f"Source: {source}")
            print("Chord Progression:")
            
            if progression:
                print(" -> ".join(progression))
            else:
                print("No chord progression available")
            
            print("\n" + "-"*50 + "\n")
    
    except Exception as e:
        print(f"Error searching for song: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_song.py <song_name>")
        sys.exit(1)
    
    search_term = " ".join(sys.argv[1:])
    search_song(search_term)
