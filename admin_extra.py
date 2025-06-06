# admin_extra.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, get_flashed_messages
from flask_login import login_required, current_user
from database import db, Subject, ClassLevel, Stimulus, UserReadStatus, MCQ
from database import ShortQuestion, ComprehensionQuestion, CreativeQuestion
import json
from functools import wraps

admin_extra_bp = Blueprint('admin_extra', __name__, url_prefix='/admin/extra')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('এই পৃষ্ঠা অ্যাক্সেস করার জন্য আপনার অ্যাডমিন অনুমতি প্রয়োজন।', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def get_or_create_stimulus(stimulus_text_str):
    if not stimulus_text_str or not stimulus_text_str.strip():
        return None
    stimulus_text = stimulus_text_str.strip()
    stimulus = Stimulus.query.filter_by(text=stimulus_text).first()
    if not stimulus:
        stimulus = Stimulus(text=stimulus_text)
        db.session.add(stimulus)
        db.session.flush()
    return stimulus.id

# --- Short Question Management ---
@admin_extra_bp.route('/short/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_short_questions():
    classes = ClassLevel.query.order_by(ClassLevel.name).all()
    form_data = {
        'selected_class_id': request.form.get('class_id_selector', type=int) if request.method == 'POST' else None,
        'selected_subject_id': request.form.get('subject_id', type=int) if request.method == 'POST' else None,
        'json_data': request.form.get('json_data', '') if request.method == 'POST' else ''
    }
    subjects_for_selected_class = []
    if form_data['selected_class_id']:
        current_selected_class = ClassLevel.query.get(form_data['selected_class_id'])
        if current_selected_class:
            subjects_for_selected_class = sorted(current_selected_class.subjects, key=lambda s: s.name)

    if request.method == 'POST':
        if not form_data['selected_subject_id'] or not form_data['json_data']:
            flash('শ্রেণী, বিষয় এবং JSON ডেটা আবশ্যক।', 'danger')
        else:
            subject = Subject.query.get(form_data['selected_subject_id'])
            if not subject:
                flash('নির্বাচিত বিষয় খুঁজে পাওয়া যায়নি।', 'danger')
            elif subject.class_level_id != form_data['selected_class_id']:
                flash('নির্বাচিত বিষয় এবং শ্রেণীর মধ্যে গরমিল রয়েছে।', 'danger')
            else:
                try:
                    data = json.loads(form_data['json_data'])
                    if 'questions' not in data or not isinstance(data['questions'], list):
                        raise ValueError("JSON এর মূল 'questions' একটি তালিকা (array) হতে হবে।")
                    added_count = 0; error_messages = []
                    for idx, q_item in enumerate(data['questions']):
                        q_err_prefix = f"আইটেম {idx+1}"
                        if not q_item.get('question_text') or not q_item.get('answer_text'):
                            error_messages.append(f"{q_err_prefix}: 'question_text' এবং 'answer_text' উভয়ই আবশ্যক।")
                            continue
                        new_short_q = ShortQuestion(
                            subject_id=subject.id,
                            question_text=str(q_item['question_text']).strip(),
                            answer_text=str(q_item['answer_text']).strip(),
                            created_by_admin_id=current_user.id
                        )
                        db.session.add(new_short_q); added_count += 1

                    if error_messages:
                        for err in error_messages: flash(err, 'warning')
                        if added_count > 0: db.session.commit()
                        else: db.session.rollback()
                        flash(f"{added_count} টি সংক্ষিপ্ত প্রশ্ন যোগ করা হয়েছে। কিছু ত্রুটি থাকতে পারে।", 'info')
                    elif added_count > 0:
                        db.session.commit()
                        flash(f'{added_count} টি সংক্ষিপ্ত প্রশ্ন সফলভাবে যোগ করা হয়েছে।', 'success')
                        return redirect(url_for('admin_extra.list_short_questions', class_id=subject.class_level_id, subject_id=subject.id))
                    else:
                        flash('JSON ডেটাতে কোনো প্রশ্ন পাওয়া যায়নি অথবা যোগ করার মতো কোনো সঠিক প্রশ্ন ছিল না।', 'info')
                except (json.JSONDecodeError, ValueError) as e:
                    db.session.rollback(); flash(f'JSON পার্সিং বা ডেটা ভ্যালিডেশনে ত্রুটি: {e}', 'danger')
                except Exception as e:
                    db.session.rollback(); flash(f'সংক্ষিপ্ত প্রশ্ন যোগ করার সময় অপ্রত্যাশিত ত্রুটি: {e}', 'danger')

        return render_template('extra/admin/short_question_adder.html',
                               classes=classes,
                               selected_class_id=form_data['selected_class_id'],
                               subjects_for_selected_class=subjects_for_selected_class,
                               selected_subject_id=form_data['selected_subject_id'],
                               json_data=form_data['json_data'])
    # GET request
    return render_template('extra/admin/short_question_adder.html',
                           classes=classes,
                           selected_class_id=None, subjects_for_selected_class=[],
                           selected_subject_id=None, json_data='')

@admin_extra_bp.route('/short/list', defaults={'class_id': None, 'subject_id': None})
@admin_extra_bp.route('/short/list/class/<int:class_id>', defaults={'subject_id': None})
@admin_extra_bp.route('/short/list/class/<int:class_id>/subject/<int:subject_id>')
@login_required
@admin_required
def list_short_questions(class_id, subject_id):
    query = ShortQuestion.query.join(Subject).join(ClassLevel)
    classes_all = ClassLevel.query.order_by(ClassLevel.name).all()
    subjects_for_filter = []
    selected_class_obj = None
    selected_subject_obj = None

    if class_id:
        selected_class_obj = ClassLevel.query.get(class_id)
        if selected_class_obj:
            query = query.filter(Subject.class_level_id == class_id)
            subjects_for_filter = sorted(selected_class_obj.subjects, key=lambda s: s.name)
        else: flash(f"শ্রেণী আইডি {class_id} খুঁজে পাওয়া যায়নি।", "warning"); class_id = None
    if subject_id and selected_class_obj:
        selected_subject_obj = Subject.query.filter_by(id=subject_id, class_level_id=class_id).first()
        if selected_subject_obj: query = query.filter(ShortQuestion.subject_id == subject_id)
        else: flash(f"বিষয় আইডি {subject_id} শ্রেণী '{selected_class_obj.name}' এর অধীনে খুঁজে পাওয়া যায়নি।", "warning"); subject_id = None
    elif subject_id and not selected_class_obj:
        flash("বিষয় ফিল্টার করার জন্য অনুগ্রহ করে প্রথমে শ্রেণী নির্বাচন করুন।", "warning"); subject_id = None

    questions = query.order_by(ClassLevel.name, Subject.name, ShortQuestion.id.desc()).all()
    return render_template('extra/admin/short_question_list.html',
                           questions=questions, classes=classes_all,
                           subjects_for_filter=subjects_for_filter,
                           selected_class=selected_class_obj, selected_subject=selected_subject_obj)

@admin_extra_bp.route('/short/edit/<int:q_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_short_question(q_id):
    question = ShortQuestion.query.get_or_404(q_id)
    if request.method == 'POST':
        new_question_text = request.form.get('question_text')
        new_answer_text = request.form.get('answer_text')
        new_subject_id_str = request.form.get('subject_id')
        if not new_question_text or not new_answer_text or not new_subject_id_str:
            flash('বিষয়, প্রশ্ন এবং উত্তর আবশ্যক।', 'danger')
        else:
            try:
                new_subject_id = int(new_subject_id_str)
                new_subject = Subject.query.get(new_subject_id)
                if not new_subject: flash("অবৈধ বিষয়।", "danger"); raise ValueError("Invalid subject")
                question.subject_id = new_subject_id
                question.question_text = new_question_text.strip()
                question.answer_text = new_answer_text.strip()
                db.session.commit()
                flash('সংক্ষিপ্ত প্রশ্ন সফলভাবে আপডেট করা হয়েছে।', 'success')
                return redirect(url_for('admin_extra.list_short_questions', class_id=question.subject.class_level_id, subject_id=question.subject_id))
            except ValueError: pass 
            except Exception as e: db.session.rollback(); flash(f'প্রশ্ন আপডেট করার সময় ত্রুটি হয়েছে: {str(e)}', 'danger')

    classes = ClassLevel.query.order_by(ClassLevel.name).all()
    subjects_for_selected_class = []
    selected_class_id_for_form = question.subject.class_level_id
    if selected_class_id_for_form:
        current_selected_class = ClassLevel.query.get(selected_class_id_for_form)
        if current_selected_class: subjects_for_selected_class = sorted(current_selected_class.subjects, key=lambda s: s.name)
    return render_template('extra/admin/short_question_editor.html',
                           question=question, classes=classes,
                           subjects_for_selected_class=subjects_for_selected_class,
                           selected_class_id=selected_class_id_for_form, selected_subject_id=question.subject_id)

@admin_extra_bp.route('/short/delete/<int:q_id>', methods=['POST'])
@login_required
@admin_required
def delete_short_question(q_id):
    question = ShortQuestion.query.get_or_404(q_id)
    class_id_redirect = question.subject.class_level_id
    subject_id_redirect = question.subject_id
    try:
        db.session.delete(question)
        UserReadStatus.query.filter_by(question_type='short', question_id=q_id).delete()
        db.session.commit()
        flash('সংক্ষিপ্ত প্রশ্ন সফলভাবে ডিলিট করা হয়েছে।', 'success')
    except Exception as e: db.session.rollback(); flash(f'প্রশ্ন ডিলিট করার সময় ত্রুটি হয়েছে: {str(e)}', 'danger')
    return redirect(url_for('admin_extra.list_short_questions', class_id=class_id_redirect, subject_id=subject_id_redirect))

# --- Comprehension Question Management ---
@admin_extra_bp.route('/comprehension/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_comprehension_questions():
    classes = ClassLevel.query.order_by(ClassLevel.name).all()
    form_data = {
        'selected_class_id': request.form.get('class_id_selector', type=int) if request.method == 'POST' else None,
        'selected_subject_id': request.form.get('subject_id', type=int) if request.method == 'POST' else None,
        'json_data': request.form.get('json_data', '') if request.method == 'POST' else ''
    }
    subjects_for_selected_class = []
    if form_data['selected_class_id']:
        current_selected_class = ClassLevel.query.get(form_data['selected_class_id'])
        if current_selected_class: subjects_for_selected_class = sorted(current_selected_class.subjects, key=lambda s: s.name)

    if request.method == 'POST':
        if not form_data['selected_subject_id'] or not form_data['json_data']:
            flash('শ্রেণী, বিষয় এবং JSON ডেটা আবশ্যক।', 'danger')
        else:
            subject = Subject.query.get(form_data['selected_subject_id'])
            if not subject: flash('নির্বাচিত বিষয় খুঁজে পাওয়া যায়নি।', 'danger')
            elif subject.class_level_id != form_data['selected_class_id']: flash('নির্বাচিত বিষয় এবং শ্রেণীর মধ্যে গরমিল রয়েছে।', 'danger')
            else:
                try:
                    data = json.loads(form_data['json_data'])
                    if 'questions' not in data or not isinstance(data['questions'], list):
                        raise ValueError("JSON এর মূল 'questions' একটি তালিকা (array) হতে হবে।")
                    added_count = 0; error_messages = []
                    for idx, q_item in enumerate(data['questions']):
                        q_err_prefix = f"আইটেম {idx+1}"
                        if not q_item.get('question_text') or not q_item.get('answer_text'):
                            error_messages.append(f"{q_err_prefix}: 'question_text' এবং 'answer_text' উভয়ই আবশ্যক।")
                            continue
                        new_comp_q = ComprehensionQuestion(
                            subject_id=subject.id,
                            question_text=str(q_item['question_text']).strip(),
                            answer_text=str(q_item['answer_text']).strip(),
                            created_by_admin_id=current_user.id
                        )
                        db.session.add(new_comp_q); added_count += 1
                    if error_messages:
                        for err in error_messages: flash(err, 'warning')
                        if added_count > 0: db.session.commit()
                        else: db.session.rollback()
                        flash(f"{added_count} টি অনুধাবনমূলক প্রশ্ন যোগ করা হয়েছে। কিছু ত্রুটি থাকতে পারে।", 'info')
                    elif added_count > 0:
                        db.session.commit()
                        flash(f'{added_count} টি অনুধাবনমূলক প্রশ্ন সফলভাবে যোগ করা হয়েছে।', 'success')
                        return redirect(url_for('admin_extra.list_comprehension_questions', class_id=subject.class_level_id, subject_id=subject.id))
                    else: flash('JSON ডেটাতে কোনো প্রশ্ন পাওয়া যায়নি অথবা যোগ করার মতো কোনো সঠিক প্রশ্ন ছিল না।', 'info')
                except (json.JSONDecodeError, ValueError) as e: db.session.rollback(); flash(f'JSON পার্সিং বা ডেটা ভ্যালিডেশনে ত্রুটি: {e}', 'danger')
                except Exception as e: db.session.rollback(); flash(f'অনুধাবনমূলক প্রশ্ন যোগে অপ্রত্যাশিত ত্রুটি: {e}', 'danger')
        return render_template('extra/admin/comprehension_question_adder.html',
                               classes=classes, selected_class_id=form_data['selected_class_id'],
                               subjects_for_selected_class=subjects_for_selected_class,
                               selected_subject_id=form_data['selected_subject_id'], json_data=form_data['json_data'])
    return render_template('extra/admin/comprehension_question_adder.html',
                           classes=classes, selected_class_id=None, subjects_for_selected_class=[],
                           selected_subject_id=None, json_data='')

@admin_extra_bp.route('/comprehension/list', defaults={'class_id': None, 'subject_id': None})
@admin_extra_bp.route('/comprehension/list/class/<int:class_id>', defaults={'subject_id': None})
@admin_extra_bp.route('/comprehension/list/class/<int:class_id>/subject/<int:subject_id>')
@login_required
@admin_required
def list_comprehension_questions(class_id, subject_id):
    query = ComprehensionQuestion.query.join(Subject).join(ClassLevel)
    classes_all = ClassLevel.query.order_by(ClassLevel.name).all()
    subjects_for_filter = []
    selected_class_obj = None
    selected_subject_obj = None
    if class_id:
        selected_class_obj = ClassLevel.query.get(class_id)
        if selected_class_obj: query = query.filter(Subject.class_level_id == class_id); subjects_for_filter = sorted(selected_class_obj.subjects, key=lambda s: s.name)
        else: flash(f"শ্রেণী আইডি {class_id} খুঁজে পাওয়া যায়নি।", "warning"); class_id = None
    if subject_id and selected_class_obj:
        selected_subject_obj = Subject.query.filter_by(id=subject_id, class_level_id=class_id).first()
        if selected_subject_obj: query = query.filter(ComprehensionQuestion.subject_id == subject_id)
        else: flash(f"বিষয় আইডি {subject_id} শ্রেণী '{selected_class_obj.name}' এর অধীনে খুঁজে পাওয়া যায়নি।", "warning"); subject_id = None
    elif subject_id and not selected_class_obj: flash("বিষয় ফিল্টার করার জন্য অনুগ্রহ করে প্রথমে শ্রেণী নির্বাচন করুন।", "warning"); subject_id = None
    questions = query.order_by(ClassLevel.name, Subject.name, ComprehensionQuestion.id.desc()).all()
    return render_template('extra/admin/comprehension_question_list.html',
                           questions=questions, classes=classes_all, subjects_for_filter=subjects_for_filter,
                           selected_class=selected_class_obj, selected_subject=selected_subject_obj)

@admin_extra_bp.route('/comprehension/edit/<int:q_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_comprehension_question(q_id):
    question = ComprehensionQuestion.query.get_or_404(q_id)
    if request.method == 'POST':
        new_question_text = request.form.get('question_text')
        new_answer_text = request.form.get('answer_text')
        new_subject_id_str = request.form.get('subject_id')
        if not new_question_text or not new_answer_text or not new_subject_id_str: flash('বিষয়, প্রশ্ন এবং উত্তর আবশ্যক।', 'danger')
        else:
            try:
                new_subject_id = int(new_subject_id_str)
                new_subject = Subject.query.get(new_subject_id)
                if not new_subject: flash("অবৈধ বিষয়।", "danger"); raise ValueError("Invalid subject")
                question.subject_id = new_subject_id
                question.question_text = new_question_text.strip()
                question.answer_text = new_answer_text.strip()
                db.session.commit()
                flash('অনুধাবনমূলক প্রশ্ন সফলভাবে আপডেট করা হয়েছে।', 'success')
                return redirect(url_for('admin_extra.list_comprehension_questions', class_id=question.subject.class_level_id, subject_id=question.subject_id))
            except ValueError: pass
            except Exception as e: db.session.rollback(); flash(f'প্রশ্ন আপডেট করার সময় ত্রুটি হয়েছে: {str(e)}', 'danger')
    classes = ClassLevel.query.order_by(ClassLevel.name).all()
    subjects_for_selected_class = []
    selected_class_id_for_form = question.subject.class_level_id
    if selected_class_id_for_form:
        current_selected_class = ClassLevel.query.get(selected_class_id_for_form)
        if current_selected_class: subjects_for_selected_class = sorted(current_selected_class.subjects, key=lambda s: s.name)
    return render_template('extra/admin/comprehension_question_editor.html',
                           question=question, classes=classes, subjects_for_selected_class=subjects_for_selected_class,
                           selected_class_id=selected_class_id_for_form, selected_subject_id=question.subject_id)

@admin_extra_bp.route('/comprehension/delete/<int:q_id>', methods=['POST'])
@login_required
@admin_required
def delete_comprehension_question(q_id):
    question = ComprehensionQuestion.query.get_or_404(q_id)
    class_id_redirect = question.subject.class_level_id
    subject_id_redirect = question.subject_id
    try:
        db.session.delete(question)
        UserReadStatus.query.filter_by(question_type='comprehension', question_id=q_id).delete()
        db.session.commit()
        flash('অনুধাবনমূলক প্রশ্ন সফলভাবে ডিলিট করা হয়েছে।', 'success')
    except Exception as e: db.session.rollback(); flash(f'প্রশ্ন ডিলিট করার সময় ত্রুটি হয়েছে: {str(e)}', 'danger')
    return redirect(url_for('admin_extra.list_comprehension_questions', class_id=class_id_redirect, subject_id=subject_id_redirect))

# --- Creative Question Management ---
@admin_extra_bp.route('/creative/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_creative_questions():
    classes = ClassLevel.query.order_by(ClassLevel.name).all()
    form_data = {
        'selected_class_id': request.form.get('class_id_selector', type=int) if request.method == 'POST' else None,
        'selected_subject_id': request.form.get('subject_id', type=int) if request.method == 'POST' else None,
        'json_data': request.form.get('json_data', '') if request.method == 'POST' else ''
    }
    subjects_for_selected_class = []
    if form_data['selected_class_id']:
        current_selected_class = ClassLevel.query.get(form_data['selected_class_id'])
        if current_selected_class: subjects_for_selected_class = sorted(current_selected_class.subjects, key=lambda s: s.name)

    if request.method == 'POST':
        if not form_data['selected_subject_id'] or not form_data['json_data']: flash('শ্রেণী, বিষয় এবং JSON ডেটা আবশ্যক।', 'danger')
        else:
            subject = Subject.query.get(form_data['selected_subject_id'])
            if not subject: flash('নির্বাচিত বিষয় খুঁজে পাওয়া যায়নি।', 'danger')
            elif subject.class_level_id != form_data['selected_class_id']: flash('নির্বাচিত বিষয় এবং শ্রেণীর মধ্যে গরমিল রয়েছে।', 'danger')
            else:
                try:
                    data = json.loads(form_data['json_data'])
                    if 'questions' not in data or not isinstance(data['questions'], list):
                        raise ValueError("JSON এর মূল 'questions' একটি তালিকা (array) হতে হবে।")
                    added_count = 0; error_messages = []
                    for idx, q_item in enumerate(data['questions']):
                        q_err_prefix = f"সৃজনশীল আইটেম {idx+1}"; stimulus_text = q_item.get('stimulus_text', '').strip(); parts = q_item.get('parts')
                        if not stimulus_text: error_messages.append(f"{q_err_prefix}: 'stimulus_text' আবশ্যক।"); continue
                        if not parts or not isinstance(parts, list) or len(parts) != 4: error_messages.append(f"{q_err_prefix}: 'parts' সেকশনে ঠিক ৪টি প্রশ্ন-উত্তর (অবজেক্ট) অ্যারে হিসেবে থাকতে হবে।"); continue
                        valid_parts = True
                        for part_idx, part_item in enumerate(parts):
                            if not isinstance(part_item, dict) or not part_item.get('question_text') or not part_item.get('answer_text'):
                                error_messages.append(f"{q_err_prefix}, অংশ {part_idx+1}: প্রতিটি অংশে 'question_text' এবং 'answer_text' আবশ্যক।"); valid_parts = False; break
                        if not valid_parts: continue

                        stimulus_id = get_or_create_stimulus(stimulus_text)
                        if stimulus_id is None: 
                            error_messages.append(f"{q_err_prefix}: উদ্দীপক টেক্সট প্রদান করা আবশ্যক এবং এটি খালি হতে পারবে না।"); continue

                        parts_json = json.dumps([{"question_text": str(p['question_text']).strip(), "answer_text": str(p['answer_text']).strip()} for p in parts])
                        new_creative_q = CreativeQuestion(subject_id=subject.id, stimulus_id=stimulus_id, parts_data=parts_json, created_by_admin_id=current_user.id)
                        db.session.add(new_creative_q); added_count += 1
                    if error_messages:
                        for err in error_messages: flash(err, 'warning')
                        if added_count > 0: db.session.commit()
                        else: db.session.rollback()
                        flash(f"{added_count} টি সৃজনশীল প্রশ্ন যোগ করা হয়েছে। কিছু ত্রুটি থাকতে পারে।", 'info')
                    elif added_count > 0:
                        db.session.commit(); flash(f'{added_count} টি সৃজনশীল প্রশ্ন সফলভাবে যোগ করা হয়েছে।', 'success')
                        return redirect(url_for('admin_extra.list_creative_questions', class_id=subject.class_level_id, subject_id=subject.id))
                    else: flash('JSON ডেটাতে কোনো প্রশ্ন পাওয়া যায়নি বা যোগ করার মতো সঠিক প্রশ্ন ছিল না।', 'info')
                except (json.JSONDecodeError, ValueError) as e: db.session.rollback(); flash(f'JSON পার্সিং বা ডেটা ভ্যালিডেশনে ত্রুটি: {e}', 'danger')
                except Exception as e: db.session.rollback(); flash(f'সৃজনশীল প্রশ্ন যোগে অপ্রত্যাশিত ত্রুটি: {e}', 'danger')
        return render_template('extra/admin/creative_question_adder.html',
                               classes=classes, selected_class_id=form_data['selected_class_id'],
                               subjects_for_selected_class=subjects_for_selected_class,
                               selected_subject_id=form_data['selected_subject_id'], json_data=form_data['json_data'])
    return render_template('extra/admin/creative_question_adder.html',
                           classes=classes, selected_class_id=None, subjects_for_selected_class=[],
                           selected_subject_id=None,json_data='')

@admin_extra_bp.route('/creative/list', defaults={'class_id': None, 'subject_id': None})
@admin_extra_bp.route('/creative/list/class/<int:class_id>', defaults={'subject_id': None})
@admin_extra_bp.route('/creative/list/class/<int:class_id>/subject/<int:subject_id>')
@login_required
@admin_required
def list_creative_questions(class_id, subject_id):
    query = CreativeQuestion.query.join(Subject).join(ClassLevel).options(db.joinedload(CreativeQuestion.stimulus))
    classes_all = ClassLevel.query.order_by(ClassLevel.name).all(); subjects_for_filter = []; selected_class_obj = None; selected_subject_obj = None
    if class_id:
        selected_class_obj = ClassLevel.query.get(class_id)
        if selected_class_obj: query = query.filter(Subject.class_level_id == class_id); subjects_for_filter = sorted(selected_class_obj.subjects, key=lambda s: s.name)
        else: flash(f"শ্রেণী আইডি {class_id} খুঁজে পাওয়া যায়নি।", "warning"); class_id = None
    if subject_id and selected_class_obj:
        selected_subject_obj = Subject.query.filter_by(id=subject_id, class_level_id=class_id).first()
        if selected_subject_obj: query = query.filter(CreativeQuestion.subject_id == subject_id)
        else: flash(f"বিষয় আইডি {subject_id} শ্রেণী '{selected_class_obj.name}' এর অধীনে খুঁজে পাওয়া যায়নি।", "warning"); subject_id = None
    elif subject_id and not selected_class_obj: flash("বিষয় ফিল্টার করার জন্য অনুগ্রহ করে প্রথমে শ্রেণী নির্বাচন করুন।", "warning"); subject_id = None
    questions = query.order_by(ClassLevel.name, Subject.name, CreativeQuestion.id.desc()).all()
    return render_template('extra/admin/creative_question_list.html',
                           questions=questions, classes=classes_all, subjects_for_filter=subjects_for_filter,
                           selected_class=selected_class_obj, selected_subject=selected_subject_obj)

@admin_extra_bp.route('/creative/edit/<int:q_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_creative_question(q_id):
    question = CreativeQuestion.query.options(db.joinedload(CreativeQuestion.stimulus)).get_or_404(q_id)

    if request.method == 'POST':
        new_subject_id_str = request.form.get('subject_id')
        new_stimulus_text = request.form.get('stimulus_text', '').strip()

        new_parts_list = []
        valid_parts_submission = True
        for i in range(1, 5): 
            part_q_key = f'part_q_{i}'
            part_a_key = f'part_a_{i}'

            part_q_value = request.form.get(part_q_key)
            part_a_value = request.form.get(part_a_key)

            if not part_q_value or not part_a_value:
                valid_parts_submission = False
                break
            new_parts_list.append({"question_text": part_q_value.strip(), "answer_text": part_a_value.strip()})

        if not new_subject_id_str or not new_stimulus_text or not valid_parts_submission:
            flash('বিষয়, উদ্দীপক এবং ৪টি অংশের প্রশ্ন ও উত্তর (প্রতিটির জন্য) আবশ্যক।', 'danger')
        else:
            try:
                new_subject_id = int(new_subject_id_str)
                target_subject = Subject.query.get(new_subject_id)
                if not target_subject:
                    flash("অবৈধ বিষয় নির্বাচন করা হয়েছে।", "danger")
                    raise ValueError("Invalid subject ID")

                current_stimulus_id = question.stimulus_id
                current_stimulus_text = question.stimulus.text if question.stimulus else ""
                updated_stimulus_id = current_stimulus_id

                if current_stimulus_text != new_stimulus_text:
                    if not new_stimulus_text: 
                        flash("উদ্দীপক টেক্সট খালি হতে পারবে না যদি এটি পরিবর্তন করা হয়।", "danger") # সামান্য পরিবর্তন
                        raise ValueError("Stimulus text cannot be empty if it's being changed.")

                    existing_stimulus_with_new_text = Stimulus.query.filter(Stimulus.text == new_stimulus_text).first()
                    if existing_stimulus_with_new_text:
                        updated_stimulus_id = existing_stimulus_with_new_text.id
                    else:
                        new_stim_obj = Stimulus(text=new_stimulus_text)
                        db.session.add(new_stim_obj)
                        db.session.flush()
                        updated_stimulus_id = new_stim_obj.id

                if current_stimulus_id is not None and current_stimulus_id != updated_stimulus_id:
                    is_old_stimulus_used_elsewhere = MCQ.query.filter_by(stimulus_id=current_stimulus_id).first() or \
                                                     CreativeQuestion.query.filter(CreativeQuestion.id != q_id, CreativeQuestion.stimulus_id == current_stimulus_id).first()
                    if not is_old_stimulus_used_elsewhere:
                        stimulus_to_delete = Stimulus.query.get(current_stimulus_id)
                        if stimulus_to_delete:
                            db.session.delete(stimulus_to_delete)

                question.subject_id = new_subject_id
                question.stimulus_id = updated_stimulus_id 
                question.parts_data = json.dumps(new_parts_list)

                db.session.commit()
                flash('সৃজনশীল প্রশ্ন সফলভাবে আপডেট করা হয়েছে।', 'success')
                redirect_class_id = target_subject.class_level_id
                redirect_subject_id = target_subject.id
                return redirect(url_for('admin_extra.list_creative_questions', class_id=redirect_class_id, subject_id=redirect_subject_id))

            except ValueError as ve:
                 # যদি ValueError আগেই flash করা না হয়ে থাকে
                if 'Stimulus text cannot be empty' not in str(ve) and 'Invalid subject ID' not in str(ve):
                    flash(str(ve), 'danger')
                # ডিবাগিং এর জন্য প্রিন্ট করা যেতে পারে
                print(f"ValueError during creative question edit (POST): {ve}")
            except Exception as e:
                db.session.rollback()
                flash(f'সৃজনশীল প্রশ্ন আপডেট করার সময় একটি অপ্রত্যাশিত ত্রুটি হয়েছে: {str(e)}', 'danger')
                print(f"Unexpected error during creative question edit (POST): {e}")
                # সম্পূর্ণ ট্রেসবেক প্রিন্ট করা যেতে পারে ডিবাগিং এর জন্য
                import traceback
                traceback.print_exc()


    # --- GET অনুরোধ বা POST ব্যর্থ হলে টেমপ্লেটের জন্য ভেরিয়েবল প্রস্তুত করা ---
    classes = ClassLevel.query.order_by(ClassLevel.name).all()
    subjects_for_selected_class = []

    # GET: ডেটাবেস থেকে মান; POST ব্যর্থ হলে: ফর্ম থেকে মান অথবা ডেটাবেস থেকে ফলব্যাক
    selected_class_id_to_render = int(request.form.get('class_id_selector_disabled_visual_hack', question.subject.class_level_id)) if request.method == 'POST' else question.subject.class_level_id
    selected_subject_id_to_render = int(request.form.get('subject_id', question.subject_id)) if request.method == 'POST' else question.subject_id

    if selected_class_id_to_render:
        current_selected_class = ClassLevel.query.get(selected_class_id_to_render)
        if current_selected_class:
            subjects_for_selected_class = sorted(current_selected_class.subjects, key=lambda s: s.name)

    stimulus_text_to_render = request.form.get('stimulus_text', question.stimulus.text if question.stimulus else "")

    parts_to_render = []
    db_parts_list = question.get_parts_data_dict_list() # ডেটাবেস থেকে আসা পার্টস

    # POST অনুরোধ হলে এবং ফর্মে ডেটা থাকলে সেই ডেটা ব্যবহার করা হবে, অন্যথায় ডেটাবেসের ডেটা
    # এই লজিকটি নিশ্চিত করে যে ভ্যালিডেশন ফেইল করলে ব্যবহারকারীর ইনপুটগুলো যেন থেকে যায়
    if request.method == 'POST': 
        for i in range(4):
            q_val = request.form.get(f'part_q_{i+1}')
            a_val = request.form.get(f'part_a_{i+1}')
            # যদি ফর্মে মান না থাকে (যেমন, GET এর সময় request.form খালি থাকবে, অথবা POST এ ফিল্ড মিসিং)
            # এবং db_parts_list এ ডেটা থাকে, তাহলে সেটা ব্যবহার করা হবে।
            # কিন্তু POST এর ক্ষেত্রে, ব্যবহারকারী যদি কিছু খালি রাখে, সেটাই দেখানো উচিত।
            parts_to_render.append({
                "question_text": q_val if q_val is not None else (db_parts_list[i].get('question_text') if i < len(db_parts_list) else ""),
                "answer_text": a_val if a_val is not None else (db_parts_list[i].get('answer_text') if i < len(db_parts_list) else "")
            })
    else: # GET রিকোয়েস্ট
        parts_to_render = db_parts_list

    # ডিবাগিং প্রিন্ট (প্রয়োজনে ব্যবহার করুন)
    # print(f"--- Debugging edit_creative_question (before render_template GET/POST FAIL) ---")
    # print(f"stimulus_text_to_render: '{stimulus_text_to_render}', type: {type(stimulus_text_to_render)}")
    # print(f"parts_to_render: {parts_to_render}, type: {type(parts_to_render)}")
    # print(f"selected_class_id_to_render: {selected_class_id_to_render}, type: {type(selected_class_id_to_render)}")
    # print(f"selected_subject_id_to_render: {selected_subject_id_to_render}, type: {type(selected_subject_id_to_render)}")
    # print(f"-----------------------------------------------------------------")

    return render_template('extra/admin/creative_question_editor.html',
                           question=question, 
                           stimulus_text_val=str(stimulus_text_to_render), 
                           parts_val=parts_to_render,
                           classes=classes, 
                           subjects_for_selected_class=subjects_for_selected_class,
                           selected_class_id=selected_class_id_to_render, 
                           selected_subject_id=selected_subject_id_to_render )


@admin_extra_bp.route('/creative/delete/<int:q_id>', methods=['POST'])
@login_required
@admin_required
def delete_creative_question(q_id):
    question = CreativeQuestion.query.get_or_404(q_id); stimulus_id_to_check = question.stimulus_id
    class_id_redirect = question.subject.class_level_id; subject_id_redirect = question.subject_id
    try:
        db.session.delete(question)
        UserReadStatus.query.filter_by(question_type='creative', question_id=q_id).delete()
        db.session.flush() 
        if stimulus_id_to_check:
            mcq_uses_stimulus = MCQ.query.filter_by(stimulus_id=stimulus_id_to_check).first()
            cq_uses_stimulus = CreativeQuestion.query.filter_by(stimulus_id=stimulus_id_to_check).first()
            if not mcq_uses_stimulus and not cq_uses_stimulus:
                stim_to_delete = Stimulus.query.get(stimulus_id_to_check)
                if stim_to_delete: 
                    db.session.delete(stim_to_delete)
        db.session.commit(); flash('সৃজনশীল প্রশ্ন সফলভাবে ডিলিট করা হয়েছে।', 'success')
    except Exception as e: db.session.rollback(); flash(f'প্রশ্ন ডিলিট করার সময় ত্রুটি হয়েছে: {str(e)}', 'danger')
    return redirect(url_for('admin_extra.list_creative_questions', class_id=class_id_redirect, subject_id=subject_id_redirect))

# admin_extra.py (ফাইলের শেষে নতুন রুট যোগ করুন)

# ... (আগের সব কোড অপরিবর্তিত থাকবে) ...

# --- Extra Questions Dashboard ---
@admin_extra_bp.route('/dashboard')
@login_required
@admin_required
def extra_dashboard():
    try:
        short_q_count = ShortQuestion.query.count()
        comprehension_q_count = ComprehensionQuestion.query.count()
        creative_q_count = CreativeQuestion.query.count()
    except Exception as e:
        flash(f"ড্যাশবোর্ডের তথ্য আনতে সমস্যা হয়েছে: {str(e)}", "danger")
        short_q_count = 0
        comprehension_q_count = 0
        creative_q_count = 0
        
    return render_template('extra/admin/extra_dashboard.html',
                           short_q_count=short_q_count,
                           comprehension_q_count=comprehension_q_count,
                           creative_q_count=creative_q_count)