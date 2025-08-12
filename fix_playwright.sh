#!/bin/bash

echo "🔧 Fixing Playwright installation..."

# Remove existing Playwright installation
echo "🧹 Cleaning existing Playwright installation..."
rm -rf ~/.cache/ms-playwright
rm -rf ~/.local/share/ms-playwright

# Reinstall Playwright
echo "📦 Reinstalling Playwright..."
pip uninstall playwright -y
pip install playwright==1.40.0

# Install browsers
echo "🌐 Installing Playwright browsers..."
playwright install chromium --with-deps

# Verify installation
echo "✅ Verifying installation..."
playwright --version
playwright install --help

echo "🎉 Playwright installation fixed!"
echo "🚀 You can now run: python bot.py"
