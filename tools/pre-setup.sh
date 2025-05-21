#!/bin/bash
set -e

echo "📦 Installing APT dependencies..."
sudo apt update
xargs -a requirements_apt.txt sudo apt install -y

echo "🐍 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "⬆️ Upgrading pip..."
pip install --upgrade pip

echo "📦 Installing Python dependencies from requirements_py.txt..."
pip install -r requirements_py.txt

echo "✅ Setup complete."
echo "👉 Activate the virtual environment with: source venv/bin/activate"