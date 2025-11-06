# Simplified bot with web-login helpers (see earlier assistant message for fuller variants)
import os, asyncio, json, pytz, uuid
from datetime import datetime, timedelta
from telethon import TelegramClient, events as tg_events
from threading import Thread
from anthropic import Anthropic

from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError

API_ID = int(os.environ.get('TELEGRAM_API_ID', '0'))
API_HASH = os.environ.get('TELEGRAM_API_HASH', '')
PHONE = os.environ.get('TELEGRAM_PHONE', '')
GROUP_ID = int(os.environ.get('TELEGRAM_GROUP_ID', '0'))

BD_TZ = pytz.timezone('Asia/Dhaka')

loaded_events = []
logs = []
telegram_loop = None
client_username = ''

def log(msg):
    timestamp = datetime.now(BD_TZ).strftime('%Y-%m-%d %H:%M:%S')
    entry = f'[{timestamp}] {msg}'
    logs.append(entry)
    with open('bot_logs.txt', 'a', encoding='utf-8') as f:
        f.write(entry + '\n')

# minimal data loaders
def load_all_data():
    global loaded_events
    if os.path.exists('events.json'):
        try:
            with open('events.json', 'r', encoding='utf-8') as f:
                loaded_events = json.load(f)
        except:
            loaded_events = []

# Web login helpers
login_sessions = {}

async def start_telegram_login_web(phone, app, session_name_prefix='web_login'):
    if not API_ID or not API_HASH:
        raise RuntimeError('Missing TELEGRAM_API_ID or TELEGRAM_API_HASH on server.')
    session_id = uuid.uuid4().hex
    session_name = f'{session_name_prefix}_{session_id}'
    client = TelegramClient(session_name, API_ID, API_HASH)
    await client.connect()
    try:
        phone_code = await client.send_code_request(phone)
        phone_code_hash = getattr(phone_code, 'phone_code_hash', None)
        login_sessions[session_id] = {
            'client': client,
            'phone': phone,
            'phone_code_hash': phone_code_hash,
            'session_name': session_name,
            'created_at': datetime.now(BD_TZ).isoformat()
        }
        log(f'Started web login for {phone} session {session_id}')
        return session_id
    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        log(f'web login start error: {e}')
        raise

async def verify_telegram_code_web(session_id, code, app, password=None):
    info = login_sessions.get(session_id)
    if not info:
        raise RuntimeError('Invalid or expired login session id.')
    client = info['client']
    phone = info['phone']
    try:
        try:
            await client.sign_in(phone=phone, code=code)
        except TypeError:
            await client.sign_in(phone=phone, code=code, phone_code_hash=info.get('phone_code_hash'))
    except SessionPasswordNeededError:
        if password:
            await client.sign_in(password=password)
        else:
            raise SessionPasswordNeededError('2FA required. Provide password.')
    except PhoneCodeInvalidError:
        raise PhoneCodeInvalidError('Invalid code.')
    except PhoneCodeExpiredError:
        raise PhoneCodeExpiredError('Code expired.')
    # finalize: ensure authorized and store in app
    if not await client.is_user_authorized():
        raise RuntimeError('Sign-in did not complete.')
    app.config['telegram_client'] = client
    global telegram_loop, client_username
    try:
        me = await client.get_me()
        client_username = me.username.lower() if me.username else ''
    except:
        client_username = ''
    try:
        telegram_loop = asyncio.get_running_loop()
    except:
        telegram_loop = None
    # start scheduler if available
    try:
        client.loop.create_task(periodic_scheduler(app))
    except Exception as e:
        log(f'could not start scheduler on client loop: {e}')
    login_sessions.pop(session_id, None)
    log('Telegram login via dashboard successful.')
    return True

async def start_telegram_client(app):
    global client_username, telegram_loop
    if not API_ID or not API_HASH or not PHONE:
        log('Missing Telegram credentials; cannot auto-start client.')
        return
    client = TelegramClient('crypto_session', API_ID, API_HASH)
    await client.start(phone=PHONE)
    me = await client.get_me()
    client_username = me.username.lower() if me.username else ''
    app.config['telegram_client'] = client
    telegram_loop = asyncio.get_running_loop()
    load_all_data()
    client.loop.create_task(periodic_scheduler(app))
    await client.run_until_disconnected()

def run_telegram(app):
    asyncio.run(start_telegram_client(app))

def start_bot(app):
    t = Thread(target=run_telegram, args=(app,), daemon=True)
    t.start()
    log('Telegram bot thread started.')

# minimal periodic scheduler (placeholder)
async def periodic_scheduler(app):
    while True:
        try:
            # placeholder: could send scheduled events
            await asyncio.sleep(60)
        except Exception as e:
            log(f'scheduler error: {e}')
            await asyncio.sleep(60)
