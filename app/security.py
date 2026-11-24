"""Session authentication and request protection for JalaTantra."""
import hashlib
import hmac
import secrets
import traceback
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from flask import g, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

import db

COOKIE = 'jalatantra_session'
SESSION_SECONDS = 8 * 60 * 60
DUMMY_HASH = generate_password_hash('not-a-user-' + secrets.token_urlsafe(32), method='scrypt')


class APIError(Exception):
    def __init__(self, message, status=400, headers=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.headers = headers or {}


def fail(message, status=400, headers=None):
    raise APIError(message, status, headers)


def payload(allowed, required=()):
    if not request.is_json:
        fail('Gunakan Content-Type application/json.', 415)
    if not allowed and not required and not request.get_data(cache=True):
        return {}
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        fail('Isi JSON harus berupa objek.')
    if set(value) - set(allowed):
        fail('Kolom tidak dikenal atau tidak dapat diubah.')
    if set(required) - set(value):
        fail('Kolom wajib belum lengkap.')
    return value


def text(value, label, maximum, minimum=0, strip=True):
    if not isinstance(value, str):
        fail(label + ' tidak valid.')
    value = value.strip() if strip else value
    if not minimum <= len(value) <= maximum or '\x00' in value:
        fail(label + ' tidak valid.')
    return value


def require_operator():
    if g.user['role'] not in ('admin', 'operator'):
        fail('Akses hanya untuk operator atau admin.', 403)


def require_admin():
    if g.user['role'] != 'admin':
        fail('Persetujuan hanya untuk admin.', 403)


def audit(cursor, action, environment, detail, device_id=None, actor=None):
    cursor.execute(
        'INSERT INTO audit_events(actor,action,environment,detail,device_id) VALUES(%s,%s,%s,%s,%s)',
        (actor if actor is not None else g.user['username'], action, environment, detail[:1000], device_id),
    )


def same_origin():
    if request.headers.get('Sec-Fetch-Site', '').lower() == 'cross-site':
        fail('Permintaan harus berasal dari situs yang sama.', 403)
    origin = request.headers.get('Origin')
    if origin is None:
        return
    try:
        source = urlsplit(origin)
        target = urlsplit(request.host_url)
        def identity(url):
            return url.scheme.lower(), url.hostname, url.port or (443 if url.scheme == 'https' else 80)
        valid = (source.scheme in ('http', 'https') and not source.username and not source.password
                 and not source.path and not source.query and not source.fragment
                 and identity(source) == identity(target))
    except ValueError:
        valid = False
    if not valid:
        fail('Asal permintaan tidak diizinkan.', 403)


def session_view():
    return {'user': {key: g.user[key] for key in ('id', 'username', 'role')},
            'csrf_token': g.csrf_token}


def token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def login():
    data = payload(('username', 'password'), ('username', 'password'))
    username = text(data['username'], 'Nama pengguna', 80, 1)
    password = text(data['password'], 'Kata sandi', 1024, 1, strip=False)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    error = None
    with db.connection() as client, client.cursor() as cursor:
        # Lock the account as well as the limiter, including case-insensitive aliases.
        cursor.execute('SELECT id,username,role,password_hash FROM users WHERE username=%s FOR UPDATE', (username,))
        user = cursor.fetchone()
        canonical_name = user['username'] if user else username.casefold()
        identity = token_hash((request.remote_addr or '') + '\x00' + canonical_name)
        cursor.execute('INSERT IGNORE INTO login_attempts(identity_hash,attempts,window_start) VALUES(%s,%s,%s)',
                       (identity, 0, now))
        cursor.execute('SELECT attempts,window_start FROM login_attempts WHERE identity_hash=%s FOR UPDATE', (identity,))
        attempt = cursor.fetchone()
        failures = attempt['attempts'] if attempt['window_start'] > now - timedelta(minutes=15) else 0
        start = attempt['window_start'] if failures else now
        if failures >= 5:
            error = ('Terlalu banyak percobaan. Coba lagi setelah 15 menit.', 429)
        else:
            password_ok = check_password_hash(user['password_hash'] if user else DUMMY_HASH, password)
            valid = password_ok and user is not None and not user.get('disabled', 0)
            if not valid or user is None:
                cursor.execute('UPDATE login_attempts SET attempts=%s,window_start=%s WHERE identity_hash=%s',
                               (failures + 1, start, identity))
                error = ('Nama pengguna atau kata sandi salah.', 401)
            else:
                cursor.execute('DELETE FROM login_attempts WHERE identity_hash=%s', (identity,))
                previous = request.cookies.get(COOKIE, '')
                if previous:
                    cursor.execute('DELETE FROM sessions WHERE token_hash=%s AND user_id=%s',
                                   (token_hash(previous), user['id']))
                cursor.execute('DELETE FROM sessions WHERE user_id=%s AND expires_at<=%s', (user['id'], now))
                cursor.execute('INSERT INTO sessions(token_hash,user_id,csrf_token,expires_at) VALUES(%s,%s,%s,%s)',
                               (token_hash(token), user['id'], csrf, now + timedelta(seconds=SESSION_SECONDS)))
                audit(cursor, 'login', 'system', 'Sesi masuk dibuat.', actor=user['username'])
    # A failed login must commit its limiter update, not roll it back with the error.
    if error:
        fail(*error)
    g.user, g.csrf_token = user, csrf
    response = jsonify(session_view())
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=bool(db.settings().get('cookie_secure', False)), samesite='Strict', path='/')
    return response


def logout():
    payload(())
    with db.connection() as client, client.cursor() as cursor:
        cursor.execute('DELETE FROM sessions WHERE token_hash=%s', (g.session_hash,))
        audit(cursor, 'logout', 'system', 'Sesi keluar.')
    response = jsonify({'ok': True})
    response.delete_cookie(COOKIE, path='/', httponly=True, samesite='Strict',
                           secure=bool(db.settings().get('cookie_secure', False)))
    return response


def change_password():
    data = payload(('current_password', 'new_password'), ('current_password', 'new_password'))
    current = text(data['current_password'], 'Kata sandi saat ini', 1024, 1, strip=False)
    new = text(data['new_password'], 'Kata sandi baru (minimal 12 karakter)', 1024, 12, strip=False)
    with db.connection() as client, client.cursor() as cursor:
        cursor.execute('SELECT password_hash FROM users WHERE id=%s FOR UPDATE', (g.user['id'],))
        user = cursor.fetchone()
        if not user or not check_password_hash(user['password_hash'], current):
            fail('Kata sandi saat ini salah.', 403)
        cursor.execute('UPDATE users SET password_hash=%s WHERE id=%s',
                       (generate_password_hash(new, method='scrypt'), g.user['id']))
        cursor.execute('DELETE FROM sessions WHERE user_id=%s AND token_hash<>%s',
                       (g.user['id'], g.session_hash))
        audit(cursor, 'password_changed', 'system', 'Kata sandi diubah; sesi lain dicabut.')
    return jsonify({'ok': True})


def install(app):
    app.config['MAX_CONTENT_LENGTH'] = 64 * 1024

    @app.before_request
    def protect():
        if request.content_length is not None and request.content_length > app.config['MAX_CONTENT_LENGTH']:
            fail('Isi permintaan terlalu besar.', 413)
        if not (request.path == '/api' or request.path.startswith('/api/')):
            return
        public = ((request.path == '/api/login' and request.method == 'POST')
                  or (request.path == '/api/health' and request.method in ('GET', 'HEAD')))
        if not public:
            token = request.cookies.get(COOKIE, '')
            if not token or len(token) > 128:
                fail('Silakan masuk terlebih dahulu.', 401)
            session = db.one(
                'SELECT u.id,u.username,u.role,s.csrf_token FROM sessions s JOIN users u ON u.id=s.user_id '
                'WHERE s.token_hash=%s AND s.expires_at>UTC_TIMESTAMP(6) AND u.disabled=0', (token_hash(token),))
            if not session:
                fail('Sesi berakhir. Silakan masuk kembali.', 401)
            g.user = {key: session[key] for key in ('id', 'username', 'role')}
            g.csrf_token, g.session_hash = session['csrf_token'], token_hash(token)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            same_origin()
            if not request.is_json:
                fail('Gunakan Content-Type application/json.', 415)
            if not public:
                csrf = request.headers.get('X-CSRF-Token', '')
                if not hmac.compare_digest(csrf.encode('utf-8'), g.csrf_token.encode('utf-8')):
                    fail('Token CSRF tidak valid. Muat ulang halaman.', 403)

    @app.after_request
    def headers(response):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        if request.path == '/api' or request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        elif request.path.startswith('/static/'):
            # Always revalidate so a deployed interface never calls an older API shape.
            response.headers['Cache-Control'] = 'no-cache'
        return response

    @app.errorhandler(APIError)
    def api_error(error):
        response = jsonify({'error': error.message})
        for name, value in error.headers.items():
            response.headers[name] = value
        if error.status == 429 and 'Retry-After' not in response.headers:
            response.headers['Retry-After'] = '900'
        return response, error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        messages = {400: 'Permintaan tidak valid.', 404: 'Data tidak ditemukan.',
                    405: 'Metode tidak diizinkan.', 413: 'Isi permintaan terlalu besar.',
                    415: 'Gunakan Content-Type application/json.'}
        return jsonify({'error': messages.get(error.code, 'Permintaan tidak dapat diproses.')}), error.code

    @app.errorhandler(Exception)
    def unexpected(error):
        if isinstance(error, db.pymysql.IntegrityError):
            return jsonify({'error': 'Data bertentangan dengan data yang sudah ada.'}), 409
        if isinstance(error, db.pymysql.OperationalError) and error.args and error.args[0] in (1205, 1213):
            return jsonify({'error': 'Data sedang berubah. Silakan coba kembali.'}), 409
        if isinstance(error, db.pymysql.MySQLError):
            return jsonify({'error': 'Database belum tersedia.'}), 503
        # Frames locate the failing line; the message is left out because it can
        # embed request data or connection details.
        frames = ''.join(traceback.format_tb(error.__traceback__)[-6:])
        app.logger.error('Permintaan gagal (%s) pada %s %s\n%s', type(error).__name__,
                         request.method, request.path[:120], frames)
        return jsonify({'error': 'Permintaan tidak dapat diproses.'}), 500
