#!/usr/bin/env python3
"""
Script to verify Playwright browser installation
"""

import os
import sys
from playwright.async_api import async_playwright

async def verify_browser():
    print("🔍 Verifying Playwright browser installation...")
    
    # Check environment variable
    browser_path = os.getenv('PLAYWRIGHT_BROWSERS_PATH')
    if browser_path:
        print(f"✅ PLAYWRIGHT_BROWSERS_PATH set to: {browser_path}")
        
        # Check if the path exists
        if os.path.exists(browser_path):
            print(f"✅ Browser path exists: {browser_path}")
            
            # Check for chromium executable
            chromium_path = os.path.join(browser_path, 'chromium-1091', 'chrome-linux', 'chrome')
            if os.path.exists(chromium_path):
                print(f"✅ Chromium executable found: {chromium_path}")
            else:
                print(f"❌ Chromium executable not found at: {chromium_path}")
        else:
            print(f"❌ Browser path does not exist: {browser_path}")
    else:
        print("⚠️  PLAYWRIGHT_BROWSERS_PATH not set")
    
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
