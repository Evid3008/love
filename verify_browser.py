#!/usr/bin/env python3
"""
Script to verify Playwright browser installation
"""

import os
import sys
from playwright.async_api import async_playwright

async def verify_browser():
    print("🔍 Verifying Playwright browser installation...")
    
    import glob
    
    # Check environment variable
    browser_path = os.getenv('PLAYWRIGHT_BROWSERS_PATH')
    if browser_path:
        print(f"✅ PLAYWRIGHT_BROWSERS_PATH set to: {browser_path}")
        
        # Check if the path exists
        if os.path.exists(browser_path):
            print(f"✅ Browser path exists: {browser_path}")
            
            # Check for chromium executable with wildcard
            chromium_patterns = [
                os.path.join(browser_path, 'chromium-1091', 'chrome-linux', 'chrome'),
                os.path.join(browser_path, 'chromium-*', 'chrome-linux', 'chrome'),
            ]
            
            found = False
            for pattern in chromium_patterns:
                if '*' in pattern:
                    matches = glob.glob(pattern)
                    if matches:
                        print(f"✅ Chromium executable found: {matches[0]}")
                        found = True
                        break
                elif os.path.exists(pattern):
                    print(f"✅ Chromium executable found: {pattern}")
                    found = True
                    break
            
            if not found:
                print(f"❌ Chromium executable not found in: {browser_path}")
        else:
            print(f"❌ Browser path does not exist: {browser_path}")
    else:
        print("⚠️  PLAYWRIGHT_BROWSERS_PATH not set")
    
    # Check default locations
    default_paths = [
        '/app/.cache/ms-playwright',
        '/home/botuser/.cache/ms-playwright',
    ]
    
    for path in default_paths:
        if os.path.exists(path):
            print(f"✅ Default path exists: {path}")
            chromium_pattern = os.path.join(path, 'chromium-*', 'chrome-linux', 'chrome')
            matches = glob.glob(chromium_pattern)
            if matches:
                print(f"✅ Found chromium in default location: {matches[0]}")
    
    # Try to launch browser
    try:
        async with async_playwright() as p:
            print("🚀 Attempting to launch browser...")
            browser = await p.chromium.launch(headless=True)
            await browser.close()
            print("✅ Browser launched successfully!")
            return True
    except Exception as e:
        print(f"❌ Failed to launch browser: {e}")
        return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(verify_browser())
    sys.exit(0 if success else 1)
