#!/bin/bash

# Install audio dependencies for Bitsy on Raspberry Pi

echo "Installing audio dependencies for Bitsy..."

# Update package list
sudo apt update

# Install audio players and codecs
echo "Installing mpg123 (MP3 player)..."
sudo apt install -y mpg123

echo "Installing alsa-utils (includes aplay)..."
sudo apt install -y alsa-utils

echo "Installing pulseaudio-utils (includes paplay)..."
sudo apt install -y pulseaudio-utils

echo "Installing ffmpeg (includes ffplay)..."
sudo apt install -y ffmpeg

echo "Installing espeak (text-to-speech fallback)..."
sudo apt install -y espeak

echo "Audio dependencies installed successfully!"
echo "You can now run Bitsy without pygame audio conflicts." 