#!/usr/bin/env python3
"""
Script to manually install Playwright browser
"""

import os
import subprocess
import sys

def install_browser():
    print("🔧 Installing Playwright browser...")
    
    # Set environment variable
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/app/.cache/ms-playwright'
    
    try:
        # Install chromium with dependencies
        result = subprocess.run([
            'playwright', 'install', 'chromium', '--with-deps'
        ], capture_output=True, text=True, check=True)
        
        print("✅ Browser installed successfully!")
        print(result.stdout)
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install browser: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ Playwright command not found. Make sure playwright is installed.")
        return False

if __name__ == "__main__":
    success = install_browser()
    sys.exit(0 if success else 1)
