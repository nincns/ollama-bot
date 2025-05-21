#!/bin/bash
echo "📦 Installiere APT-Abhängigkeiten..."

sudo apt update
xargs -a requirements_apt.txt sudo apt install -y
