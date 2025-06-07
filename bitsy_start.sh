#!/bin/bash
# Bitsy Auto-Start Script

# Set working directory to the home directory
cd /home/jmunning

# Log file for debugging
LOGFILE="/home/jmunning/bitsy_startup.log"

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOGFILE"
}

log "Starting Bitsy service..."

# Wait for system to fully boot and network to be available
log "Waiting for system initialization..."
sleep 30

# Check if required hardware interfaces are available
if [ ! -d "/sys/class/gpio" ]; then
    log "ERROR: GPIO interface not available"
    exit 1
fi

# Check if I2C is available (for PCA9685)
if [ ! -e "/dev/i2c-1" ]; then
    log "ERROR: I2C interface not available"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "chatgpt_with_driving.py" ]; then
    log "ERROR: chatgpt_with_driving.py not found in current directory: $(pwd)"
    log "Contents of current directory:"
    ls -la >> "$LOGFILE"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    log "Activating virtual environment..."
    source venv/bin/activate
    log "Virtual environment activated. Python path: $(which python3)"
else
    log "WARNING: No virtual environment found, using system Python"
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    log "ERROR: .env file not found - OpenAI API key required"
    exit 1
fi

# Set proper permissions for GPIO/I2C access
log "Setting permissions for hardware access..."
sudo chmod 666 /dev/i2c-1
sudo chmod 666 /dev/gpiomem

# Set audio environment variables to suppress JACK errors
export JACK_NO_START_SERVER=1
export JACK_NO_AUDIO_RESERVATION=1

# Log system information for debugging
log "System info - User: $(whoami), Directory: $(pwd)"
log "Python version: $(python3 --version)"
log "Available microphones:"
python3 -c "import speech_recognition as sr; [print(f'Index {i}: {name}') for i, name in enumerate(sr.Microphone.list_microphone_names())]" >> "$LOGFILE" 2>&1

# Run the main script
log "Starting ChatGPT with driving script..."
python3 chatgpt_with_driving.py >> "$LOGFILE" 2>&1 &

# Store the PID for later use
echo $! > /home/jmunning/bitsy.pid

log "Bitsy service started with PID: $!" 