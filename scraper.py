from playwright.async_api import async_playwright
import re
import logging
from typing import Dict, List, Optional
import uuid
import subprocess
import sys

# Configure logging - LIVE DEBUG MODE
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Abort control for long-running sessions
ABORT_REQUESTED: bool = False

def request_abort() -> None:
    """Signal any in-flight scraping session to abort ASAP."""
    global ABORT_REQUESTED
    ABORT_REQUESTED = True

# Netflix URLs
BROWSE_URL = "https://www.netflix.com/browse"
ACCOUNT_URL = "https://www.netflix.com/account"
SECURITY_URL = "https://www.netflix.com/account/security"
PROFILES_URL = "https://www.netflix.com/account/profiles"
MEMBERSHIP_URL = "https://www.netflix.com/account/membership"
VIEWING_ACTIVITY_URL = "https://www.netflix.com/viewingactivity"
PROFILE_SEL = "div.profile-icon"
TIMEOUT = 30_000  # 30 seconds timeout

async def _ensure_chromium_and_launch(
    p,
    *,
    headless: bool = True,
    slow_mo: int = 0,
    args: Optional[List[str]] = None,
    viewport: Optional[Dict[str, int]] = None,
    user_agent: Optional[str] = None,
):
    """Original launcher without auto-install or locale/headers overrides."""
    import os
    import glob
    launch_args = args or []
    
    # Set environment variable if not already set
    if not os.getenv('PLAYWRIGHT_BROWSERS_PATH'):
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/app/.cache/ms-playwright'
        logger.info("🔧 Set PLAYWRIGHT_BROWSERS_PATH to /app/.cache/ms-playwright")
    
    # Try multiple browser paths
    executable_path = None
    
    # 1. Check environment variable first
    env_path = os.getenv('PLAYWRIGHT_BROWSERS_PATH')
    logger.info(f"🔍 Environment path: {env_path}")
    
    if env_path:
        possible_paths = [
            os.path.join(env_path, 'chromium-1091', 'chrome-linux', 'chrome'),
            os.path.join(env_path, 'chromium-*', 'chrome-linux', 'chrome'),
        ]
        for path in possible_paths:
            if '*' in path:
                # Handle wildcard paths
                matches = glob.glob(path)
                if matches:
                    executable_path = matches[0]
                    logger.info(f"✅ Found browser via wildcard: {executable_path}")
                    break
            elif os.path.exists(path):
                executable_path = path
                logger.info(f"✅ Found browser via direct path: {executable_path}")
                break
    
    # 2. If not found, try default locations
    if not executable_path:
        logger.info("🔍 Trying default locations...")
        default_paths = [
            '/app/.cache/ms-playwright/chromium-1091/chrome-linux/chrome',
            '/app/.cache/ms-playwright/chromium-*/chrome-linux/chrome',
            '/home/botuser/.cache/ms-playwright/chromium-1091/chrome-linux/chrome',
            '/home/botuser/.cache/ms-playwright/chromium-*/chrome-linux/chrome',
        ]
        for path in default_paths:
            if '*' in path:
                matches = glob.glob(path)
                if matches:
                    executable_path = matches[0]
                    logger.info(f"✅ Found browser in default location: {executable_path}")
                    break
            elif os.path.exists(path):
                executable_path = path
                logger.info(f"✅ Found browser in default location: {executable_path}")
                break
    
    # 3. If still not found, try to find any chromium executable
    if not executable_path:
        logger.info("🔍 Searching for any chromium executable...")
        search_paths = [
            '/app/.cache/ms-playwright',
            '/home/botuser/.cache/ms-playwright',
            '/root/.cache/ms-playwright',
        ]
        for search_path in search_paths:
            if os.path.exists(search_path):
                chromium_pattern = os.path.join(search_path, '**', 'chrome')
                matches = glob.glob(chromium_pattern, recursive=True)
                if matches:
                    executable_path = matches[0]
                    logger.info(f"✅ Found browser via recursive search: {executable_path}")
                    break
    
    logger.info(f"🔍 Final browser executable: {executable_path}")
    
    browser = await p.chromium.launch(
        headless=headless, 
        slow_mo=slow_mo, 
        args=launch_args,
        executable_path=executable_path if executable_path and os.path.exists(executable_path) else None
    )
    context_kwargs: Dict[str, object] = {}
    if viewport:
        context_kwargs["viewport"] = viewport
    if user_agent:
        context_kwargs["user_agent"] = user_agent
    context = await browser.new_context(**context_kwargs)
    return browser, context

def parse_cookies_string(cookie_str: str) -> list[dict]:
    cookies = []
    for pair in cookie_str.strip().split(";"):
        if "=" in pair:
            name, value = pair.strip().split("=", 1)
            cookies.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".netflix.com",
                "path": "/",
            })
    return cookies

async def goto_netflix_account(cookies: list[dict]) -> bool:
    async with async_playwright() as p:
        browser, context = await _ensure_chromium_and_launch(p, headless=True)
        await context.add_cookies(cookies)
        page = await context.new_page()

        try:
            await page.goto(BROWSE_URL, wait_until="networkidle", timeout=TIMEOUT)
            await page.goto(ACCOUNT_URL, wait_until="networkidle", timeout=TIMEOUT)

            if page.url.startswith(ACCOUNT_URL):
                await browser.close()
                return True

            try:
                await page.wait_for_selector(PROFILE_SEL, timeout=8000)
                await page.click(PROFILE_SEL, force=True)
                await page.wait_for_load_state("networkidle", timeout=TIMEOUT)
                await page.goto(ACCOUNT_URL, wait_until="networkidle", timeout=TIMEOUT)
                if page.url.startswith(ACCOUNT_URL):
                    await browser.close()
                    return True
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Error opening Netflix: {e}")

        await browser.close()
        return False

async def fetch_account_details(cookies: list[dict]) -> dict | None:
    async with async_playwright() as p:
        browser, context = await _ensure_chromium_and_launch(p, headless=True)
        await context.add_cookies(cookies)
        page = await context.new_page()

        email = "N/A"
        plan = "N/A"
        member_since = "N/A"
        package = "N/A"
        profile_name = "N/A"
        service_code = "N/A"
        phone_number = "N/A"
        email_verified = "N/A"
        phone_verified = "N/A"

        try:
            await page.goto(SECURITY_URL, wait_until="networkidle", timeout=TIMEOUT)
            text = await page.inner_text("body")
            email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
            if email_match:
                email = email_match.group(0)

            # Updated regex to handle various phone number formats including (609) 505-0234
            phone_match = re.search(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\+?\d{1,3}[-.\s]?\d{3,4}[-.\s]?\d{3,5}", text)
            if phone_match:
                phone_number = phone_match.group(0).strip()
            
            # Also try to find phone number in specific HTML structure like "Mobile phone(609) 505-0234"
            if phone_number == "N/A":
                mobile_phone_match = re.search(r"Mobile phone\s*\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
                if mobile_phone_match:
                    # Extract just the phone number part
                    phone_part = re.search(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", mobile_phone_match.group(0))
                    if phone_part:
                        phone_number = phone_part.group(0).strip()

            # Improved verification detection
            phone_verified = "N/A"
            email_verified = "N/A"
            
            # Check for verification status using multiple methods
            try:
                # Method 1: Look for verification status in the page content
                page_text = text.lower()
                
                # Check for phone verification
                if phone_number != "N/A":
                    # Look for phone verification patterns
                    phone_verification_patterns = [
                        "needs verification" in page_text,
                        "verify phone" in page_text,
                        "unverified phone" in page_text,
                        "phone verification" in page_text
                    ]
                    
                    if any(phone_verification_patterns):
                        phone_verified = "❌ Non-verified"
                    else:
                        # Check if phone is mentioned without verification issues
                        phone_verified = "✅ Verified"
                
                # Check for email verification
                if email != "N/A":
                    # Look for email verification patterns
                    email_verification_patterns = [
                        "needs verification" in page_text,
                        "verify email" in page_text,
                        "unverified email" in page_text,
                        "email verification" in page_text
                    ]
                    
                    if any(email_verification_patterns):
                        email_verified = "❌ Non-verified"
                    else:
                        # Check if email is mentioned without verification issues
                        email_verified = "✅ Verified"
                
                # Method 2: Look for verification status in specific HTML elements
                try:
                    # Look for verification status in security page elements
                    verification_status_elements = await page.query_selector_all('[data-uia*="verification"], [data-uia*="verify"], .verification-status, button[data-uia*="verify"], a[data-uia*="verify"]')
                    
                    for element in verification_status_elements:
                        element_text = await element.inner_text()
                        if "needs verification" in element_text.lower() or "verify" in element_text.lower():
                            if phone_number != "N/A" and phone_number in element_text:
                                phone_verified = "❌ Non-verified"
                            if email != "N/A" and email in element_text:
                                email_verified = "❌ Non-verified"
                    
                    # Method 3: Check for verification status by looking at button states
                    verify_buttons = await page.query_selector_all('button[data-uia*="verify"], a[data-uia*="verify"]')
                    
                    for button in verify_buttons:
                        button_text = await button.inner_text()
                        button_html = await button.inner_html()
                        
                        # If there's a verify button, it means verification is needed
                        if "verify" in button_text.lower():
                            if phone_number != "N/A" and (phone_number in button_html or "phone" in button_text.lower()):
                                phone_verified = "❌ Non-verified"
                            if email != "N/A" and (email in button_html or "email" in button_text.lower()):
                                email_verified = "❌ Non-verified"
                                
                except Exception as e:
                    logger.error(f"Error in verification element detection: {e}")
                    
            except Exception as e:
                logger.error(f"Error in verification detection: {e}")
                # Fallback to basic detection
                if "needs verification" in text.lower():
                    if phone_number != "N/A":
                        phone_verified = "❌ Non-verified"
                    if email != "N/A":
                        email_verified = "❌ Non-verified"
                else:
                    if phone_number != "N/A":
                        phone_verified = "✅ Verified"
                    if email != "N/A":
                        email_verified = "✅ Verified"

        except Exception as e:
            logger.error(f"Could not read email/phone: {e}")

        try:
            await page.goto(ACCOUNT_URL, wait_until="networkidle", timeout=TIMEOUT)
            
            elem = await page.query_selector('h3[data-uia="account-overview-page+membership-card+title"]')
            if elem:
                plan = (await elem.inner_text()).strip()

            mem = await page.query_selector('div[data-uia="account-overview-page+membership-card+plan-banner"]')
            if mem:
                txt = (await mem.inner_text()).strip()
                member_since = txt.replace("Member Since", "").strip()

            # Enhanced package/payment method extraction
            payment_detail_selectors = [
                '[data-uia*="payment+details"] span[data-uia*="mopType"]',
                '[data-uia*="DIRECT_DEBIT"] span[data-uia*="mopType"]',
                '[data-uia*="CREDIT_CARD"] span[data-uia*="mopType"]',
                '[data-uia*="PAYPAL"] span[data-uia*="mopType"]',
                'div[data-uia="account-overview-page+membership-card+payment"] p'
            ]
            
            for selector in payment_detail_selectors:
                try:
                    payment_element = await page.query_selector(selector)
                    if payment_element:
                        payment_text = (await payment_element.inner_text()).strip()
                        # Clean up HTML entities and extra spaces
                        payment_text = payment_text.replace('&nbsp;', ' ').replace('\u00a0', ' ').replace('  ', ' ')
                        if payment_text and len(payment_text) > 3:
                            package = payment_text
                            logger.info(f"✅ Found payment method: {payment_text}")
                            break
                except Exception:
                    continue

            btn = await page.query_selector('button[data-uia="account+footer+service-code-button"]')
            if btn:
                await btn.click()
                await page.wait_for_timeout(1000)
                service_code_text = await btn.inner_text()
                if service_code_text:
                    service_code = service_code_text.strip()

        except Exception as e:
            logger.error(f"Could not read plan/member/package/service code: {e}")

        try:
            await page.goto("https://www.netflix.com/account/profiles", wait_until="networkidle", timeout=TIMEOUT)
            name_div = await page.query_selector('div[data-cl-view="accountProfileSettings"] p.e1tifjsj0')
            if name_div:
                profile_name = (await name_div.inner_text()).strip()

        except Exception as e:
            logger.error(f"Could not read profile name: {e}")

        await browser.close()

        return {
            "email": email,
            "plan": plan,
            "member_since": member_since,
            "profile_name": profile_name,
            "package": package,
            "service_code": service_code,
            "phone_number": phone_number,
            "email_verified": email_verified,
            "phone_verified": phone_verified,
        }

async def detect_and_change_language_to_english(page) -> bool:
    """Detect if language is not English and force-change to English via language settings.

    Robust flow with multiple fallbacks: account profiles -> language section, or direct LanguagePreferences page.
    """
    try:
        logger.info("🔍 Checking current language...")

        # Quick check: HTML lang or URL locale
        try:
            html_lang = await page.get_attribute("html", "lang")
        except Exception:
            html_lang = None
        url_locale_non_english = any(seg in (page.url or "") for seg in ["/ja", "/es", "/de", "/fr", "/pl", "/it", "/pt", "/tr", "/ar", "/ru"]) if hasattr(page, 'url') else False
        if html_lang and html_lang.startswith("en") and not url_locale_non_english:
            logger.info("✅ Language is already English")
            return True

        # Always attempt to enforce English to be safe
        logger.info("🔄 Enforcing English language...")

        # Fallback A: try dedicated LanguagePreferences page first
        try:
            await page.goto("https://www.netflix.com/LanguagePreferences", wait_until="domcontentloaded", timeout=TIMEOUT)
            await page.wait_for_load_state("networkidle", timeout=15000)
            await page.wait_for_timeout(1000)

            # Try select dropdown approach
            try:
                dropdown = await page.query_selector('select, select[data-uia*="language"], select[name*="lang" i]')
                if dropdown:
                    for val in ["English", "en", "en-US", "en-GB"]:
                        try:
                            await dropdown.select_option(value=val)
                            break
                        except Exception:
                            continue
            except Exception:
                pass

            # Try radio button/label approach
            try:
                # Click label that contains English text
                english_label = await page.query_selector('label:has-text("English")')
                if english_label:
                    await english_label.click()
                else:
                    # Try any input with value containing en
                    en_input = await page.query_selector('input[type="radio"][value*="en" i], input[type="checkbox"][value*="en" i]')
                    if en_input:
                        await en_input.check()
            except Exception:
                pass

            # Save button
            try:
                save = await page.query_selector('button[data-uia*="save"], button:has-text("Save"), input[type="submit"]')
                if save:
                    await save.click()
                    await page.wait_for_timeout(1500)
            except Exception:
                pass

            # Verify again
            try:
                html_lang = await page.get_attribute("html", "lang")
                if html_lang and html_lang.startswith("en"):
                    logger.info("✅ Successfully set English (LanguagePreferences)")
                    return True
            except Exception:
                pass
        except Exception:
            # ignore and try next fallback
            pass

        # Fallback B: go via account profiles -> profile language settings
        try:
            await page.goto(PROFILES_URL, wait_until="domcontentloaded", timeout=TIMEOUT)
            await page.wait_for_load_state("networkidle", timeout=15000)
            await page.wait_for_timeout(1000)

            profile_selectors = [
                'button[data-uia*="menu-card"]:first-of-type',
                'li[data-uia*="menu-card"]:first-of-type button',
                'button[data-uia*="PressableListItem"]:first-of-type',
                '.profile-button:first-of-type',
                '.menu-card:first-of-type button'
            ]
            clicked = False
            for sel in profile_selectors:
                try:
                    el = await page.wait_for_selector(sel, timeout=4000)
                    if el:
                        await el.click()
                        await page.wait_for_load_state("networkidle", timeout=12000)
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                logger.error("❌ Could not open first profile")
                return False

            language_triggers = [
                '[data-uia*="languages"] button',
                '[data-uia*="language"] button',
                'button:has-text("Language")',
                'a[href*="language" i]'
            ]
            opened = False
            for sel in language_triggers:
                try:
                    el = await page.wait_for_selector(sel, timeout=4000)
                    if el:
                        await el.click()
                        await page.wait_for_load_state("networkidle", timeout=10000)
                        opened = True
                        break
                except Exception:
                    continue
            if not opened:
                logger.error("❌ Could not open language preferences from profile")
                return False

            # Try select and radio methods again
            try:
                dropdown = await page.query_selector('select, select[data-uia*="language"], select[name*="lang" i]')
                if dropdown:
                    for val in ["English", "en", "en-US", "en-GB"]:
                        try:
                            await dropdown.select_option(value=val)
                            break
                        except Exception:
                            continue
                label = await page.query_selector('label:has-text("English")')
                if label:
                    await label.click()
                else:
                    en_input = await page.query_selector('input[type="radio"][value*="en" i], input[type="checkbox"][value*="en" i]')
                    if en_input:
                        await en_input.check()
            except Exception:
                pass

            # Save
            try:
                save = await page.query_selector('button[data-uia*="save"], button:has-text("Save"), input[type="submit"]')
                if save:
                    await save.click()
                    await page.wait_for_timeout(1200)
            except Exception:
                pass

            # Verify
            try:
                html_lang = await page.get_attribute("html", "lang")
                if html_lang and html_lang.startswith("en"):
                    logger.info("✅ Successfully set English (profile path)")
                    return True
            except Exception:
                pass
        except Exception:
            pass

        logger.warning("⚠️ Could not confirm English language; proceeding anyway")
        return False
    except Exception as e:
        logger.error(f"❌ Error in language detection/change: {e}")
        return False

async def get_last_viewed_content(page) -> str:
    """Get the last viewed content from viewing activity"""
    try:
        logger.info("🔍 Fetching last viewed content...")
        
        # Go to viewing activity page
        await page.goto(VIEWING_ACTIVITY_URL, wait_until="domcontentloaded", timeout=TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(3000)
        
        # Try multiple selectors for viewing activity items
        activity_selectors = [
            '.retableRow:first-child .title',
            '.viewing-activity-item:first-child .title-name',
            'tr:first-child .title',
            '.activity-row:first-child .show-title',
            '[data-uia="viewing-activity-item"]:first-child .title',
            '.retableRow:first-child td:nth-child(1)',
            'tbody tr:first-child td:first-child'
        ]
        
        for selector in activity_selectors:
            try:
                last_viewed_element = await page.wait_for_selector(selector, timeout=5000)
                if last_viewed_element:
                    last_viewed = await last_viewed_element.inner_text()
                    if last_viewed and last_viewed.strip():
                        logger.info(f"✅ Found last viewed: {last_viewed.strip()}")
                        return last_viewed.strip()
            except Exception:
                continue
        
        # Try alternative approach - look for any title in viewing activity
        try:
            all_titles = await page.query_selector_all('.title, .show-title, .title-name')
            if all_titles:
                for title_element in all_titles[:3]:  # Check first 3 titles
                    title_text = await title_element.inner_text()
                    if title_text and title_text.strip():
                        logger.info(f"✅ Found viewing activity title: {title_text.strip()}")
                        return title_text.strip()
        except Exception:
            pass
            
        logger.warning("⚠️ No viewing activity found")
        return "No recent activity"
        
    except Exception as e:
        logger.error(f"❌ Error fetching last viewed content: {e}")
        return "Unable to fetch"

async def fetch_enhanced_account_details(cookies: List[Dict]) -> Optional[Dict]:
    """Fetch enhanced account details with comprehensive information"""
    logger.info(f"🔍 Starting enhanced account details extraction with {len(cookies)} cookies")
    
    async with async_playwright() as p:
        # LIVE BROWSER DEBUG MODE - Chromium Session (smaller window)
        # Early abort check
        global ABORT_REQUESTED
        ABORT_REQUESTED = False
        browser, context = await _ensure_chromium_and_launch(
            p,
            headless=True,
            slow_mo=0,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1200x800'
            ],
            viewport={'width': 1200, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        try:
            if ABORT_REQUESTED:
                await browser.close()
                return None
            await context.add_cookies(cookies)
            logger.info("✅ Cookies added to browser context")
        except Exception as e:
            logger.error(f"❌ Error adding cookies: {e}")
            await browser.close()
            return None
            
        page = await context.new_page()

        # Initialize enhanced account info
        account_info = {
            "email": "N/A",
            "phone_number": "N/A", 
            "plan": "N/A",
            "member_since": "N/A",
            "package": "N/A",
            "profile_name": "N/A",
            "service_code": "N/A",
            "email_verified": "❌ Non-verified",
            "phone_verified": "❌ Non-verified",
            "last_viewed": "Unable to fetch",
            "language": "N/A",
            "profiles_count": "N/A",
            "screenshot_path": None
        }

        try:
            # Check access first
            logger.info("🔍 Checking Netflix account access...")
            logger.debug("📱 LIVE DEBUG: Opening Netflix browse page...")
            if ABORT_REQUESTED:
                await browser.close()
                return None
            await page.goto(BROWSE_URL, wait_until="networkidle", timeout=TIMEOUT)
            logger.info(f"📍 Browse page loaded: {page.url}")
            
            # Take screenshot for debugging
            # optional screenshot disabled for server hygiene
            logger.debug("📸 Screenshot saved: debug_browse.png")
            
            logger.debug("📱 LIVE DEBUG: Navigating to account page...")
            if ABORT_REQUESTED:
                await browser.close()
                return None
            await page.goto(ACCOUNT_URL, wait_until="networkidle", timeout=TIMEOUT)
            logger.info(f"📍 Account page attempt: {page.url}")
            
            # Take screenshot of account page
            # optional screenshot disabled for server hygiene
            logger.debug("📸 Screenshot saved: debug_account.png")

            if not page.url.startswith(ACCOUNT_URL):
                logger.info("🔄 Not on account page, trying profile selection...")
                logger.debug("📱 LIVE DEBUG: Looking for profile selector...")
                try:
                    if ABORT_REQUESTED:
                        await browser.close()
                        return None
                    await page.wait_for_selector(PROFILE_SEL, timeout=8000)
                    logger.debug("📱 LIVE DEBUG: Profile selector found, clicking...")
                    if ABORT_REQUESTED:
                        await browser.close()
                        return None
                    await page.click(PROFILE_SEL, force=True)
                    # optional screenshot disabled for server hygiene
                    logger.debug("📸 Screenshot saved: debug_profile_click.png")

                    await page.wait_for_load_state("networkidle", timeout=TIMEOUT)
                    logger.debug("📱 LIVE DEBUG: Navigating back to account page...")
                    if ABORT_REQUESTED:
                        await browser.close()
                        return None
                    await page.goto(ACCOUNT_URL, wait_until="networkidle", timeout=TIMEOUT)
                    logger.info(f"📍 After profile selection: {page.url}")

                    await page.screenshot(path="debug_after_profile.png")
                    logger.debug("📸 Screenshot saved: debug_after_profile.png")
                except Exception as e:
                    logger.warning(f"⚠️ Profile selection failed: {e}")
                    # optional screenshot disabled for server hygiene
                    logger.debug("📸 Error screenshot saved: debug_profile_error.png")

            if not page.url.startswith(ACCOUNT_URL):
                logger.error(f"❌ Cannot access account page. Current URL: {page.url}")
                await browser.close()
                return None
            
            logger.info("✅ Successfully accessed Netflix account page")

            # Auto-change language to English if needed
            logger.debug("📱 LIVE DEBUG: Starting language detection and auto-change...")
            # optional screenshot disabled for server hygiene
            logger.debug("📸 Screenshot saved: debug_before_language.png")
            
            if ABORT_REQUESTED:
                await browser.close()
                return None
            await detect_and_change_language_to_english(page)
            
            # optional screenshot disabled for server hygiene
            logger.debug("📸 Screenshot saved: debug_after_language.png")

            # Get basic account details directly (avoid browser conflicts)
            try:
                # Get security information (email, phone, verification status)
                logger.debug("📱 LIVE DEBUG: Navigating to security page for email/phone extraction...")
                if ABORT_REQUESTED:
                    await browser.close()
                    return None
                await page.goto(SECURITY_URL, wait_until="networkidle", timeout=TIMEOUT)
                # optional screenshot disabled for server hygiene
                logger.debug("📸 Screenshot saved: debug_security.png")

                page_text = await page.inner_text("body")
                logger.debug(f"📱 LIVE DEBUG: Extracted page text length: {len(page_text)}")

                # Extract email
                email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", page_text)
                if email_match:
                    account_info["email"] = email_match.group(0)

                # Extract phone number with various formats
                phone_patterns = [
                    r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",  # US format
                    r"\+?\d{1,3}[-.\s]?\d{3,4}[-.\s]?\d{3,5}",  # International
                    r"\d{2}\s\d{8}",  # European format
                    r"\d{3}[-.\s]?\d{3}[-.\s]?\d{3}"  # Alternative format
                ]

                for pattern in phone_patterns:
                    phone_match = re.search(pattern, page_text)
                    if phone_match:
                        account_info["phone_number"] = phone_match.group(0).strip()
                        break

                # Check verification status
                page_lower = page_text.lower()
                verification_keywords = ["needs verification", "verify", "unverified", "verification required"]

                if any(keyword in page_lower for keyword in verification_keywords):
                    if account_info["email"] != "N/A":
                        account_info["email_verified"] = "❌ Non-verified"
                    if account_info["phone_number"] != "N/A":
                        account_info["phone_verified"] = "❌ Non-verified"
                else:
                    if account_info["email"] != "N/A":
                        account_info["email_verified"] = "✅ Verified"
                    if account_info["phone_number"] != "N/A":
                        account_info["phone_verified"] = "✅ Verified"

                # Get account overview information
                logger.debug("📱 LIVE DEBUG: Returning to account page for plan/payment extraction...")
                if ABORT_REQUESTED:
                    await browser.close()
                    return None
                await page.goto(ACCOUNT_URL, wait_until="networkidle", timeout=TIMEOUT)
                # optional screenshot disabled for server hygiene
                logger.debug("📸 Screenshot saved: debug_account_overview.png")

                # Extract plan information
                plan_selectors = [
                    'h3[data-uia="account-overview-page+membership-card+title"]',
                    '.plan-title',
                    '.membership-plan h3',
                    '[data-uia*="plan-title"]'
                ]

                for selector in plan_selectors:
                    try:
                        plan_element = await page.query_selector(selector)
                        if plan_element:
                            account_info["plan"] = (await plan_element.inner_text()).strip()
                            break
                    except Exception:
                        continue

                # Extract member since information
                member_selectors = [
                    'div[data-uia="account-overview-page+membership-card+plan-banner"]',
                    '.member-since',
                    '.membership-date',
                    '[data-uia*="member-since"]'
                ]

                for selector in member_selectors:
                    try:
                        member_element = await page.query_selector(selector)
                        if member_element:
                            member_text = (await member_element.inner_text()).strip()
                            account_info["member_since"] = member_text.replace("Member Since", "").strip()
                            break
                    except Exception:
                        continue

                # Enhanced package/payment method extraction
                payment_detail_selectors = [
                    '[data-uia*="payment+details"] span[data-uia*="mopType"]',
                    '[data-uia*="DIRECT_DEBIT"] span[data-uia*="mopType"]',
                    '[data-uia*="CREDIT_CARD"] span[data-uia*="mopType"]',
                    '[data-uia*="PAYPAL"] span[data-uia*="mopType"]',
                    'div[data-uia="account-overview-page+membership-card+payment"] p'
                ]

                for selector in payment_detail_selectors:
                    try:
                        payment_element = await page.query_selector(selector)
                        if payment_element:
                            payment_text = (await payment_element.inner_text()).strip()
                            # Clean up HTML entities and extra spaces
                            payment_text = payment_text.replace('&nbsp;', ' ').replace('\u00a0', ' ').replace('  ', ' ')
                            if payment_text and len(payment_text) > 3:
                                account_info["package"] = payment_text
                                logger.info(f"✅ Found payment method: {payment_text}")
                                break
                    except Exception:
                        continue

                # Get service code
                try:
                    service_code_button = await page.query_selector('button[data-uia="account+footer+service-code-button"]')
                    if service_code_button:
                        await service_code_button.click()
                        await page.wait_for_timeout(1000)
                        service_code_text = await service_code_button.inner_text()
                        if service_code_text and service_code_text.strip():
                            account_info["service_code"] = service_code_text.strip()
                except Exception:
                    pass

                # Get profile information
                if ABORT_REQUESTED:
                    await browser.close()
                    return None
                await page.goto(PROFILES_URL, wait_until="networkidle", timeout=TIMEOUT)

                # Get main profile name
                profile_selectors = [
                    'div[data-cl-view="accountProfileSettings"] p.e1tifjsj0',
                    '.profile-name',
                    '[data-uia*="profile"] p:first-child',
                    'button[data-uia*="menu-card"] p:first-child'
                ]

                for selector in profile_selectors:
                    try:
                        profile_element = await page.query_selector(selector)
                        if profile_element:
                            account_info["profile_name"] = (await profile_element.inner_text()).strip()
                            break
                    except Exception:
                        continue
                        
            except Exception as e:
                logger.error(f"Error extracting basic account details: {e}")

            # Get enhanced details
            try:
                # Get last viewed content
                account_info["last_viewed"] = await get_last_viewed_content(page)
                
                # Get profiles count
                await page.goto(PROFILES_URL, wait_until="networkidle", timeout=TIMEOUT)
                profile_count_elements = await page.query_selector_all('button[data-uia*="menu-card"]')
                if profile_count_elements:
                    account_info["profiles_count"] = str(len(profile_count_elements))
                
                # Get membership details
                if ABORT_REQUESTED:
                    await browser.close()
                    return None
                await page.goto(MEMBERSHIP_URL, wait_until="networkidle", timeout=TIMEOUT)
                
                # Skip payment and billing extraction - now handled in basic details as package
                
                # Get language from HTML
                html_lang = await page.get_attribute("html", "lang")
                if html_lang:
                    account_info["language"] = html_lang
                    
            except Exception as e:
                logger.error(f"Error getting enhanced details: {e}")

        except Exception as e:
            logger.error(f"Error in enhanced account details: {e}")

        # Final screenshot per account for on-demand preview
        # omit auto screenshots; we only take on-demand shots via capture_security_screenshot

        await browser.close()
        return account_info

async def sign_out_all_devices(cookies: List[Dict]) -> bool:
    """Sign out of all devices from the security page."""
    try:
        async with async_playwright() as p:
            browser, context = await _ensure_chromium_and_launch(p, headless=True)
            await context.add_cookies(cookies)
            page = await context.new_page()

            try:
                await page.goto(SECURITY_URL, wait_until="networkidle", timeout=TIMEOUT)
            except Exception:
                await browser.close()
                return False

            # Try multiple selectors/texts for "Sign out of all devices"
            selectors = [
                'button[data-uia*="sign-out-all"]',
                'button:has-text("Sign out of all devices")',
                'button:has-text("Sign out")',
                'a:has-text("Sign out of all devices")',
            ]

            clicked = False
            for selector in selectors:
                try:
                    el = await page.query_selector(selector)
                    if el:
                        await el.click()
                        clicked = True
                        break
                except Exception:
                    continue

            # If not found by selector, try text search fallback
            if not clicked:
                try:
                    all_buttons = await page.query_selector_all('button, a')
                    for btn in all_buttons:
                        text = (await btn.inner_text()).lower()
                        if "sign out" in text and ("all" in text or "devices" in text):
                            await btn.click()
                            clicked = True
                            break
                except Exception:
                    pass

            if not clicked:
                await browser.close()
                return False

            # Confirm dialog if any
            try:
                confirm_selectors = [
                    'button:has-text("Sign out")',
                    'button:has-text("Confirm")',
                    'button[data-uia*="confirm"]',
                    'button[aria-label*="confirm"]'
                ]
                for selector in confirm_selectors:
                    try:
                        conf = await page.query_selector(selector)
                        if conf:
                            await conf.click()
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            await page.wait_for_timeout(1500)
            await browser.close()
            return True
    except Exception as e:
        logger.error(f"Error in sign_out_all_devices: {e}")
        return False

async def sign_out_via_manage_devices(cookies: List[Dict]) -> bool:
    """Open Manage Devices and click the Sign Out button.

    This signs out the current device/session per Netflix UI.
    Returns True if the click action succeeded.
    """
    try:
        async with async_playwright() as p:
            browser, context = await _ensure_chromium_and_launch(
                p, headless=True, viewport={"width": 1200, "height": 800}
            )
            await context.add_cookies(cookies)
            page = await context.new_page()

            try:
                await page.goto("https://www.netflix.com/ManageDevices", wait_until="networkidle", timeout=TIMEOUT)
            except Exception:
                await browser.close()
                return False

            # Wait for sign-out button and click it
            try:
                # Prefer Netflix data-uia attribute
                btn = await page.wait_for_selector('[data-uia="btn-sign-out"]', timeout=6000)
                if btn:
                    await btn.click()
                else:
                    # Fallback by text
                    await page.click('button:has-text("Sign Out")')
            except Exception:
                # Try text fallback if data-uia failed
                try:
                    await page.click('button:has-text("Sign Out")')
                except Exception:
                    await browser.close()
                    return False

            # Optional: wait a moment for completion
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
                await page.wait_for_timeout(800)
            except Exception:
                pass

            await browser.close()
            return True
    except Exception as e:
        logger.error(f"Error in sign_out_via_manage_devices: {e}")
        return False
async def capture_security_screenshot(cookies: List[Dict], width: int = 1200, height: int = 800, email_hint: Optional[str] = None) -> Optional[str]:
    """Open Security page and capture from top of page down to the Mobile phone block.

    The viewport is adjusted to clip from y=0 to just below the Mobile phone section for a tall, top-aligned screenshot.
    Returns the saved screenshot path, or None on failure.
    """
    try:
        async with async_playwright() as p:
            browser, context = await _ensure_chromium_and_launch(
                p, headless=True, viewport={"width": width, "height": height}
            )
            await context.add_cookies(cookies)
            page = await context.new_page()

            try:
                # Attempt to go directly, handle profile selection if needed
                await page.goto(SECURITY_URL, wait_until="networkidle", timeout=TIMEOUT)
                if not page.url.startswith(SECURITY_URL):
                    # Try profile select then navigate again
                    try:
                        await page.wait_for_selector(PROFILE_SEL, timeout=6000)
                        await page.click(PROFILE_SEL, force=True)
                        await page.wait_for_load_state("networkidle", timeout=TIMEOUT)
                        await page.goto(SECURITY_URL, wait_until="networkidle", timeout=TIMEOUT)
                    except Exception:
                        pass

                # If still not on security, try account and then security
                if not page.url.startswith(SECURITY_URL):
                    try:
                        await page.goto(ACCOUNT_URL, wait_until="networkidle", timeout=TIMEOUT)
                        await page.goto(SECURITY_URL, wait_until="networkidle", timeout=TIMEOUT)
                    except Exception:
                        pass

                if not page.url.startswith(SECURITY_URL):
                    await browser.close()
                    return None

                # Small delay to allow dynamic sections
                await page.wait_for_timeout(600)

                # Compute a clip from top to the Mobile phone area
                # Build filename from email if possible
                path = None
                page_text = None
                try:
                    page_text = await page.inner_text('body')
                except Exception:
                    pass

                extracted_email = None
                if page_text:
                    try:
                        m = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", page_text)
                        if m:
                            extracted_email = m.group(0)
                    except Exception:
                        pass

                chosen_email = (email_hint or extracted_email or f"nf_{uuid.uuid4().hex}")
                safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", chosen_email)
                if not safe_name.lower().endswith('.png'):
                    safe_name = f"{safe_name}.png"
                path = safe_name

                # Primary label and helper text
                phone_label = page.locator("text=Mobile phone").first
                helper_text = page.locator("text=Add a phone number").first

                bbox_main = None
                bbox_helper = None
                try:
                    await phone_label.wait_for(state="visible", timeout=3000)
                    bbox_main = await phone_label.bounding_box()
                except Exception:
                    pass

                try:
                    bbox_helper = await helper_text.bounding_box()
                except Exception:
                    pass

                # If we found the label, compute clip from top (0) to below the phone area
                if bbox_main:
                    vp_w = width
                    top_y = 0
                    bottom_y = (bbox_helper["y"] + bbox_helper["height"] + 24) if bbox_helper else (bbox_main["y"] + bbox_main["height"] + 48)
                    clip = {
                        "x": 16,
                        "y": top_y,
                        "width": max(200, vp_w - 32),
                        "height": max(120, bottom_y - top_y)
                    }
                    await page.screenshot(path=path, clip=clip)
                else:
                    # Fallback: top-of-page to a default height if label not found
                    await page.screenshot(path=path, clip={"x": 16, "y": 0, "width": max(200, width-32), "height": min(height, 600)})

                await browser.close()
                return path
            except Exception:
                await browser.close()
                return None
    except Exception as e:
        logger.error(f"Error in capture_security_screenshot: {e}")
        return None

async def fetch_service_code_only(cookies: List[Dict]) -> Optional[str]:
    """Navigate to account page and retrieve a fresh service code only.

    Returns the service code string or None.
    """
    try:
        async with async_playwright() as p:
            browser, context = await _ensure_chromium_and_launch(
                p, headless=True, viewport={"width": 1024, "height": 720}
            )
            await context.add_cookies(cookies)
            page = await context.new_page()
            try:
                await page.goto(ACCOUNT_URL, wait_until="networkidle", timeout=TIMEOUT)
                btn = await page.query_selector('button[data-uia="account+footer+service-code-button"]')
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(600)
                    text = await btn.inner_text()
                    await browser.close()
                    return text.strip() if text else None
            except Exception:
                pass
            await browser.close()
            return None
    except Exception as e:
        logger.error(f"Error in fetch_service_code_only: {e}")
        return None