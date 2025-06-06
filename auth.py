# auth.py

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
# সরাসরি database.py থেকে ইম্পোর্ট করা হচ্ছে
from database import db, User
import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
    flash('এই পৃষ্ঠা অ্যাক্সেস করতে আপনাকে লগইন করতে হবে।', 'warning')
    return redirect(url_for('auth.login'))

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('public.home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('ইউজারনেম এবং পাসওয়ার্ড উভয়ই আবশ্যক।', 'danger')
            return redirect(url_for('auth.signup'))
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('এই ইউজারনেম দিয়ে ইতিমধ্যে অ্যাকাউন্ট খোলা হয়েছে।', 'warning')
            return redirect(url_for('auth.signup'))
        new_user = User(username=username, role='student')
        new_user.set_password(password)
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('সাইনআপ সফল হয়েছে! এখন লগইন করুন।', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'সাইনআপ করার সময় একটি ত্রুটি হয়েছে: {str(e)}', 'danger')
            return redirect(url_for('auth.signup'))
    return render_template('auth/signup.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('public.home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember_me') else False
        if not username or not password:
            flash('ইউজারনেম এবং পাসওয়ার্ড উভয়ই আবশ্যক।', 'danger')
            return redirect(url_for('auth.login'))
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash('ইউজারনেম বা পাসওয়ার্ড সঠিক নয়।', 'danger')
            return redirect(url_for('auth.login'))
        login_user(user, remember=remember)
        flash(f'স্বাগতম, {user.username}! আপনি সফলভাবে লগইন করেছেন।', 'success')
        if user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('public.home'))
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('আপনি সফলভাবে লগআউট হয়েছেন।', 'info')
    return redirect(url_for('auth.login'))

def init_auth_app(app):
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'