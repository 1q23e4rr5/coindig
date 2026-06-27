import sqlite3
import hashlib
from datetime import datetime
import json
import os

DB_PATH = 'crypto_platform.db'

def get_db():
    """دریافت اتصال به دیتابیس"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    """هش کردن رمز عبور با SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    """ایجاد جداول دیتابیس"""
    conn = get_db()
    cursor = conn.cursor()
    
    # جدول کاربران
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            user_type TEXT DEFAULT 'simple',
            status TEXT DEFAULT 'active',
            full_name TEXT,
            email TEXT,
            phone TEXT,
            created_at TEXT,
            last_login TEXT,
            login_count INTEGER DEFAULT 0,
            referral_code TEXT,
            referred_by TEXT,
            portfolio TEXT DEFAULT '{}'
        )
    ''')
    
    # جدول تاریخچه چت
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            response TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # جدول پیام‌های ادمین
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            created_at TEXT,
            from_admin INTEGER DEFAULT 0,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # جدول کدهای معرف
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referral_codes (
            code TEXT PRIMARY KEY,
            type TEXT DEFAULT 'normal',
            created_by TEXT,
            created_at TEXT,
            is_active INTEGER DEFAULT 1,
            max_uses INTEGER DEFAULT 5
        )
    ''')
    
    # جدول استفاده از کدهای معرف
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referral_uses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            user_id INTEGER,
            used_at TEXT,
            FOREIGN KEY (code) REFERENCES referral_codes (code),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # جدول درخواست‌ها
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            email TEXT,
            phone TEXT,
            referral_code TEXT,
            requested_user_type TEXT DEFAULT 'simple',
            status TEXT DEFAULT 'pending',
            is_pinned INTEGER DEFAULT 0,
            created_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# ============================================================
# توابع کاربران
# ============================================================

def create_user(username, password, user_type='simple', full_name='', email='', phone='', referral_code=''):
    """ایجاد کاربر جدید با رمز ساده (هش می‌شود)"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        hashed_password = hash_password(password)
        
        cursor.execute('''
            INSERT INTO users (username, password, user_type, full_name, email, phone, 
                               referral_code, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, hashed_password, user_type, full_name, email, phone, 
              referral_code, datetime.now().isoformat(), 'active'))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def create_user_with_hashed_password(username, hashed_password, user_type='simple', full_name='', email='', phone='', referral_code=''):
    """ایجاد کاربر با رمز هش شده (برای تایید درخواست)"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO users (username, password, user_type, full_name, email, phone, 
                               referral_code, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, hashed_password, user_type, full_name, email, phone, 
              referral_code, datetime.now().isoformat(), 'active'))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def get_user_by_username(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_id(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def update_user(user_id, **kwargs):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    for key, value in kwargs.items():
        if key in columns:
            if key == 'password':
                value = hash_password(value)
            cursor.execute(f'UPDATE users SET {key} = ? WHERE id = ?', (value, user_id))
    
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
    users = cursor.fetchall()
    conn.close()
    return [dict(user) for user in users]

def delete_user(username):
    user = get_user_by_username(username)
    if user:
        update_user(user['id'], status='deleted')
        return True
    return False

# ============================================================
# توابع تاریخچه چت
# ============================================================

def add_chat_history(user_id, message, response):
    """افزودن به تاریخچه چت"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO chat_history (user_id, message, response, created_at)
        VALUES (?, ?, ?, ?)
    ''', (user_id, message, response, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_chat_history(user_id, limit=50):
    """دریافت تاریخچه چت"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM chat_history WHERE user_id = ? 
        ORDER BY created_at DESC LIMIT ?
    ''', (user_id, limit))
    history = cursor.fetchall()
    conn.close()
    return [dict(h) for h in history]

# ============================================================
# توابع درخواست‌ها
# ============================================================

def create_request(username, password, full_name='', email='', phone='', referral_code='', requested_user_type='simple'):
    """ایجاد درخواست ثبت‌نام (رمز هش می‌شود)"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        hashed_password = hash_password(password)
        
        cursor.execute('''
            INSERT INTO requests (username, password, full_name, email, phone, referral_code, 
                                   requested_user_type, created_at, status, is_pinned)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, hashed_password, full_name, email, phone, referral_code,
              requested_user_type, datetime.now().isoformat(), 'pending', 1 if referral_code else 0))
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return request_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def get_pending_requests():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM requests WHERE status = "pending" ORDER BY is_pinned DESC, created_at ASC')
    requests = cursor.fetchall()
    conn.close()
    return [dict(req) for req in requests]

def approve_request(request_id):
    """تایید درخواست - رمز قبلاً هش شده است، دوباره هش نمی‌شود"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM requests WHERE id = ?', (request_id,))
    req = cursor.fetchone()
    
    if not req:
        conn.close()
        return None
    
    req = dict(req)
    
    user_id = create_user_with_hashed_password(
        username=req['username'],
        hashed_password=req['password'],
        user_type=req['requested_user_type'],
        full_name=req['full_name'],
        email=req['email'],
        phone=req['phone'],
        referral_code=req['referral_code']
    )
    
    if user_id:
        cursor.execute('UPDATE requests SET status = "approved" WHERE id = ?', (request_id,))
        conn.commit()
        conn.close()
        return user_id
    
    conn.close()
    return None

def reject_request(request_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE requests SET status = "rejected" WHERE id = ?', (request_id,))
    conn.commit()
    conn.close()

def update_request_type(request_id, user_type):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE requests SET requested_user_type = ? WHERE id = ?', (user_type, request_id))
    conn.commit()
    conn.close()

# ============================================================
# توابع پیام‌ها
# ============================================================

def add_admin_message(user_id, message, from_admin=0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO admin_messages (user_id, message, created_at, from_admin, is_read)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, message, datetime.now().isoformat(), from_admin, 0))
    conn.commit()
    conn.close()

def get_user_messages(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM admin_messages WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (user_id,))
    messages = cursor.fetchall()
    conn.close()
    return [dict(msg) for msg in messages]

def get_all_messages_for_admin():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT users.username, users.user_type, admin_messages.* 
        FROM admin_messages 
        JOIN users ON admin_messages.user_id = users.id 
        ORDER BY admin_messages.created_at DESC
    ''')
    messages = cursor.fetchall()
    conn.close()
    return [dict(msg) for msg in messages]

# ============================================================
# توابع کدهای معرف
# ============================================================

def create_referral_code(code, code_type='normal', created_by='admin', max_uses=5):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO referral_codes (code, type, created_by, created_at, max_uses)
            VALUES (?, ?, ?, ?, ?)
        ''', (code, code_type, created_by, datetime.now().isoformat(), max_uses))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def get_referral_codes():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM referral_codes ORDER BY created_at DESC')
    codes = cursor.fetchall()
    conn.close()
    return [dict(code) for code in codes]

def get_referral_code(code):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM referral_codes WHERE code = ?', (code,))
    result = cursor.fetchone()
    conn.close()
    return dict(result) if result else None

def use_referral_code(code, user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) as count FROM referral_uses WHERE code = ?', (code,))
    count = cursor.fetchone()['count']
    
    cursor.execute('SELECT max_uses FROM referral_codes WHERE code = ?', (code,))
    max_uses = cursor.fetchone()['max_uses']
    
    if count >= max_uses:
        conn.close()
        return False
    
    cursor.execute('INSERT INTO referral_uses (code, user_id, used_at) VALUES (?, ?, ?)',
                   (code, user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

# ============================================================
# راه‌اندازی
# ============================================================

if __name__ == '__main__':
    init_db()
    print("✅ دیتابیس با موفقیت ایجاد شد!")