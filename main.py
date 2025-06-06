# main.py

from flask import Flask
# from flask_wtf.csrf import CSRFProtect # CSRF সুরক্ষা ব্যবহার না করলে এটি বাদ দিন

from database import init_db_app, db, User
from auth import auth_bp, init_auth_app
from public_routes import public_bp
from admin_routes import admin_bp
from admin_extra import admin_extra_bp
from public_extra import public_extra_bp
from post_admin import post_admin_bp
from post_public import post_public_bp
import os
import datetime
import pytz

# --- বাংলা তারিখ ও সময় ফরম্যাটিং এর জন্য ফাংশন ---
def format_custom_bangla_datetime_filter(value_utc):
    if not isinstance(value_utc, datetime.datetime):
        return value_utc if value_utc is not None else ""
    
    dhaka_tz = pytz.timezone('Asia/Dhaka')
    dt_dhaka = value_utc.replace(tzinfo=pytz.utc).astimezone(dhaka_tz)
    
    bn_months = {
        1: "জানুয়ারি", 2: "ফেব্রুয়ারি", 3: "মার্চ", 4: "এপ্রিল",
        5: "মে", 6: "জুন", 7: "জুলাই", 8: "আগস্ট",
        9: "সেপ্টেম্বর", 10: "অক্টোবর", 11: "নভেম্বর", 12: "ডিসেম্বর"
    }
    bn_digits = "০১২৩৪৫৬৭৮৯"
    
    def to_bengali_digits(num_or_str):
        num_str = str(num_or_str)
        return "".join(bn_digits[int(digit)] if digit.isdigit() else digit for digit in num_str)

    day = to_bengali_digits(dt_dhaka.day)
    month_name = bn_months.get(dt_dhaka.month, "")
    year = to_bengali_digits(dt_dhaka.year)
    
    hour = dt_dhaka.hour
    minute = to_bengali_digits(f"{dt_dhaka.minute:02d}")
    
    am_pm_en = dt_dhaka.strftime("%p").upper()
    am_pm_bn = ""
    hour_12 = hour % 12
    if hour_12 == 0:
        hour_12 = 12

    if hour == 0: 
        am_pm_bn = "মধ্যরাত"
        hour_12 = 12
    elif hour < 12:
        am_pm_bn = "পূর্বাহ্ণ"
    elif hour == 12: 
        am_pm_bn = "মধ্যাহ্ন"
        hour_12 = 12
    else: 
        am_pm_bn = "অপরাহ্ণ"
        hour_12 = hour - 12

    hour_bn = to_bengali_digits(hour_12)
    
    return f"{day} {month_name}, {year} সময়ঃ {hour_bn}:{minute} {am_pm_bn}"
# --- বাংলা ফরম্যাটিং ফাংশন শেষ ---


# --- সরাসরি কনফিগারেশন ভেরিয়েবল ---
# আপনার Render.com এর PostgreSQL কানেকশন স্ট্রিং এখানে দিন
DATABASE_URL_CONFIG = os.environ.get('DATABASE_URL', 'postgresql://paathshala_ecvv_user:u49VmQvHmB6iLImHXqD4abmyppyDc6wg@dpg-d10s7t3e5dus73al7klg-a.singapore-postgres.render.com/paathshala_ecvv')
# APP_SECRET_KEY পরিবেশ পরিবর্তনশীল (Environment Variable) থেকে নেওয়া ভালো
APP_SECRET_KEY = os.environ.get('SECRET_KEY', "একটি_শক্তিশালী_গোপন_কী_দিন_না_হলে_এটি_ব্যবহার_করুন") 

DEBUG_MODE_CONFIG_STR = os.environ.get('FLASK_DEBUG', 'True')
DEBUG_MODE_CONFIG = DEBUG_MODE_CONFIG_STR.lower() in ('true', '1', 't')


ADMIN_USERNAME_CONFIG = os.environ.get('ADMIN_USERNAME', "replitadmin")
ADMIN_PASSWORD_CONFIG = os.environ.get('ADMIN_PASSWORD', "replit_strong_password_456")
# --- কনফিগারেশন শেষ ---


def create_app():
    app = Flask(__name__, instance_relative_config=False) # instance_relative_config=False করা হলো কারণ instance ফোল্ডার আর দরকার নেই

    app.config['SECRET_KEY'] = APP_SECRET_KEY
    if not app.config['SECRET_KEY'] or app.config['SECRET_KEY'] == "একটি_শক্তিশালী_গোপন_কী_দিন_না_হলে_এটি_ব্যবহার_করুন":
        print("সতর্কবার্তা: SECRET_KEY সেট করা হয়নি অথবা ডিফল্ট মান ব্যবহার করা হচ্ছে। প্রোডাকশনের জন্য এটি পরিবর্তন করুন।")
        # raise ValueError("ত্রুটি: SECRET_KEY সেট করা হয়নি অথবা ডিফল্ট মান পরিবর্তন করা হয়নি।") # ডেভেলপমেন্টের সময় এটি বন্ধ রাখতে পারেন

    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL_CONFIG
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['DEBUG'] = DEBUG_MODE_CONFIG

    app.config['REMEMBER_COOKIE_DURATION'] = datetime.timedelta(days=30)
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['REMEMBER_COOKIE_SAMESITE'] = "Lax"

    # CSRF সুরক্ষা (যদি ব্যবহার না করেন, তাহলে এই অংশটি বাদ দিন)
    # from flask_wtf.csrf import CSRFProtect
    # csrf = CSRFProtect(app)

    init_db_app(app)
    init_auth_app(app)

    app.jinja_env.filters['bangla_datetime'] = format_custom_bangla_datetime_filter

    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_extra_bp) 
    app.register_blueprint(public_extra_bp)
    app.register_blueprint(post_admin_bp)
    app.register_blueprint(post_public_bp)

    @app.context_processor
    def inject_current_year():
        return {'current_year': datetime.datetime.utcnow().year}

    with app.app_context():
        if not User.query.filter_by(username=ADMIN_USERNAME_CONFIG).first():
            try:
                admin_user = User(username=ADMIN_USERNAME_CONFIG, role='admin')
                admin_user.set_password(ADMIN_PASSWORD_CONFIG)
                db.session.add(admin_user)
                db.session.commit()
                print(f"Default admin user '{ADMIN_USERNAME_CONFIG}' created.")
            except Exception as e:
                db.session.rollback()
                print(f"Error creating default admin user: {str(e)}")

    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get("PORT", 5000)) # Render.com সাধারণত PORT এনভায়রনমেন্ট ভেরিয়েবল সেট করে
    app.run(host='0.0.0.0', port=port) # ডিবাগ মোড এখন DEBUG_MODE_CONFIG দ্বারা নিয়ন্ত্রিত