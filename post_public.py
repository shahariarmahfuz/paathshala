# post_public.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc
from database import db, User, EducationalPost, PostLike, PostComment
# from app.utils import format_bangla_datetime # যদি utils.py তে রাখেন বা main.py তে রেজিস্টার করা থাকে

post_public_bp = Blueprint('post_public', __name__, url_prefix='/posts')

# --- শিক্ষামূলক পোস্ট দেখা ---

@post_public_bp.route('/')
def list_all_posts():
    page = request.args.get('page', 1, type=int)
    per_page = 10 

    posts_pagination = EducationalPost.query.order_by(EducationalPost.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    posts_items = posts_pagination.items

    return render_template('post/public/posts_home.html', 
                           posts=posts_items, 
                           pagination=posts_pagination)

@post_public_bp.route('/<int:post_id>')
def view_single_post(post_id):
    post = EducationalPost.query.get_or_404(post_id)
    comments_query = PostComment.query.filter_by(post_id=post.id, parent_comment_id=None).order_by(PostComment.created_at.desc())

    initial_comments_limit = 5
    comments = comments_query.limit(initial_comments_limit).all()

    total_comments_count = comments_query.count()

    user_liked_post = False
    if current_user.is_authenticated:
        user_liked_post = PostLike.query.filter_by(post_id=post.id, user_id=current_user.id).first() is not None

    return render_template('post/public/view_post.html', 
                           post=post, 
                           comments=comments,
                           user_liked_post=user_liked_post,
                           initial_comments_limit=initial_comments_limit,
                           total_comments_count=total_comments_count)

# --- লাইক এবং কমেন্টের জন্য AJAX হ্যান্ডলার ---

@post_public_bp.route('/like/<int:post_id>', methods=['POST'])
@login_required
def toggle_like_post(post_id):
    post = EducationalPost.query.get_or_404(post_id)
    like = PostLike.query.filter_by(post_id=post.id, user_id=current_user.id).first()

    if like:
        db.session.delete(like)
        liked = False
    else:
        new_like = PostLike(post_id=post.id, user_id=current_user.id)
        db.session.add(new_like)
        liked = True

    try:
        db.session.commit()
        like_count = PostLike.query.filter_by(post_id=post.id).count()
        return jsonify({'success': True, 'liked': liked, 'like_count': like_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@post_public_bp.route('/comment/add/<int:post_id>', methods=['POST'])
@login_required
def add_comment_to_post(post_id):
    post = EducationalPost.query.get_or_404(post_id)
    comment_content = request.form.get('comment_content')
    parent_id_str = request.form.get('parent_comment_id')

    if not comment_content or not comment_content.strip():
        return jsonify({'success': False, 'error': 'কমেন্টের বিষয়বস্তু খালি হতে পারবে না।'}), 400

    parent_id = None
    if parent_id_str:
        try:
            parent_id = int(parent_id_str)
            parent_comment_check = PostComment.query.filter_by(id=parent_id, post_id=post_id).first()
            if not parent_comment_check:
                return jsonify({'success': False, 'error': 'অবৈধ প্যারেন্ট কমেন্ট আইডি।'}), 400
        except ValueError:
             return jsonify({'success': False, 'error': 'অবৈধ প্যারেন্ট কমেন্ট আইডি ফরম্যাট।'}), 400

    new_comment = PostComment(
        post_id=post.id,
        user_id=current_user.id,
        content=comment_content.strip(),
        parent_comment_id=parent_id
    )
    try:
        db.session.add(new_comment)
        db.session.commit()

        return jsonify({
            'success': True,
            'comment': {
                'id': new_comment.id,
                'content': new_comment.content,
                'user_id': new_comment.user_id,
                'username': new_comment.user.username, 
                'created_at_raw': new_comment.created_at.isoformat() + "Z", # 'Z' যোগ করা হয়েছে UTC বোঝানোর জন্য
                'parent_id': new_comment.parent_comment_id,
                'replies': [] # নতুন কমেন্টের জন্য খালি replies অ্যারে
            },
            'message': 'কমেন্ট সফলভাবে যোগ করা হয়েছে।' if not parent_id else 'রিপ্লাই সফলভাবে যোগ করা হয়েছে.'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@post_public_bp.route('/comments/load/<int:post_id>')
@login_required 
def load_more_comments(post_id):
    post = EducationalPost.query.get_or_404(post_id)
    offset = request.args.get('offset', 0, type=int)
    limit = 5 

    more_comments = PostComment.query.filter_by(post_id=post.id, parent_comment_id=None)\
                                     .order_by(PostComment.created_at.desc())\
                                     .offset(offset)\
                                     .limit(limit)\
                                     .all()

    comments_data = [] # comments_html এর পরিবর্তে comments_data
    if more_comments:
        for comment in more_comments:
            replies_data = []
            # রিপ্লাইগুলো পুরাতন থেকে নতুন ক্রমে লোড করা হচ্ছে
            for reply in comment.replies.order_by(PostComment.created_at.asc()).all():
                replies_data.append({
                    'id': reply.id,
                    'content': reply.content,
                    'user_id': reply.user_id,
                    'username': reply.user.username,
                    'created_at_raw': reply.created_at.isoformat() + "Z",
                })

            comments_data.append({ # comments_html এর পরিবর্তে comments_data
                'id': comment.id,
                'content': comment.content,
                'user_id': comment.user_id,
                'username': comment.user.username,
                'created_at_raw': comment.created_at.isoformat() + "Z",
                'replies': replies_data,
                # 'current_user_id' এখানে পাঠানোর প্রয়োজন নেই, কারণ renderCommentItem এটি নেয়
            })
        return jsonify({'success': True, 'comments': comments_data, 'has_more': len(more_comments) == limit})
    else:
        return jsonify({'success': True, 'comments': [], 'has_more': False})