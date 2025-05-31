#!/bin/bash
# Setup Auto-Start for Bitsy

echo "🤖 Setting up Bitsy Auto-Start Service..."

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please do not run this script as root/sudo"
    echo "   Run it as user jmunning: ./setup_autostart.sh"
    exit 1
fi

# Check if we're on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Make startup script executable
echo "📁 Making startup script executable..."
chmod +x bitsy_start.sh

# Copy service file to systemd directory
echo "📋 Installing systemd service..."
sudo cp bitsy.service /etc/systemd/system/

# Add user to required groups for hardware access
echo "👤 Adding user to hardware access groups..."
sudo usermod -a -G gpio,i2c,spi,audio jmunning

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: No .env file found!"
    echo "   Please create a .env file with your OpenAI API key:"
    echo "   echo 'OPENAI_API_KEY=your_api_key_here' > .env"
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠️  Warning: No virtual environment found!"
    echo "   Creating virtual environment and installing dependencies..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# Enable I2C and SPI if not already enabled
echo "🔧 Checking hardware interfaces..."
if ! grep -q "dtparam=i2c_arm=on" /boot/config.txt; then
    echo "   Enabling I2C interface..."
    echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt
fi

if ! grep -q "dtparam=spi=on" /boot/config.txt; then
    echo "   Enabling SPI interface..."
    echo "dtparam=spi=on" | sudo tee -a /boot/config.txt
fi

# Reload systemd and enable the service
echo "⚙️  Configuring systemd service..."
sudo systemctl daemon-reload
sudo systemctl enable bitsy.service

echo ""
echo "✅ Auto-start setup complete!"
echo ""
echo "🎯 Next steps:"
echo "   1. Reboot your Raspberry Pi: sudo reboot"
echo "   2. Check service status: sudo systemctl status bitsy"
echo "   3. View logs: tail -f bitsy.log"
echo ""
echo "🛠️  Useful commands:"
echo "   • Start service: sudo systemctl start bitsy"
echo "   • Stop service: sudo systemctl stop bitsy"
echo "   • Disable auto-start: sudo systemctl disable bitsy"
echo "   • View service logs: sudo journalctl -u bitsy -f"
echo ""
echo "📝 Log files will be created:"
echo "   • bitsy.log - Startup process logs"
echo "   • bitsy.log - Service runtime logs" 