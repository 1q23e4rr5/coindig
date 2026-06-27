from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from datetime import timedelta
import requests
import threading
import time
from datetime import datetime
import random
import string
import database as db
import json
import os
from functools import wraps

app = Flask(__name__)

# ============================================================
# بخش ۱: تنظیمات سشن و امنیت
# ============================================================

app.secret_key = 'crypto_pro_secret_key_2026_super_secure_!@#$%^&*()_+'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# ============================================================
# بخش ۲: تنظیمات و کانفیگ
# ============================================================

CONFIG_FILE = 'config.json'

DEFAULT_CONFIG = {
    'api_key': '010fc89b-8f88-4d84-8e3a-37cbb4d95fb9',
    'base_url': 'https://api.aki.io/v1',
    'model': 'gpt-4o-mini',
    'system_prompt': """شما یک تحلیلگر حرفه‌ای بازار ارزهای دیجیتال هستید.

📋 **دستورالعمل‌های کلی:**
- تحلیل خود را بر اساس داده‌های لحظه‌ای بازار ارائه دهید.
- پاسخ را به صورت ساختاریافته و با بندبندی منظم بنویسید.
- به ریسک‌های بازار اشاره کنید.

🎯 **برای تحلیل عمومی:**
بر اساس داده‌های ارائه شده، بهترین ارزها را برای سرمایه‌گذاری در ۵ بازه زمانی مختلف معرفی کنید.

📈 **برای تحلیل تکنیکال:**
بر اساس اندیکاتورها و الگوهای قیمتی، نقاط ورود و خروج مناسب را مشخص کنید.

📊 **برای تحلیل فاندامنتال:**
بر اساس ارزش ذاتی، تیم توسعه و کاربرد پروژه، تحلیل کنید."""
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# ============================================================
# بخش ۳: دکوریتورهای احراز هویت
# ============================================================

def login_required(f):
    """دکوریتور برای بررسی ورود کاربر"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'error': 'لطفاً وارد شوید'}), 401
        
        user = db.get_user_by_username(session['username'])
        if not user:
            session.clear()
            return jsonify({'error': 'کاربر یافت نشد'}), 401
        
        if user.get('status') == 'blocked':
            session.clear()
            return jsonify({'error': 'حساب کاربری شما مسدود شده است'}), 403
        
        if user.get('status') == 'deleted':
            session.clear()
            return jsonify({'error': 'حساب کاربری شما حذف شده است'}), 403
        
        session.permanent = True
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """دکوریتور برای بررسی نقش ادمین"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'error': 'لطفاً وارد شوید'}), 401
        
        user = db.get_user_by_username(session['username'])
        if not user or user.get('role') != 'admin':
            session.clear()
            return jsonify({'error': 'دسترسی غیرمجاز'}), 403
        
        session.permanent = True
        return f(*args, **kwargs)
    return decorated_function

# ============================================================
# بخش ۴: متغیرهای سراسری
# ============================================================

config = load_config()
API_KEY = config.get('api_key', DEFAULT_CONFIG['api_key'])
BASE_URL = config.get('base_url', DEFAULT_CONFIG['base_url'])
MODEL = config.get('model', DEFAULT_CONFIG['model'])
SYSTEM_PROMPT = config.get('system_prompt', DEFAULT_CONFIG['system_prompt'])

crypto_data = []
market_stats = {}
last_update = "در حال دریافت..."
fear_greed_data = {}

# ============================================================
# بخش ۵: دریافت داده از APIها
# ============================================================

def fetch_crypto_data():
    """دریافت داده‌های ارزهای دیجیتال از CoinGecko"""
    global crypto_data, market_stats, last_update
    
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': 50,
            'page': 1,
            'sparkline': 'false',
            'price_change_percentage': '1h,24h,7d'
        }
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            crypto_data = []
            
            for coin in data:
                try:
                    price = coin.get('current_price', 0)
                    price_str = f"${price:,.2f}" if price else "N/A"
                    
                    market_cap = coin.get('market_cap', 0)
                    market_cap_str = f"${market_cap:,.0f}" if market_cap else "N/A"
                    
                    volume = coin.get('total_volume', 0)
                    volume_str = f"${volume:,.0f}" if volume else "N/A"
                    
                    crypto_data.append({
                        'name': coin.get('name', 'N/A'),
                        'symbol': coin.get('symbol', '').upper(),
                        'price': price_str,
                        'change_1h': coin.get('price_change_percentage_1h_in_currency', 0) or 0,
                        'change_24h': coin.get('price_change_percentage_24h', 0) or 0,
                        'change_7d': coin.get('price_change_percentage_7d_in_currency', 0) or 0,
                        'market_cap': market_cap_str,
                        'volume': volume_str,
                        'image': coin.get('image', '')
                    })
                except:
                    continue
            
            if crypto_data:
                prices = []
                for coin in crypto_data:
                    try:
                        price_str = coin['price'].replace('$', '').replace(',', '')
                        prices.append(float(price_str))
                    except:
                        pass
                
                if prices:
                    market_stats = {
                        'total_coins': len(crypto_data),
                        'avg_price': sum(prices) / len(prices),
                        'max_price': max(prices),
                        'min_price': min(prices),
                        'top_gainer': max(crypto_data, key=lambda x: x.get('change_24h', 0)) if crypto_data else {},
                        'top_loser': min(crypto_data, key=lambda x: x.get('change_24h', 0)) if crypto_data else {}
                    }
                
                last_update = datetime.now().strftime("%H:%M:%S")
                
    except Exception as e:
        print(f"❌ Error fetching crypto data: {e}")

def fetch_fear_greed():
    """دریافت شاخص ترس و طمع از API"""
    global fear_greed_data
    
    try:
        url = "https://api.alternative.me/fng/"
        response = requests.get(url, timeout=10)
        
        print(f"📊 Fear & Greed API Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                fear_greed_data = {
                    'value': int(data['data'][0]['value']),
                    'classification': data['data'][0]['value_classification'],
                    'timestamp': data['data'][0]['timestamp'],
                    'time_until_update': data.get('time_until_update', '')
                }
                print(f"📊 Fear & Greed به‌روز شد: {fear_greed_data['value']}/100 - {fear_greed_data['classification']}")
            else:
                print("⚠️ داده ترس و طمع دریافت نشد")
        else:
            print(f"❌ خطا در دریافت ترس و طمع: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error fetching fear & greed: {e}")

def background_updater():
    """بروزرسانی خودکار داده‌ها در پس‌زمینه"""
    while True:
        fetch_crypto_data()
        fetch_fear_greed()
        time.sleep(60)

# ============================================================
# بخش ۶: ساخت پرامپت
# ============================================================

def build_market_summary():
    """ساخت خلاصه داده‌های بازار"""
    if not crypto_data:
        return "📊 داده‌های بازار در دسترس نیست.\n"
    
    categories = {'24h': [], '7d': [], '30d': [], '180d': [], '365d': []}
    
    for coin in crypto_data[:30]:
        if coin.get('change_24h', 0) > 5:
            categories['24h'].append(coin)
        if coin.get('change_7d', 0) > 10:
            categories['7d'].append(coin)
        if coin.get('change_7d', 0) > 20:
            categories['30d'].append(coin)
        if coin.get('change_7d', 0) > 50:
            categories['180d'].append(coin)
        if coin.get('change_7d', 0) > 100:
            categories['365d'].append(coin)
    
    market_summary = "📊 **داده‌های لحظه‌ای بازار:**\n\n"
    
    time_periods = [
        ("۲۴ ساعت گذشته (بیش از ۵%)", '24h'),
        ("هفته گذشته (بیش از ۱۰%)", '7d'),
        ("ماه گذشته (بیش از ۲۰%)", '30d'),
        ("شش ماه گذشته (بیش از ۵۰%)", '180d'),
        ("یک سال گذشته (بیش از ۱۰۰%)", '365d')
    ]
    
    for label, key in time_periods:
        market_summary += f"🔹 **ارزهای سودده در {label}:**\n"
        if categories[key]:
            for coin in categories[key][:5]:
                change_key = 'change_24h' if key == '24h' else 'change_7d'
                market_summary += f"   • {coin['name']}: +{coin[change_key]:.2f}% | قیمت: {coin['price']}\n"
        else:
            market_summary += "   • هیچ ارزی یافت نشد\n"
        market_summary += "\n"
    
    market_summary += f"📈 **آمار کلی بازار:**\n"
    market_summary += f"   • تعداد ارزها: {market_stats.get('total_coins', 0)}\n"
    market_summary += f"   • میانگین قیمت: ${market_stats.get('avg_price', 0):,.2f}\n"
    
    top_gainer = market_stats.get('top_gainer', {})
    if top_gainer:
        market_summary += f"   • بیشترین افزایش: {top_gainer.get('name', 'N/A')} (+{top_gainer.get('change_24h', 0):.2f}%)\n"
    
    return market_summary

def build_fear_greed_summary():
    """ساخت خلاصه شاخص ترس و طمع"""
    if not fear_greed_data:
        return ""
    return (
        f"\n📊 **شاخص ترس و طمع:**\n"
        f"   • مقدار: {fear_greed_data.get('value', 0)}/100\n"
        f"   • وضعیت: {fear_greed_data.get('classification', 'N/A')}\n"
    )

def build_advanced_prompt(user_query="", analysis_type="general"):
    """
    ساخت پرامپت بر اساس نوع تحلیل
    
    انواع تحلیل:
    - general: تحلیل عمومی
    - technical: تحلیل تکنیکال
    - fundamental: تحلیل فاندامنتال
    """
    
    market_summary = build_market_summary()
    fear_greed_summary = build_fear_greed_summary()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    full_market_summary = market_summary + fear_greed_summary
    
    print(f"🔍 نوع تحلیل انتخاب شده: {analysis_type}")
    
    # ============================================================
    # پرامپت‌های اختصاصی برای هر نوع تحلیل
    # ============================================================
    
    if analysis_type == "technical":
        system_prompt = """📈 **شما یک تحلیلگر تکنیکال حرفه‌ای هستید.**

🎯 **هدف:** تحلیل تکنیکال بازار ارزهای دیجیتال

📋 **دستورالعمل‌ها:**
۱. بر اساس داده‌های قیمت و تغییرات، تحلیل تکنیکال انجام دهید.
۲. به موارد زیر توجه کنید:
   - سطوح حمایت و مقاومت کلیدی
   - روندهای صعودی و نزولی
   - حجم معاملات و نقدینگی
   - اندیکاتورهای اصلی (RSI، MACD، میانگین متحرک)
   - الگوهای شمعی و شکست‌ها
۳. نقاط ورود و خروج مناسب را مشخص کنید.
۴. نسبت ریسک به ریوارد را محاسبه کنید.
۵. پاسخ را با بندبندی منظم به فارسی بنویسید.

⚠️ **تذکر:** این تحلیل صرفاً جنبه اطلاع‌رسانی دارد."""
        
        user_prompt = f"""📅 **زمان تحلیل تکنیکال:** {current_time}

{full_market_summary}

🎯 **درخواست:** {user_query if user_query else 'تحلیل تکنیکال بازار و معرفی بهترین نقاط ورود و خروج بر اساس اندیکاتورها'}

📊 **لطفاً تحلیل تکنیکال خود را با ساختار زیر ارائه دهید:**

۱️⃣ **بررسی کلی بازار** (روند کلی، حجم معاملات)
۲️⃣ **تحلیل اندیکاتورها** (RSI، MACD، میانگین متحرک)
۳️⃣ **سطوح کلیدی** (حمایت و مقاومت)
۴️⃣ **نقاط ورود و خروج** (با ذکر قیمت‌ها)
۵️⃣ **نسبت ریسک به ریوارد**
۶️⃣ **جمع‌بندی و توصیه‌ها**

⚠️ **تذکر:** این تحلیل صرفاً جنبه اطلاع‌رسانی دارد."""

    elif analysis_type == "fundamental":
        system_prompt = """📊 **شما یک تحلیلگر فاندامنتال حرفه‌ای هستید.**

🎯 **هدف:** تحلیل فاندامنتال بازار ارزهای دیجیتال

📋 **دستورالعمل‌ها:**
۱. بر اساس داده‌های بازار، تحلیل فاندامنتال انجام دهید.
۲. به موارد زیر توجه کنید:
   - تیم توسعه‌دهنده و سابقه پروژه
   - کاربرد و استفاده‌پذیری توکن
   - میزان پذیرش و همکاری‌های استراتژیک
   - رقبا و مزیت رقابتی
   - اخبار و رویدادهای مهم آینده
   - توکنومیک و توزیع توکن‌ها
   - جامعه کاربری و میزان فعالیت
۳. ارزش ذاتی هر پروژه را ارزیابی کنید.
۴. پتانسیل رشد بلندمدت را بررسی کنید.
۵. پاسخ را با بندبندی منظم به فارسی بنویسید.

⚠️ **تذکر:** این تحلیل صرفاً جنبه اطلاع‌رسانی دارد."""
        
        user_prompt = f"""📅 **زمان تحلیل فاندامنتال:** {current_time}

{full_market_summary}

🎯 **درخواست:** {user_query if user_query else 'تحلیل فاندامنتال بازار و معرفی بهترین پروژه‌ها برای سرمایه‌گذاری بلندمدت'}

📊 **لطفاً تحلیل فاندامنتال خود را با ساختار زیر ارائه دهید:**

۱️⃣ **بررسی کلی بازار** (وضعیت کلی، روندها)
۲️⃣ **تحلیل پروژه‌های برتر** (تیم، کاربرد، توکنومیک)
۳️⃣ **مقایسه با رقبا** (مزیت رقابتی)
۴️⃣ **اخبار و رویدادهای مهم**
۵️⃣ **ارزش‌گذاری** (ارزش ذاتی vs قیمت فعلی)
۶️⃣ **پتانسیل رشد** (کوتاه‌مدت و بلندمدت)
７️⃣ **جمع‌بندی و توصیه‌ها**

⚠️ **تذکر:** این تحلیل صرفاً جنبه اطلاع‌رسانی دارد."""

    else:  # general
        system_prompt = """📊 **شما یک تحلیلگر ارشد بازار ارزهای دیجیتال هستید.**

🎯 **هدف:** تحلیل جامع بازار و معرفی بهترین فرصت‌های سرمایه‌گذاری

📋 **دستورالعمل‌ها:**
۱. بر اساس داده‌های ارائه شده، ارزهایی را معرفی کنید.
۲. ارزها را در ۵ دسته زیر دسته‌بندی کنید:
   - دسته اول: سوددهی در ۲۴ ساعت (۵-۱۵٪)
   - دسته دوم: سوددهی در هفته (۱۵-۳۰٪)
   - دسته سوم: سوددهی در ماه (۳۰-۵۰٪)
   - دسته چهارم: سوددهی در شش ماه (۵۰-۱۰۰٪)
   - دسته پنجم: سوددهی در یک سال (بیش از ۱۰۰٪)
۳. برای هر ارز، دلیل انتخاب را ذکر کنید.
۴. پاسخ را با ساختار منظم بنویسید.

⚠️ """
        
        user_prompt = f"""📅 **زمان تحلیل عمومی:** {current_time}

{full_market_summary}

🎯 **درخواست:** {user_query if user_query else 'تحلیل جامع بازار و معرفی بهترین فرصت‌های سرمایه‌گذاری'}

📊 **لطفاً تحلیل جامع خود را با ساختار زیر ارائه دهید:**

۱️⃣ **بررسی کلی بازار** (وضعیت فعلی، روندها)
۲️⃣ **دسته‌بندی ارزهای پیشنهادی** (در ۵ بازه زمانی)
۳️⃣ **تحلیل هر ارز** (دلیل انتخاب، پتانسیل سود)
۴️⃣ **جدول خلاصه** (نام ارز، بازه زمانی، سود مورد انتظار)

"""
    
    print(f"📝 نوع پرامپت ساخته شده: {analysis_type}")
    
    return {
        'system': system_prompt,
        'user': user_prompt
    }

def call_ai_api(messages, temperature=0.7, max_tokens=400000):
    """ارسال درخواست به API"""
    global API_KEY, BASE_URL, MODEL
    
    try:
        headers = {
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': MODEL,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens
        }
        
        response = requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"من نمی توانم شما را کوچکترین اجباری کنم"
            
    except requests.exceptions.Timeout:
        return "❌ خطا: زمان اتصال به API به پایان رسید"
    except requests.exceptions.ConnectionError:
        return "❌ خطا: اتصال به سرور API برقرار نشد"
    except Exception as e:
        return f"❌ خطا: {str(e)}"

# ============================================================
# بخش ۷: مسیرهای اصلی
# ============================================================

@app.route('/')
def index():
    if 'username' in session:
        user = db.get_user_by_username(session['username'])
        if user and user.get('status') == 'active':
            session.permanent = True
            return render_template('index.html')
        else:
            session.clear()
            return redirect(url_for('login_page'))
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    if 'username' in session:
        user = db.get_user_by_username(session['username'])
        if user and user.get('status') == 'active':
            return redirect(url_for('index'))
        else:
            session.clear()
    return render_template('login.html')

@app.route('/register')
def register_page():
    if 'username' in session:
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/admin-panel')
def admin_panel():
    if 'username' not in session:
        return redirect(url_for('login_page'))
    
    user = db.get_user_by_username(session['username'])
    if not user or user.get('role') != 'admin':
        session.clear()
        return redirect(url_for('login_page'))
    
    if user.get('status') != 'active':
        session.clear()
        return redirect(url_for('login_page'))
    
    session.permanent = True
    return render_template('admin.html')

# ============================================================
# بخش ۸: API های احراز هویت
# ============================================================

@app.route('/api/auth/status')
def auth_status():
    """بررسی وضعیت ورود"""
    if 'username' in session:
        user = db.get_user_by_username(session['username'])
        if user and user.get('status') == 'active':
            session.permanent = True
            return jsonify({
                'logged_in': True,
                'username': user['username'],
                'role': user['role'],
                'user_type': user['user_type'],
                'user_data': {
                    'full_name': user.get('full_name', ''),
                    'email': user.get('email', ''),
                    'created_at': user.get('created_at', ''),
                    'last_login': user.get('last_login', ''),
                    'login_count': user.get('login_count', 0),
                    'user_type': user.get('user_type', 'simple')
                }
            })
    
    return jsonify({'logged_in': False})

@app.route('/api/auth/login', methods=['POST'])
def login():
    """ورود کاربر"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'error':'You should Enter user name and password'}), 400
        
        user = db.get_user_by_username(username)
        
        if not user:
            return jsonify({'error':'User name or password is wrong'}), 401
        
        if user['password'] != db.hash_password(password):
            return jsonify({'error': 'User name or password is wrong'}), 401
        
        if user.get('status') == 'blocked':
            return jsonify({'error': 'Sorry ! , you account was banned'}), 403
        
        if user.get('status') == 'deleted':
            return jsonify({'error': 'Your account was deleted '}), 403
        
        session['username'] = username
        session['user_id'] = user['id']
        session['role'] = user['role']
        session['user_type'] = user['user_type']
        session.permanent = True
        
        db.update_user(user['id'], last_login=datetime.now().isoformat(), login_count=user['login_count'] + 1)
        
        return jsonify({
            'success': True,
            'username': username,
            'role': user['role'],
            'user_type': user['user_type']
        })
        
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'خطا در ورود به سیستم'}), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    """ثبت‌نام کاربر جدید"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        full_name = data.get('full_name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        referral_code = data.get('referral_code', '').strip().upper()
        
        if not username or not password:
            return jsonify({'error': 'نام کاربری و رمز عبور الزامی است'}), 400
        
        if len(password) < 4:
            return jsonify({'error': 'رمز عبور باید حداقل ۴ کاراکتر باشد'}), 400
        
        if db.get_user_by_username(username):
            return jsonify({'error': 'این نام کاربری قبلاً ثبت شده است'}), 400
        
        user_type = 'simple'
        
        # بررسی کد معرف
        if referral_code:
            code_data = db.get_referral_code(referral_code)
            if code_data and code_data['is_active'] == 1:
                if code_data['type'] == 'golden':
                    user_type = 'premium'
                    user_id = db.create_user(username, password, user_type, full_name, email, phone, referral_code)
                    if user_id:
                        db.use_referral_code(referral_code, user_id)
                        return jsonify({
                            'success': True,
                            'username': username,
                            'user_type': user_type,
                            'direct': True
                        })
                elif code_data['type'] == 'normal':
                    user_type = 'custom'
        
        # ثبت درخواست
        request_id = db.create_request(username, password, full_name, email, phone, referral_code, user_type)
        
        if request_id:
            return jsonify({
                'success': True,
                'message': 'درخواست شما ثبت شد. منتظر تایید ادمین باشید.'
            })
        
        return jsonify({'error': 'خطا در ثبت درخواست'}), 400
        
    except Exception as e:
        print(f"Register error: {e}")
        return jsonify({'error': 'خطا در ثبت‌نام'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """خروج کاربر"""
    session.clear()
    return jsonify({'success': True})

# ============================================================
# بخش ۹: API های مدیریت کاربران
# ============================================================

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def get_users():
    """دریافت لیست کاربران"""
    users = db.get_all_users()
    return jsonify({'users': users})

@app.route('/api/admin/users/<username>/change-type', methods=['POST'])
@admin_required
def change_user_type(username):
    """تغییر نوع اکانت کاربر"""
    if username == 'admin':
        return jsonify({'error': 'نمی‌توان نوع اکانت ادمین را تغییر داد'}), 400
    
    user = db.get_user_by_username(username)
    if not user:
        return jsonify({'error': 'کاربر یافت نشد'}), 404
    
    data = request.get_json()
    new_type = data.get('user_type', 'simple')
    
    if new_type not in ['simple', 'custom', 'premium']:
        return jsonify({'error': 'نوع اکانت نامعتبر است'}), 400
    
    db.update_user(user['id'], user_type=new_type)
    
    return jsonify({'success': True, 'username': username, 'user_type': new_type})

@app.route('/api/admin/users/<username>/password', methods=['GET'])
@admin_required
def get_user_password(username):
    """نمایش هش رمز کاربر"""
    if username == 'admin':
        return jsonify({'error': 'نمی‌توان رمز ادمین را نمایش داد'}), 400
    
    user = db.get_user_by_username(username)
    if not user:
        return jsonify({'error': 'کاربر یافت نشد'}), 404
    
    return jsonify({
        'username': username,
        'password': user['password'],
        'password_hash': user['password']
    })

@app.route('/api/admin/users/<username>/password', methods=['PUT'])
@admin_required
def change_user_password(username):
    """تغییر رمز کاربر توسط ادمین"""
    if username == 'admin':
        return jsonify({'error': 'نمی‌توان رمز ادمین را تغییر داد'}), 400
    
    user = db.get_user_by_username(username)
    if not user:
        return jsonify({'error': 'کاربر یافت نشد'}), 404
    
    data = request.get_json()
    new_password = data.get('password', '').strip()
    
    if not new_password or len(new_password) < 4:
        return jsonify({'error': 'رمز باید حداقل ۴ کاراکتر باشد'}), 400
    
    db.update_user(user['id'], password=new_password)
    
    return jsonify({
        'success': True,
        'username': username,
        'message': 'رمز با موفقیت تغییر یافت'
    })

@app.route('/api/admin/users/<username>/block', methods=['POST'])
@admin_required
def block_user(username):
    """مسدود کردن کاربر"""
    if username == 'admin':
        return jsonify({'error': 'نمی‌توان ادمین را مسدود کرد'}), 400
    
    user = db.get_user_by_username(username)
    if not user:
        return jsonify({'error': 'کاربر یافت نشد'}), 404
    
    db.update_user(user['id'], status='blocked')
    return jsonify({'success': True})

@app.route('/api/admin/users/<username>/unblock', methods=['POST'])
@admin_required
def unblock_user(username):
    """رفع مسدودیت کاربر"""
    user = db.get_user_by_username(username)
    if not user:
        return jsonify({'error': 'کاربر یافت نشد'}), 404
    
    db.update_user(user['id'], status='active')
    return jsonify({'success': True})

@app.route('/api/admin/users/<username>/delete', methods=['DELETE'])
@admin_required
def delete_user(username):
    """حذف کاربر (غیرفعال کردن)"""
    if username == 'admin':
        return jsonify({'error': 'نمی‌توان ادمین را حذف کرد'}), 400
    
    user = db.get_user_by_username(username)
    if not user:
        return jsonify({'error': 'کاربر یافت نشد'}), 404
    
    db.update_user(user['id'], status='deleted')
    return jsonify({'success': True})

# ============================================================
# بخش ۱۰: API های درخواست‌ها
# ============================================================

@app.route('/api/admin/requests', methods=['GET'])
@admin_required
def get_requests():
    """دریافت درخواست‌های ثبت‌نام"""
    requests = db.get_pending_requests()
    return jsonify({'requests': requests})

@app.route('/api/admin/requests/<int:req_id>/approve', methods=['POST'])
@admin_required
def approve_request(req_id):
    """تایید درخواست"""
    user_id = db.approve_request(req_id)
    if user_id:
        return jsonify({'success': True})
    
    return jsonify({'error': 'خطا در تایید درخواست'}), 400

@app.route('/api/admin/requests/<int:req_id>/reject', methods=['POST'])
@admin_required
def reject_request(req_id):
    """رد درخواست"""
    db.reject_request(req_id)
    return jsonify({'success': True})

@app.route('/api/admin/requests/<int:req_id>/edit', methods=['POST'])
@admin_required
def edit_request(req_id):
    """ویرایش نوع اکانت درخواستی"""
    data = request.get_json()
    user_type = data.get('user_type', 'simple')
    
    db.update_request_type(req_id, user_type)
    return jsonify({'success': True})

# ============================================================
# بخش ۱۱: API های کدهای معرف
# ============================================================

@app.route('/api/admin/referral-codes', methods=['GET'])
@admin_required
def get_referral_codes():
    """دریافت کدهای معرف"""
    codes = db.get_referral_codes()
    return jsonify({'codes': codes})

@app.route('/api/admin/referral-codes/create', methods=['POST'])
@admin_required
def create_referral_code():
    """ایجاد کد معرف جدید"""
    data = request.get_json()
    code_type = data.get('type', 'normal')
    
    new_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    max_uses = 10 if code_type == 'golden' else 5
    
    success = db.create_referral_code(new_code, code_type, session['username'], max_uses)
    
    if success:
        return jsonify({'success': True, 'code': new_code, 'type': code_type})
    
    return jsonify({'error': 'خطا در ساخت کد'}), 400

@app.route('/api/admin/referral-codes/<code>/toggle', methods=['POST'])
@admin_required
def toggle_referral_code(code):
    """فعال/غیرفعال کردن کد معرف"""
    code_data = db.get_referral_code(code)
    if not code_data:
        return jsonify({'error': 'کد یافت نشد'}), 404
    
    new_status = 0 if code_data['is_active'] == 1 else 1
    
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE referral_codes SET is_active = ? WHERE code = ?', (new_status, code))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'is_active': new_status})

@app.route('/api/admin/referral-codes/<code>/delete', methods=['DELETE'])
@admin_required
def delete_referral_code(code):
    """حذف کد معرف"""
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM referral_codes WHERE code = ?', (code,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# ============================================================
# بخش ۱۲: API های پیام‌ها
# ============================================================

@app.route('/api/admin/messages', methods=['POST'])
@admin_required
def send_admin_message():
    """ارسال پیام از ادمین به کاربران"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        target = data.get('target_user', 'all')
        
        if not message:
            return jsonify({'error': 'پیام خالی است'}), 400
        
        users = db.get_all_users()
        sent_count = 0
        
        if target == 'all':
            for user in users:
                if user['username'] != 'admin' and user.get('status') == 'active':
                    db.add_admin_message(user['id'], message, from_admin=1)
                    sent_count += 1
        elif target == 'premium':
            for user in users:
                if user['user_type'] == 'premium' and user.get('status') == 'active':
                    db.add_admin_message(user['id'], message, from_admin=1)
                    sent_count += 1
        elif target == 'custom':
            for user in users:
                if user['user_type'] == 'custom' and user.get('status') == 'active':
                    db.add_admin_message(user['id'], message, from_admin=1)
                    sent_count += 1
        elif target == 'simple':
            for user in users:
                if user['user_type'] == 'simple' and user.get('status') == 'active':
                    db.add_admin_message(user['id'], message, from_admin=1)
                    sent_count += 1
        else:
            user = db.get_user_by_username(target)
            if not user:
                return jsonify({'error': 'کاربر یافت نشد'}), 404
            if user['username'] == 'admin':
                return jsonify({'error': 'نمی‌توان به ادمین پیام داد'}), 400
            db.add_admin_message(user['id'], message, from_admin=1)
            sent_count = 1
        
        return jsonify({
            'success': True,
            'message': f'✅ پیام با موفقیت به {sent_count} کاربر ارسال شد',
            'sent_count': sent_count
        })
        
    except Exception as e:
        print(f"Error sending admin message: {e}")
        return jsonify({'error': f'خطا در ارسال پیام: {str(e)}'}), 500

@app.route('/api/user/messages')
@login_required
def get_user_messages():
    """دریافت پیام‌های دریافتی کاربر"""
    try:
        user = db.get_user_by_username(session['username'])
        if not user:
            return jsonify({'error': 'کاربر یافت نشد'}), 404
        
        messages = db.get_user_messages(user['id'])
        return jsonify({'messages': messages})
        
    except Exception as e:
        print(f"Error getting user messages: {e}")
        return jsonify({'error': f'خطا در دریافت پیام‌ها: {str(e)}'}), 500

@app.route('/api/user/send-message', methods=['POST'])
@login_required
def send_user_message():
    """ارسال پیام از کاربر به ادمین (فقط سفارشی و اشرافی)"""
    user_type = session.get('user_type', 'simple')
    if user_type not in ['custom', 'premium']:
        return jsonify({'error': 'فقط کاربران سفارشی و اشرافی می‌توانند پیام ارسال کنند'}), 403
    
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'پیام خالی است'}), 400
        
        user = db.get_user_by_username(session['username'])
        if not user:
            return jsonify({'error': 'کاربر یافت نشد'}), 404
        
        db.add_admin_message(user['id'], message, from_admin=0)
        
        return jsonify({
            'success': True,
            'message': '✅ پیام شما با موفقیت ارسال شد',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"Error sending user message: {e}")
        return jsonify({'error': f'خطا در ارسال پیام: {str(e)}'}), 500

@app.route('/api/user/messages-history')
@login_required
def get_user_messages_history():
    """دریافت تاریخچه کامل پیام‌های کاربر"""
    try:
        user = db.get_user_by_username(session['username'])
        if not user:
            return jsonify({'error': 'کاربر یافت نشد'}), 404
        
        messages = db.get_user_messages(user['id'])
        messages.reverse()
        
        return jsonify({'messages': messages})
        
    except Exception as e:
        print(f"Error getting messages history: {e}")
        return jsonify({'error': f'خطا در دریافت تاریخچه: {str(e)}'}), 500

@app.route('/api/admin/user-messages', methods=['GET'])
@admin_required
def get_user_messages_for_admin():
    """دریافت تمام پیام‌های کاربران برای ادمین"""
    try:
        messages = db.get_all_messages_for_admin()
        return jsonify({'messages': messages})
        
    except Exception as e:
        print(f"Error getting user messages for admin: {e}")
        return jsonify({'error': f'خطا در دریافت پیام‌ها: {str(e)}'}), 500

@app.route('/api/admin/reply-message', methods=['POST'])
@admin_required
def admin_reply_message():
    """پاسخ ادمین به کاربر"""
    try:
        data = request.get_json()
        target_user = data.get('target_user', '').strip()
        message = data.get('message', '').strip()
        
        if not target_user or not message:
            return jsonify({'error': 'نام کاربری و پیام الزامی است'}), 400
        
        user = db.get_user_by_username(target_user)
        if not user:
            return jsonify({'error': 'کاربر یافت نشد'}), 404
        
        db.add_admin_message(user['id'], f"📨 پاسخ ادمین: {message}", from_admin=1)
        
        return jsonify({
            'success': True,
            'message': '✅ پاسخ با موفقیت ارسال شد'
        })
        
    except Exception as e:
        print(f"Error replying to user: {e}")
        return jsonify({'error': f'خطا در ارسال پاسخ: {str(e)}'}), 500

# ============================================================
# بخش ۱۳: API های تنظیمات
# ============================================================

@app.route('/api/admin/config', methods=['GET'])
@admin_required
def get_config():
    """دریافت تنظیمات فعلی"""
    return jsonify({
        'api_key': API_KEY,
        'base_url': BASE_URL,
        'model': MODEL,
        'system_prompt': SYSTEM_PROMPT
    })

@app.route('/api/admin/config', methods=['POST'])
@admin_required
def update_config():
    """بروزرسانی تنظیمات"""
    global API_KEY, BASE_URL, MODEL, SYSTEM_PROMPT, config
    
    data = request.get_json()
    
    if 'api_key' in data and data['api_key']:
        API_KEY = data['api_key']
        config['api_key'] = API_KEY
    
    if 'base_url' in data and data['base_url']:
        BASE_URL = data['base_url']
        config['base_url'] = BASE_URL
    
    if 'model' in data and data['model']:
        MODEL = data['model']
        config['model'] = MODEL
    
    if 'system_prompt' in data and data['system_prompt']:
        SYSTEM_PROMPT = data['system_prompt']
        config['system_prompt'] = SYSTEM_PROMPT
    
    save_config(config)
    
    return jsonify({
        'success': True,
        'message': 'تنظیمات با موفقیت بروزرسانی شد'
    })

@app.route('/api/admin/test-api', methods=['POST'])
@admin_required
def test_api():
    """تست اتصال به API"""
    global API_KEY, BASE_URL, MODEL
    
    try:
        test_message = "سلام، این یک پیام تست است. لطفاً با یک پاسخ کوتاه و دوستانه پاسخ دهید."
        
        headers = {
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': MODEL,
            'messages': [
                {'role': 'system', 'content': 'شما یک دستیار مفید هستید. به زبان فارسی پاسخ دهید.'},
                {'role': 'user', 'content': test_message}
            ],
            'temperature': 0.7,
            'max_tokens': 8192
        }
        
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=30)
        elapsed_time = round((time.time() - start_time) * 1000, 2)
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            return jsonify({
                'success': True,
                'status_code': response.status_code,
                'response': ai_response,
                'elapsed_ms': elapsed_time,
                'model': MODEL,
                'config': {
                    'api_key': API_KEY[:8] + '...' + API_KEY[-4:] if len(API_KEY) > 12 else API_KEY,
                    'base_url': BASE_URL,
                    'model': MODEL
                }
            })
        else:
            return jsonify({
                'success': False,
                'status_code': response.status_code,
                'error': response.text[:500],
                'elapsed_ms': elapsed_time
            }), response.status_code
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'❌ خطا: {str(e)}'
        }), 500

# ============================================================
# بخش ۱۴: API های اصلی
# ============================================================

@app.route('/api/crypto')
def get_crypto():
    """دریافت داده‌های ارزهای دیجیتال"""
    return jsonify({
        'data': crypto_data,
        'stats': market_stats,
        'last_update': last_update
    })

@app.route('/api/fear-greed')
def get_fear_greed():
    """دریافت شاخص ترس و طمع - با هدرهای no-cache"""
    response = jsonify(fear_greed_data)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/analyze', methods=['POST'])
@login_required
def analyze():
    """تحلیل هوشمند بازار"""
    user_type = session.get('user_type', 'simple')
    if user_type == 'simple':
        return jsonify({'error': 'کاربران ساده نمی‌توانند از تحلیل استفاده کنند'}), 403
    
    try:
        data = request.get_json()
        user_query = data.get('query', '')
        analysis_type = data.get('type', 'general')
        
        prompt_data = build_advanced_prompt(user_query, analysis_type)
        messages = [
            {'role': 'system', 'content': prompt_data['system']},
            {'role': 'user', 'content': prompt_data['user']}
        ]
        
        response = call_ai_api(messages, temperature=0.7, max_tokens=8192)
        return jsonify({'analysis': response, 'type': analysis_type})
        
    except Exception as e:
        print(f"Analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    """چت با هوش مصنوعی"""
    user_type = session.get('user_type', 'simple')
    if user_type == 'simple':
        return jsonify({'error': 'کاربران ساده نمی‌توانند از چت استفاده کنند'}), 403
    
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        history = data.get('history', [])
        
        if not user_message:
            return jsonify({'error': 'پیام خالی است'}), 400
        
        system_prompt = """شما یک مشاور ارشد در بازار ارزهای دیجیتال هستید.
        پاسخ‌ها را به فارسی روان و با بندنویسی منظم بنویسید."""
        
        messages = [{'role': 'system', 'content': system_prompt}]
        
        for msg in history[-10:]:
            messages.append({
                'role': 'user' if msg['type'] == 'user' else 'assistant',
                'content': msg['content']
            })
        
        messages.append({'role': 'user', 'content': user_message})
        
        response = call_ai_api(messages, temperature=0.8, max_tokens=8192)
        
        user = db.get_user_by_username(session['username'])
        if user:
            db.add_chat_history(user['id'], user_message, response)
        
        return jsonify({'response': response})
        
    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# بخش ۱۵: اجرا
# ============================================================

if __name__ == '__main__':
    # راه‌اندازی دیتابیس
    db.init_db()
    
    # ایجاد کاربر ادمین پیش‌فرض
    if not db.get_user_by_username('admin'):
        db.create_user('admin', '2026', 'premium', 'مدیر سیستم', 'admin@crypto.com', '09120000000')
        admin = db.get_user_by_username('admin')
        if admin:
            db.update_user(admin['id'], role='admin')
        print("✅ کاربر ادمین ایجاد شد: admin / 2026")
    
    # شروع ترد پس‌زمینه
    thread = threading.Thread(target=background_updater, daemon=True)
    thread.start()
    time.sleep(2)
    
    # دریافت اولیه داده‌ها
    fetch_crypto_data()
    fetch_fear_greed()
    
    print("=" * 50)
    print("🚀 Crypto Pro Server Started!")
    print("📍 http://localhost:5000")
    print("👑 Admin: admin / 2026")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
