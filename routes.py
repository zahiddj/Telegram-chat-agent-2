from flask import request, render_template, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from app import app, db
from replit_auth import require_login, make_replit_blueprint
import bot, asyncio

replit_bp = make_replit_blueprint()
app.register_blueprint(replit_bp, url_prefix='/auth')

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route('/')
@require_login
def index():
    status = bot.get_system_status(app) if hasattr(bot, 'get_system_status') else {'telegram_connected': False, 'bot_username': 'Not connected', 'ai_available': False, 'ai_enabled': False}
    return render_template('index.html', events=getattr(bot, 'loaded_events', []), manual_news=getattr(bot, 'loaded_manual_news', []), config=getattr(bot, 'bot_config', {}), status=status)

@app.route('/telegram/login', methods=['GET', 'POST'])
@require_login
def telegram_login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        if not phone:
            flash('Phone number is required.', 'error')
            return redirect(url_for('telegram_login'))
        try:
            if bot.telegram_loop:
                future = asyncio.run_coroutine_threadsafe(bot.start_telegram_login_web(phone, app), bot.telegram_loop)
                session_id = future.result(timeout=20)
            else:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                session_id = loop.run_until_complete(bot.start_telegram_login_web(phone, app))
                loop.close()
            flash('Code sent to phone. Enter it on the next screen.', 'success')
            return redirect(url_for('telegram_verify', session_id=session_id))
        except Exception as e:
            flash(f'Failed to start Telegram login: {e}', 'error')
            return redirect(url_for('telegram_login'))
    return render_template('telegram_login.html')

@app.route('/telegram/verify', methods=['GET', 'POST'])
@require_login
def telegram_verify():
    session_id = request.args.get('session_id') or request.form.get('session_id')
    if not session_id:
        flash('Missing login session. Start login first.', 'error')
        return redirect(url_for('telegram_login'))
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        password = request.form.get('password', '').strip() or None
        if not code:
            flash('Please provide the verification code.', 'error')
            return redirect(url_for('telegram_verify', session_id=session_id))
        try:
            if bot.telegram_loop:
                future = asyncio.run_coroutine_threadsafe(bot.verify_telegram_code_web(session_id, code, app, password), bot.telegram_loop)
                result = future.result(timeout=30)
            else:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(bot.verify_telegram_code_web(session_id, code, app, password))
                loop.close()
            if result:
                flash('Telegram login successful — bot connected.', 'success')
                return redirect(url_for('index'))
            else:
                flash('Telegram login did not complete. Check logs.', 'error')
                return redirect(url_for('telegram_login'))
        except Exception as e:
            flash(f'Verification failed: {e}', 'error')
            return redirect(url_for('telegram_verify', session_id=session_id))
    return render_template('telegram_verify.html', session_id=session_id)
