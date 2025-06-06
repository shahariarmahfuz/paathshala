# post_admin.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database import db, User, EducationalPost, PostComment # PostLike এখানে সরাসরি প্রয়োজন নাও হতে পারে
from functools import wraps
# from app.utils import format_bangla_datetime # যদি utils.py তে রাখেন, অথবা নিচে সরাসরি যোগ করুন

# --- অ্যাডমিন আবশ্যক ডেকোরেটর (যদি আগে তৈরি করা না থাকে) ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('এই পৃষ্ঠা অ্যাক্সেস করার জন্য আপনার অ্যাডমিন অনুমতি প্রয়োজন।', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

post_admin_bp = Blueprint('post_admin', __name__, url_prefix='/admin/posts')

# --- শিক্ষামূলক পোস্ট পরিচালনা ---

@post_admin_bp.route('/')
@login_required
@admin_required
def list_posts():
    page = request.args.get('page', 1, type=int)
    per_page = 10 # প্রতি পৃষ্ঠায় পোস্ট সংখ্যা
    # সকল পোস্ট দেখানো হচ্ছে, আপনি চাইলে শুধুমাত্র বর্তমান অ্যাডমিনের পোস্টও দেখাতে পারেন
    posts_pagination = EducationalPost.query.order_by(EducationalPost.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    posts = posts_pagination.items
    return render_template('post/admin/list_posts_admin.html', 
                           posts=posts, 
                           pagination=posts_pagination)

@post_admin_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')

        if not title or not content:
            flash('শিরোনাম এবং বিষয়বস্তু উভয়ই আবশ্যক।', 'danger')
        else:
            try:
                new_post = EducationalPost(title=title, content=content, author_id=current_user.id)
                db.session.add(new_post)
                db.session.commit()
                flash('নতুন শিক্ষামূলক পোস্ট সফলভাবে যোগ করা হয়েছে।', 'success')
                return redirect(url_for('post_admin.list_posts'))
            except Exception as e:
                db.session.rollback()
                flash(f'পোস্ট যোগ করার সময় একটি ত্রুটি হয়েছে: {str(e)}', 'danger')

    return render_template('post/admin/add_post.html')

@post_admin_bp.route('/edit/<int:post_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_post(post_id):
    post = EducationalPost.query.get_or_404(post_id)
    # শুধুমাত্র পোস্টের লেখক অথবা সুপার অ্যাডমিন (যদি থাকে) এডিট করতে পারবে
    if post.author_id != current_user.id and current_user.role != 'superadmin': # 'superadmin' রোল আপনার সিস্টেমে না থাকলে এটি বাদ দিন
        flash('এই পোস্টটি সম্পাদনা করার অনুমতি আপনার নেই।', 'danger')
        return redirect(url_for('post_admin.list_posts'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')

        if not title or not content:
            flash('শিরোনাম এবং বিষয়বস্তু উভয়ই আবশ্যক।', 'danger')
        else:
            try:
                post.title = title
                post.content = content
                # post.updated_at স্বয়ংক্রিয়ভাবে আপডেট হবে
                db.session.commit()
                flash('পোস্ট সফলভাবে আপডেট করা হয়েছে।', 'success')
                return redirect(url_for('post_admin.list_posts'))
            except Exception as e:
                db.session.rollback()
                flash(f'পোস্ট আপডেট করার সময় একটি ত্রুটি হয়েছে: {str(e)}', 'danger')

    return render_template('post/admin/edit_post.html', post=post)

@post_admin_bp.route('/delete/<int:post_id>', methods=['POST'])
@login_required
@admin_required
def delete_post(post_id):
    post = EducationalPost.query.get_or_404(post_id)
    if post.author_id != current_user.id and current_user.role != 'superadmin':
        flash('এই পোস্টটি ডিলিট করার অনুমতি আপনার নেই।', 'danger')
        return redirect(url_for('post_admin.list_posts'))
    try:
        # সম্পর্কিত লাইক ও কমেন্ট স্বয়ংক্রিয়ভাবে ডিলিট হবে যদি cascade="all, delete-orphan" মডেলে সেট করা থাকে
        db.session.delete(post)
        db.session.commit()
        flash('পোস্ট সফলভাবে ডিলিট করা হয়েছে।', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'পোস্ট ডিলিট করার সময় একটি ত্রুটি হয়েছে: {str(e)}', 'danger')
    return redirect(url_for('post_admin.list_posts'))

# --- কমেন্ট পরিচালনা ---
@post_admin_bp.route('/post/<int:post_id>/comments')
@login_required
@admin_required
def manage_post_comments(post_id):
    post = EducationalPost.query.get_or_404(post_id)
    # এখানে আপনি কমেন্টগুলো প্যাজিনেশন করতে পারেন যদি অনেক কমেন্ট থাকে
    comments = PostComment.query.filter_by(post_id=post.id).order_by(PostComment.created_at.desc()).all()
    return render_template('post/admin/manage_post_comments.html', post=post, comments=comments)

@post_admin_bp.route('/comment/delete/<int:comment_id>', methods=['POST'])
@login_required
@admin_required
def delete_comment_admin(comment_id):
    comment = PostComment.query.get_or_404(comment_id)
    post_id_redirect = comment.post_id # ডিলিট করার পর আগের পেজে ফিরে যাওয়ার জন্য
    try:
        # যদি কমেন্টের রিপ্লাই থাকে, সেগুলোও ডিলিট করা উচিত অথবা parent_comment_id null করা উচিত
        # cascade delete সেট করা থাকলে PostComment মডেলে, replies গুলোও ডিলিট হতে পারে
        # আপাতত সরাসরি কমেন্ট ডিলিট করা হচ্ছে
        if comment.replies.count() > 0:
             for reply in comment.replies: # প্রথমে সব রিপ্লাই ডিলিট করুন
                 db.session.delete(reply)
        db.session.delete(comment)
        db.session.commit()
        flash('কমেন্ট সফলভাবে ডিলিট করা হয়েছে।', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'কমেন্ট ডিলিট করার সময় একটি ত্রুটি হয়েছে: {str(e)}', 'danger')
    return redirect(url_for('post_admin.manage_post_comments', post_id=post_id_redirect))