# database.py

import json
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='student') # 'admin' or 'student'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Relationships for question creation tracking by admin
    created_mcqs = db.relationship('MCQ', backref='creator', lazy=True, foreign_keys='MCQ.created_by_admin_id')
    created_short_questions = db.relationship('ShortQuestion', backref='creator', lazy=True, foreign_keys='ShortQuestion.created_by_admin_id')
    created_comprehension_questions = db.relationship('ComprehensionQuestion', backref='creator', lazy=True, foreign_keys='ComprehensionQuestion.created_by_admin_id')
    created_creative_questions = db.relationship('CreativeQuestion', backref='creator', lazy=True, foreign_keys='CreativeQuestion.created_by_admin_id')

    # Relationship for user read status (questions read by this user)
    read_statuses = db.relationship('UserReadStatus', backref='user', lazy='dynamic', cascade="all, delete-orphan")

    # Relationship for MCQ attempts by this user (defined via backref in UserAttempt)
    # attempts = backref from UserAttempt.user

    # Relationships for Educational Posts
    # educational_posts: posts authored by this user (defined via backref in EducationalPost.author)
    # post_likes: likes given by this user (defined via backref in PostLike.user)
    # post_comments: comments made by this user (defined via backref in PostComment.user)


    def __repr__(self):
        return f'<User {self.username}>'

class ClassLevel(db.Model):
    __tablename__ = 'class_level'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    subjects = db.relationship('Subject', backref='class_level', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<ClassLevel {self.name}>'

class Subject(db.Model):
    __tablename__ = 'subject'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    class_level_id = db.Column(db.Integer, db.ForeignKey('class_level.id'), nullable=False)

    mcqs = db.relationship('MCQ', backref='subject', lazy=True, cascade="all, delete-orphan")
    short_questions = db.relationship('ShortQuestion', backref='subject', lazy=True, cascade="all, delete-orphan")
    comprehension_questions = db.relationship('ComprehensionQuestion', backref='subject', lazy=True, cascade="all, delete-orphan")
    creative_questions = db.relationship('CreativeQuestion', backref='subject', lazy=True, cascade="all, delete-orphan")
    # Educational posts are not directly tied to a subject in this model, but can be added if needed.

    __table_args__ = (db.UniqueConstraint('name', 'class_level_id', name='uq_subject_name_class_level_id'),)

    def __repr__(self):
        return f'<Subject {self.name} (Class: {self.class_level.name if self.class_level else "N/A"})>'

class Stimulus(db.Model):
    __tablename__ = 'stimulus'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False, unique=True)

    mcqs = db.relationship('MCQ', backref='stimulus', lazy=True)
    creative_questions = db.relationship('CreativeQuestion', backref='stimulus', lazy=True)

    def __repr__(self):
        return f'<Stimulus ID {self.id}>'

class MCQ(db.Model):
    __tablename__ = 'mcq'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    stimulus_id = db.Column(db.Integer, db.ForeignKey('stimulus.id'), nullable=True)
    question_type = db.Column(db.String(50), nullable=False) 
    question_text = db.Column(db.Text, nullable=False)
    options_data = db.Column(db.Text, nullable=False) # JSON string for options
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    # creator relationship defined in User model via backref
    attempts = db.relationship('UserAttempt', backref='mcq_attempted', lazy='dynamic', cascade="all, delete-orphan")

    def get_options_data_dict(self):
        try:
            return json.loads(self.options_data)
        except json.JSONDecodeError:
            return {}

    def __repr__(self):
        return f'<MCQ ID {self.id}: {self.question_text[:30]}...>'

class ShortQuestion(db.Model):
    __tablename__ = 'short_question'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    answer_text = db.Column(db.Text, nullable=False)
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    # creator relationship defined in User model via backref

    def __repr__(self):
        return f'<ShortQuestion ID {self.id}: {self.question_text[:30]}...>'

class ComprehensionQuestion(db.Model):
    __tablename__ = 'comprehension_question'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    answer_text = db.Column(db.Text, nullable=False)
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    # creator relationship defined in User model via backref

    def __repr__(self):
        return f'<ComprehensionQuestion ID {self.id}: {self.question_text[:30]}...>'

class CreativeQuestion(db.Model):
    __tablename__ = 'creative_question'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    stimulus_id = db.Column(db.Integer, db.ForeignKey('stimulus.id'), nullable=False)
    parts_data = db.Column(db.Text, nullable=False) # JSON string for the 4 parts
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    # creator relationship defined in User model via backref

    def get_parts_data_dict_list(self):
        try:
            return json.loads(self.parts_data)
        except json.JSONDecodeError:
            return []

    def __repr__(self):
        stimulus_preview = self.stimulus.text[:20] if self.stimulus else "No Stimulus"
        return f'<CreativeQuestion ID {self.id}: Stimulus: {stimulus_preview}..>'

class UserReadStatus(db.Model):
    __tablename__ = 'user_read_status'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_type = db.Column(db.String(50), nullable=False) # 'short', 'comprehension', 'creative'
    question_id = db.Column(db.Integer, nullable=False) 
    read_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # user relationship defined in User model via backref
    __table_args__ = (db.UniqueConstraint('user_id', 'question_type', 'question_id', name='uq_user_read_status'),)

    def __repr__(self):
        return f'<UserReadStatus UserID:{self.user_id} Type:{self.question_type} QID:{self.question_id}>'

class UserAttempt(db.Model):
    __tablename__ = 'user_attempt'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mcq_id = db.Column(db.Integer, db.ForeignKey('mcq.id'), nullable=False)
    selected_option = db.Column(db.String(255), nullable=True)
    is_correct = db.Column(db.Boolean, nullable=False)
    attempt_timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    time_taken_seconds = db.Column(db.Integer, nullable=True)
    user = db.relationship('User', backref=db.backref('attempts', lazy='dynamic'))

    def __repr__(self):
        return f'<UserAttempt UserID:{self.user_id} MCQID:{self.mcq_id} Correct:{self.is_correct}>'

# --- শিক্ষামূলক পোস্টের জন্য নতুন মডেল ---
class EducationalPost(db.Model):
    __tablename__ = 'educational_post'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    author = db.relationship('User', backref=db.backref('educational_posts', lazy='dynamic'))
    likes = db.relationship('PostLike', backref='post', lazy='dynamic', cascade="all, delete-orphan")
    comments = db.relationship('PostComment', backref='post', lazy='dynamic', cascade="all, delete-orphan", order_by="PostComment.created_at.desc()")

    def __repr__(self):
        return f'<EducationalPost "{self.title[:50]}...">'

class PostLike(db.Model):
    __tablename__ = 'post_like'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('educational_post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    user = db.relationship('User', backref=db.backref('post_likes', lazy='dynamic'))
    # post relationship defined in EducationalPost model via backref

    __table_args__ = (db.UniqueConstraint('post_id', 'user_id', name='uq_post_user_like'),)

    def __repr__(self):
        return f'<PostLike UserID:{self.user_id} PostID:{self.post_id}>'

class PostComment(db.Model):
    __tablename__ = 'post_comment'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('educational_post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('post_comment.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    user = db.relationship('User', backref=db.backref('post_comments', lazy='dynamic'))
    # post relationship defined in EducationalPost model via backref
    parent = db.relationship('PostComment', remote_side=[id], backref=db.backref('replies', lazy='dynamic', order_by="PostComment.created_at.asc()"))

    def __repr__(self):
        return f'<PostComment ID:{self.id} UserID:{self.user_id} PostID:{self.post_id} Content:"{self.content[:20]}...">'
# --- শিক্ষামূলক পোস্টের মডেল শেষ ---

def init_db_app(app):
    db.init_app(app)
    with app.app_context():
        db.create_all() 
        print("Database tables (re)created including educational post models. Ensure schema changes are handled appropriately.")