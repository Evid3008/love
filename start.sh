#!/bin/bash

# Netflix Cookie Bot Startup Script
# This script handles the startup process for various deployment environments

set -e

echo "🚀 Starting Netflix Cookie Bot..."

# Function to check if environment variable is set
check_env() {
    if [ -z "${!1}" ]; then
        echo "❌ Error: $1 environment variable is not set!"
        echo "Please set $1 in your environment or .env file"
        exit 1
    fi
}

# Check required environment variables
check_env "BOT_TOKEN"

echo "✅ Environment variables validated"

# Create necessary directories
mkdir -p logs temp screenshots

# Set proper permissions
chmod 755 logs temp screenshots

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "📦 Installing Python dependencies..."
    pip install --no-cache-dir -r requirements.txt
fi

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
export PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright
playwright install chromium --with-deps

# Clean up any existing artifacts
echo "🧹 Cleaning up artifacts..."
find . -name "debug_*" -delete 2>/dev/null || true
find . -name "nfshot_*" -delete 2>/dev/null || true
find . -name "nfsecshot_*" -delete 2>/dev/null || true
find . -name "*.png" -delete 2>/dev/null || true
find . -name "Invalid.zip" -delete 2>/dev/null || true

# Health check function
health_check() {
    echo "🏥 Performing health check..."
    python -c "
import requests
import os
token = os.getenv('BOT_TOKEN')
if token:
    try:
        response = requests.get(f'https://api.telegram.org/bot{token}/getMe', timeout=10)
        if response.status_code == 200:
            bot_info = response.json()
            if bot_info.get('ok'):
                print(f'✅ Bot is ready: @{bot_info[\"result\"][\"username\"]}')
                exit(0)
            else:
                print(f'❌ Bot API error: {bot_info.get(\"description\", \"Unknown error\")}')
                exit(1)
        else:
            print(f'❌ HTTP error: {response.status_code}')
            exit(1)
    except Exception as e:
        print(f'❌ Health check failed: {e}')
        exit(1)
else:
    print('❌ BOT_TOKEN not found')
    exit(1)
"
}

# Run health check
health_check

echo "🎬 Starting Netflix Cookie Bot..."
echo "✨ No limits, no restrictions!"
echo "📝 Send Netflix cookies to get instant results!"

# Start the bot
exec python bot.py
