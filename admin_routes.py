# admin_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from database import db, Subject, MCQ, Stimulus, User, ClassLevel # ClassLevel ইম্পোর্ট করা হয়েছে
import json
from functools import wraps

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('এই পৃষ্ঠা অ্যাক্সেস করার জন্য আপনার অ্যাডমিন অনুমতি প্রয়োজন।', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    return render_template('admin/dashboard.html', 
                           user_count=User.query.count(), 
                           class_count=ClassLevel.query.count(),
                           subject_count=Subject.query.count(), 
                           mcq_count=MCQ.query.count())

# --- ClassLevel (শ্রেণী) Management ---
@admin_bp.route('/classes', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_classes():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        if not name:
            flash('শ্রেণীর নাম দেওয়া আবশ্যক।', 'danger')
        elif ClassLevel.query.filter_by(name=name).first():
            flash('এই নামের শ্রেণী আগে থেকেই রয়েছে।', 'warning')
        else:
            try:
                new_class = ClassLevel(name=name, description=description)
                db.session.add(new_class)
                db.session.commit()
                flash('নতুন শ্রেণী সফলভাবে যোগ করা হয়েছে।', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'শ্রেণী যোগ করার সময় ত্রুটি হয়েছে: {str(e)}', 'danger')
        return redirect(url_for('admin.manage_classes'))

    classes = ClassLevel.query.order_by(ClassLevel.name).all()
    return render_template('admin/class_manager.html', classes=classes)

@admin_bp.route('/classes/edit/<int:class_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_class(class_id):
    class_level = ClassLevel.query.get_or_404(class_id)
    if request.method == 'POST':
        new_name = request.form.get('name')
        new_description = request.form.get('description')

        if not new_name:
            flash('শ্রেণীর নাম দেওয়া আবশ্যক।', 'danger')
        elif new_name != class_level.name and ClassLevel.query.filter_by(name=new_name).first():
            flash('এই নামের অন্য একটি শ্রেণী রয়েছে। অনুগ্রহ করে ভিন্ন নাম দিন।', 'warning')
        else:
            try:
                class_level.name = new_name
                class_level.description = new_description
                db.session.commit()
                flash('শ্রেণী সফলভাবে আপডেট করা হয়েছে।', 'success')
                return redirect(url_for('admin.manage_classes'))
            except Exception as e:
                db.session.rollback()
                flash(f'শ্রেণী আপডেট করার সময় ত্রুটি হয়েছে: {str(e)}', 'danger')
    return render_template('admin/class_editor.html', class_level=class_level)

@admin_bp.route('/classes/delete/<int:class_id>', methods=['POST'])
@login_required
@admin_required
def delete_class(class_id):
    class_level = ClassLevel.query.get_or_404(class_id)
    try:
        db.session.delete(class_level) # Cascade delete subjects and MCQs
        db.session.commit()
        flash(f'\'{class_level.name}\' এবং এর অন্তর্গত সকল বিষয় ও MCQ সফলভাবে ডিলিট করা হয়েছে।', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'শ্রেণী ডিলিট করার সময় একটি ত্রুটি হয়েছে: {str(e)}', 'danger')
    return redirect(url_for('admin.manage_classes'))

# --- Subject Management (Updated) ---
@admin_bp.route('/subjects', methods=['GET', 'POST'])
@login_required
@admin_required
def subject_manager():
    if request.method == 'POST': 
        name = request.form.get('name')
        description = request.form.get('description')
        class_level_id_str = request.form.get('class_level_id')

        if not name or not class_level_id_str:
            flash('বিষয়ের নাম এবং শ্রেণী নির্বাচন করা আবশ্যক।', 'danger')
        else:
            class_level_id = int(class_level_id_str)
            existing_subject = Subject.query.filter_by(name=name, class_level_id=class_level_id).first()
            if existing_subject:
                selected_class = ClassLevel.query.get(class_level_id)
                flash(f"'{selected_class.name}' শ্রেণীতে '{name}' নামের বিষয় আগে থেকেই রয়েছে।", 'warning')
            else:
                try:
                    new_subject = Subject(name=name, description=description, class_level_id=class_level_id)
                    db.session.add(new_subject)
                    db.session.commit()
                    flash('নতুন বিষয় সফলভাবে যোগ করা হয়েছে।', 'success')
                except Exception as e:
                    db.session.rollback(); flash(f'বিষয় যোগ করার সময় ত্রুটি হয়েছে: {str(e)}', 'danger')
        return redirect(url_for('admin.subject_manager'))

    subjects_query = Subject.query.join(ClassLevel).order_by(ClassLevel.name, Subject.name)
    filter_class_id = request.args.get('class_id', type=int)
    if filter_class_id:
        subjects_query = subjects_query.filter(Subject.class_level_id == filter_class_id)

    subjects = subjects_query.all()
    classes = ClassLevel.query.order_by(ClassLevel.name).all()
    return render_template('admin/subject_manager.html', subjects=subjects, classes=classes, filter_class_id=filter_class_id)

@admin_bp.route('/subjects/edit/<int:subject_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    classes = ClassLevel.query.order_by(ClassLevel.name).all()

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_description = request.form.get('description')
        new_class_level_id_str = request.form.get('class_level_id')

        if not new_name or not new_class_level_id_str:
            flash('বিষয়ের নাম এবং শ্রেণী নির্বাচন করা আবশ্যক।', 'danger')
        else:
            new_class_level_id = int(new_class_level_id_str)
            # Check for uniqueness only if name or class_level_id has changed
            if (new_name != subject.name or new_class_level_id != subject.class_level_id) and \
               Subject.query.filter(Subject.id != subject.id, Subject.name == new_name, Subject.class_level_id == new_class_level_id).first():
                # Added Subject.id != subject.id to allow saving if only description changed but name and class are same
                selected_class = ClassLevel.query.get(new_class_level_id)
                flash(f"'{selected_class.name}' শ্রেণীতে '{new_name}' নামের বিষয় আগে থেকেই রয়েছে।", 'warning')
            else:
                try:
                    subject.name = new_name
                    subject.description = new_description
                    subject.class_level_id = new_class_level_id
                    db.session.commit(); flash('বিষয় সফলভাবে আপডেট করা হয়েছে।', 'success')
                    return redirect(url_for('admin.subject_manager'))
                except Exception as e:
                    db.session.rollback(); flash(f'বিষয় আপডেট করার সময় ত্রুটি হয়েছে: {str(e)}', 'danger')
    return render_template('admin/mcq_subject_editor.html', subject=subject, classes=classes)

@admin_bp.route('/subjects/delete/<int:subject_id>', methods=['POST'])
@login_required
@admin_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    try:
        stimulus_ids_to_check = {mcq.stimulus_id for mcq in subject.mcqs if mcq.stimulus_id}
        db.session.delete(subject); db.session.commit()
        if stimulus_ids_to_check:
            for stim_id in stimulus_ids_to_check:
                if MCQ.query.filter_by(stimulus_id=stim_id).count() == 0:
                    stimulus_to_delete = Stimulus.query.get(stim_id)
                    if stimulus_to_delete: db.session.delete(stimulus_to_delete)
            db.session.commit()
        flash(f'\'{subject.name}\' বিষয়টি এবং এর অন্তর্গত সকল MCQ সফলভাবে ডিলিট করা হয়েছে।', 'success')
    except Exception as e:
        db.session.rollback(); flash(f'বিষয় ডিলিট করার সময় একটি ত্রুটি হয়েছে: {str(e)}', 'danger')
    return redirect(url_for('admin.subject_manager'))

# --- MCQ Management ---
@admin_bp.route('/mcq/add', methods=['GET', 'POST'])
@login_required
@admin_required
def mcq_adder():
    classes = ClassLevel.query.order_by(ClassLevel.name).all()

    # Initialize form_data for GET request or if POST fails
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
            flash('শ্রেণী, বিষয় এবং JSON ডেটা উভয়ই আবশ্যক। অনুগ্রহ করে প্রথমে শ্রেণী, তারপর বিষয় নির্বাচন করুন।', 'danger')
        else:
            subject = Subject.query.get(form_data['selected_subject_id'])
            if not subject:
                flash('নির্বাচিত বিষয় খুঁজে পাওয়া যায়নি।', 'danger')
            # Ensure the selected subject actually belongs to the selected class (consistency check)
            elif subject.class_level_id != form_data['selected_class_id']:
                flash('নির্বাচিত বিষয় এবং শ্রেণীর মধ্যে গরমিল রয়েছে।', 'danger')
            else:
                try:
                    data = json.loads(form_data['json_data'])
                    if 'questions' not in data or not isinstance(data['questions'], list):
                        raise ValueError('JSON এর মূল "questions" একটি তালিকা (array) হতে হবে।')

                    added_count = 0; error_messages = []
                    for idx, q_item in enumerate(data['questions']):
                        stim_id = None
                        if q_item.get('stimulus_text','').strip():
                            stim = Stimulus.query.filter_by(text=q_item['stimulus_text'].strip()).first()
                            if not stim:
                                stim = Stimulus(text=q_item['stimulus_text'].strip())
                                db.session.add(stim); db.session.flush()
                            stim_id = stim.id

                        qs_to_process = q_item.get('questions', [q_item] if 'question_text' in q_item else [])
                        if not qs_to_process: error_messages.append(f"আইটেম {idx+1}: প্রশ্ন পাওয়া যায়নি।")

                        for q_idx, q_detail in enumerate(qs_to_process):
                            q_err_prefix = f"আইটেম {idx+1}" + (f", প্রশ্ন {q_idx+1}" if len(qs_to_process) > 1 else "")
                            req_keys = ['question_text', 'question_type', 'options_data']
                            if not all(k in q_detail for k in req_keys):
                                error_messages.append(f"{q_err_prefix}: আবশ্যক কী ('question_text', 'question_type', 'options_data') অনুপস্থিত।"); continue
                            opts_data = q_detail['options_data']
                            if not isinstance(opts_data, dict) or not opts_data.get('correct_option'):
                                error_messages.append(f"{q_err_prefix}: 'options_data' সঠিক নয় বা 'correct_option' নেই/খালি।"); continue

                            q_type = q_detail['question_type']
                            if q_type == 'single_correct' and 'options' not in opts_data:
                                error_messages.append(f"{q_err_prefix}: সিঙ্গেল প্রশ্নের 'options_data' তে 'options' নেই।"); continue
                            if q_type == 'multi_statement' and ('statements' not in opts_data or 'option_map' not in opts_data):
                                error_messages.append(f"{q_err_prefix}: মাল্টি-স্টেটমেন্ট প্রশ্নের 'options_data' তে 'statements' বা 'option_map' নেই।"); continue

                            new_mcq = MCQ(
                                subject_id=subject.id, stimulus_id=stim_id,
                                question_type=q_type, 
                                question_text=q_detail['question_text'],
                                options_data=json.dumps(opts_data), 
                                created_by_admin_id=current_user.id
                            )
                            db.session.add(new_mcq); added_count += 1

                    if error_messages:
                        for err in error_messages: flash(err, 'warning')
                        # If errors occurred, MCQs might have been added before an error, so commit if any added.
                        # Or rollback all if partial success is not desired. For now, commit successes.
                        if added_count > 0: db.session.commit() 
                        else: db.session.rollback()
                        flash(f"{added_count} টি MCQ যোগ করা হয়েছে। কিছু ত্রুটি থাকতে পারে, অনুগ্রহ করে সতর্কবার্তা দেখুন।", 'info')
                    elif added_count > 0:
                        db.session.commit(); flash(f'{added_count} টি MCQ সফলভাবে যোগ করা হয়েছে।', 'success')
                        return redirect(url_for('admin.list_mcqs', class_id=subject.class_level_id, subject_id=subject.id))
                    else:
                        flash('JSON ডেটাতে কোনো প্রশ্ন পাওয়া যায়নি অথবা যোগ করার মতো কোনো সঠিক প্রশ্ন ছিল না।', 'info')
                except (json.JSONDecodeError, ValueError) as e:
                    db.session.rollback(); flash(f'JSON পার্সিং বা ডেটা ভ্যালিডেশনে ত্রুটি: {e}', 'danger')
                except Exception as e:
                    db.session.rollback(); flash(f'অপ্রত্যাশিত ত্রুটি: {e}', 'danger')

    return render_template('admin/mcq_adder.html', 
                           classes=classes,
                           selected_class_id=form_data['selected_class_id'],
                           subjects_for_selected_class=subjects_for_selected_class, # For repopulating subject dropdown
                           selected_subject_id=form_data['selected_subject_id'],
                           json_data=form_data['json_data'])


@admin_bp.route('/ajax/get-subjects-for-class/<int:class_id>')
@login_required
@admin_required
def ajax_get_subjects_for_class(class_id):
    class_level = ClassLevel.query.get_or_404(class_id)
    subjects_data = [{'id': subject.id, 'name': subject.name} for subject in sorted(class_level.subjects, key=lambda s: s.name)]
    return jsonify(subjects_data)


@admin_bp.route('/mcqs/', defaults={'class_id': None, 'subject_id': None})
@admin_bp.route('/mcqs/class/<int:class_id>', defaults={'subject_id': None})
@admin_bp.route('/mcqs/class/<int:class_id>/subject/<int:subject_id>')
@login_required
@admin_required
def list_mcqs(class_id, subject_id):
    classes = ClassLevel.query.order_by(ClassLevel.name).all()
    subjects_for_filter = [] 
    query = MCQ.query.join(Subject).join(ClassLevel)\
                     .options(db.joinedload(MCQ.stimulus), db.joinedload(MCQ.subject).joinedload(Subject.class_level))
    selected_class_obj = None
    selected_subject_obj = None

    if class_id:
        selected_class_obj = ClassLevel.query.get(class_id)
        if selected_class_obj:
            query = query.filter(Subject.class_level_id == class_id)
            subjects_for_filter = sorted(selected_class_obj.subjects, key=lambda s: s.name)
        else:
            flash(f"শ্রেণী আইডি {class_id} খুঁজে পাওয়া যায়নি।", "warning"); class_id = None
    if subject_id and selected_class_obj:
        selected_subject_obj = Subject.query.filter_by(id=subject_id, class_level_id=class_id).first()
        if selected_subject_obj:
            query = query.filter(MCQ.subject_id == subject_id)
        else:
            flash(f"বিষয় আইডি {subject_id} শ্রেণী '{selected_class_obj.name}' এর অধীনে খুঁজে পাওয়া যায়নি।", "warning"); subject_id = None
    elif subject_id and not selected_class_obj:
        flash("বিষয় ফিল্টার করার জন্য অনুগ্রহ করে প্রথমে শ্রেণী নির্বাচন করুন।", "warning"); subject_id = None

    mcqs_list = query.order_by(ClassLevel.name, Subject.name, MCQ.id.desc()).all()

    return render_template('admin/mcq_list.html', 
                           mcqs=mcqs_list, classes=classes,
                           subjects_for_filter=subjects_for_filter, 
                           selected_class=selected_class_obj,
                           selected_subject=selected_subject_obj)


@admin_bp.route('/mcq/edit/<int:mcq_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_mcq(mcq_id):
    mcq = MCQ.query.get_or_404(mcq_id)
    classes = ClassLevel.query.order_by(ClassLevel.name).all()

    # Get subjects for the MCQ's current class to pre-populate subject dropdown correctly
    subjects_for_selected_class = []
    if mcq.subject and mcq.subject.class_level:
        subjects_for_selected_class = sorted(mcq.subject.class_level.subjects, key=lambda s: s.name)

    if request.method == 'POST':
        try:
            new_subject_id = int(request.form['subject_id'])
            new_subject = Subject.query.get(new_subject_id)
            if not new_subject:
                flash("নির্বাচিত বিষয়টি সঠিক নয়।", "danger"); raise ValueError("Invalid subject_id")

            # Consistency check: selected subject must belong to selected class (from hidden or js-managed class field)
            # For simplicity, assuming subject_id is the sole determinant for now, implies class.
            # Or, add a hidden class_id field in form that's updated by JS when class_id_selector_edit changes.
            # For now, we trust the subject_id.

            mcq.subject_id = new_subject_id
            mcq.question_type = request.form['question_type']
            mcq.question_text = request.form['question_text']

            opts_data_str = request.form['options_data']
            parsed_opts = json.loads(opts_data_str)
            if not parsed_opts.get('correct_option'):
                raise ValueError("'options_data' তে 'correct_option' থাকতে হবে এবং এর মান খালি হবে না।")
            mcq.options_data = opts_data_str

            stim_text = request.form.get('stimulus_text','').strip()
            if stim_text:
                stim = Stimulus.query.filter_by(text=stim_text).first()
                if not stim:
                    stim = Stimulus(text=stim_text); db.session.add(stim); db.session.flush()
                if mcq.stimulus_id != stim.id:
                    old_stim_id = mcq.stimulus_id
                    mcq.stimulus_id = stim.id
                    if old_stim_id and MCQ.query.filter_by(stimulus_id=old_stim_id).count() == 0:
                        old_s = Stimulus.query.get(old_stim_id); 
                        if old_s: db.session.delete(old_s)
            elif mcq.stimulus_id:
                old_stim_id = mcq.stimulus_id; mcq.stimulus_id = None
                if MCQ.query.filter_by(stimulus_id=old_stim_id).count() == 0:
                    old_s = Stimulus.query.get(old_stim_id);
                    if old_s: db.session.delete(old_s)

            db.session.commit(); flash('MCQ সফলভাবে আপডেট করা হয়েছে।', 'success')
            return redirect(url_for('admin.list_mcqs', 
                                    class_id=mcq.subject.class_level_id, 
                                    subject_id=mcq.subject_id))
        except (json.JSONDecodeError, ValueError) as e:
            flash(f'JSON বা ডেটা ভ্যালিডেশনে ত্রুটি: {e}', 'danger')
        except Exception as e:
            db.session.rollback(); flash(f'MCQ আপডেটে ত্রুটি: {e}', 'danger')

    return render_template('admin/mcq_editor.html', mcq=mcq, 
                           classes=classes,
                           subjects_for_selected_class=subjects_for_selected_class, 
                           selected_class_id=mcq.subject.class_level_id, 
                           selected_subject_id=mcq.subject_id, 
                           stimulus_text=mcq.stimulus.text if mcq.stimulus else "")


@admin_bp.route('/mcq/delete/<int:mcq_id>', methods=['POST'])
@login_required
@admin_required
def delete_mcq(mcq_id):
    mcq = MCQ.query.get_or_404(mcq_id)
    stim_id = mcq.stimulus_id
    class_id_for_redirect = mcq.subject.class_level_id
    subject_id_for_redirect = mcq.subject_id
    try:
        db.session.delete(mcq); db.session.commit()
        if stim_id and MCQ.query.filter_by(stimulus_id=stim_id).count() == 0:
            stim = Stimulus.query.get(stim_id); 
            if stim: db.session.delete(stim); db.session.commit()
        flash('MCQ সফলভাবে ডিলিট করা হয়েছে।', 'success')
    except Exception as e:
        db.session.rollback(); flash(f'MCQ ডিলিটে ত্রুটি: {e}', 'danger')
    return redirect(url_for('admin.list_mcqs', class_id=class_id_for_redirect, subject_id=subject_id_for_redirect))