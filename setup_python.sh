#!/bin/bash

# Setup script for Python image conversion dependencies
# Usage: bash setup_python.sh

echo "Setting up Python dependencies for image conversion..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.7 or higher."
    echo "   macOS: brew install python3"
    echo "   Ubuntu/Debian: sudo apt-get install python3"
    echo "   Or download from: https://www.python.org/downloads/"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Install Pillow
echo "Installing Pillow (PIL)..."
python3 -m pip install --upgrade Pillow

if [ $? -eq 0 ]; then
    echo "✓ Pillow installed successfully"
else
    echo "❌ Failed to install Pillow"
    echo "   Try manually: python3 -m pip install Pillow"
    exit 1
fi

# Make the conversion script executable
chmod +x "$(dirname "$0")/convert_image.py"
echo "✓ Conversion script permissions updated"

# Verify setup
echo ""
echo "Verifying Python setup..."
python3 << 'EOF'
try:
    from PIL import Image
    import base64
    import io
    print("✓ Python environment ready for image conversion")
except ImportError as e:
    print(f"❌ Missing import: {e}")
    exit(1)
EOF

echo ""
echo "✅ Setup complete! You can now run the image scraper with Python conversion."
