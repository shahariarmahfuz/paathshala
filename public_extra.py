# public_extra.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from sqlalchemy import func, desc, or_
from database import db, ClassLevel, Subject, ShortQuestion, ComprehensionQuestion, CreativeQuestion, UserReadStatus
import random

public_extra_bp = Blueprint('public_extra', __name__, url_prefix='/extra')

# Helper function to get subjects for a class - can be reused if publicly accessible
# Assuming public_routes.ajax_public_get_subjects_for_class can be used by templates
# or one can be added here if needed.

@public_extra_bp.route('/select', methods=['GET', 'POST'])
@login_required
def select_extra_questions():
    classes = ClassLevel.query.order_by(ClassLevel.name).all()

    if request.method == 'POST':
        try:
            class_id_str = request.form.get('class_id_selector_public_extra')
            subject_id_str = request.form.get('subject_id_public_extra')
            question_type = request.form.get('question_type_extra') # 'short', 'comprehension', 'creative'

            if not class_id_str or not subject_id_str or not question_type:
                flash('অনুগ্রহ করে শ্রেণী, বিষয় এবং প্রশ্নের ধরন নির্বাচন করুন।', 'warning')
                return redirect(url_for('public_extra.select_extra_questions'))

            class_id = int(class_id_str)
            subject_id = int(subject_id_str)

            # Store selection in session to be used by the view route
            session['extra_q_params'] = {
                'class_id': class_id,
                'subject_id': subject_id,
                'question_type': question_type
            }
            session.modified = True

            # Redirect to the appropriate view function based on question_type
            if question_type == 'short':
                return redirect(url_for('public_extra.view_short_questions'))
            elif question_type == 'comprehension':
                return redirect(url_for('public_extra.view_comprehension_questions'))
            elif question_type == 'creative':
                return redirect(url_for('public_extra.view_creative_questions'))
            else:
                flash('অবৈধ প্রশ্নের ধরন।', 'danger')
                return redirect(url_for('public_extra.select_extra_questions'))

        except ValueError:
            flash('অবৈধ ইনপুট। অনুগ্রহ করে সঠিকভাবে তথ্য দিন।', 'danger')
        except Exception as e:
            print(f"Error in select_extra_questions: {e}")
            flash('একটি ত্রুটি ঘটেছে। অনুগ্রহ করে আবার চেষ্টা করুন।', 'danger')
        return redirect(url_for('public_extra.select_extra_questions'))

    # For GET request, or if POST fails and redirects back
    selected_class_id = session.get('extra_q_params', {}).get('class_id')
    selected_subject_id = session.get('extra_q_params', {}).get('subject_id')
    selected_q_type = session.get('extra_q_params', {}).get('question_type')

    subjects_for_selected_class = []
    if selected_class_id:
        current_selected_class = ClassLevel.query.get(selected_class_id)
        if current_selected_class:
            subjects_for_selected_class = sorted(current_selected_class.subjects, key=lambda s: s.name)

    return render_template('extra/public/select_extra_questions.html',
                           classes=classes,
                           selected_class_id=selected_class_id,
                           subjects_for_selected_class=subjects_for_selected_class,
                           selected_subject_id=selected_subject_id,
                           selected_q_type=selected_q_type)


def get_questions_for_view(question_model, subject_id, user_id, per_page, page):
    """
    Helper function to fetch questions (short, comprehension, or creative)
    with "previously read" status and pagination.
    Prioritizes unread questions.
    """
    # Get all question IDs for the subject
    all_q_ids_query = db.session.query(question_model.id).filter(question_model.subject_id == subject_id)
    all_q_ids = [q.id for q in all_q_ids_query.all()]

    if not all_q_ids:
        return [], 0 # No questions available

    # Get IDs of questions already read by the user for this type
    read_q_ids_query = db.session.query(UserReadStatus.question_id)\
        .filter(UserReadStatus.user_id == user_id,
                UserReadStatus.question_type == question_model.__tablename__.replace('_question',''), # 'short', 'comprehension', 'creative'
                UserReadStatus.question_id.in_(all_q_ids))
    read_q_ids = {r.question_id for r in read_q_ids_query.all()}

    unread_q_ids = [qid for qid in all_q_ids if qid not in read_q_ids]

    # Prioritize unread questions
    # If not enough unread, supplement with read questions (randomly for now, could be oldest read)

    final_query_ids = list(unread_q_ids) # Take all unread first

    # If we need to show already read questions because unread are exhausted for the *entire subject*
    # (not just for the current page, but for the overall pool)
    # For pagination, we might fetch a larger pool first then paginate from that pool.
    # Current approach: fetch all unread, then all read, then paginate combined list.

    questions_to_fetch_ordered = []

    if unread_q_ids:
        unread_questions = question_model.query.filter(question_model.id.in_(unread_q_ids)).order_by(func.random()).all() # Randomize unread
        questions_to_fetch_ordered.extend(unread_questions)

    # If we always want to show a mix, or if unread are less than per_page and we need to fill up with read ones
    # For simplicity now, let's consider if unread_q_ids are less than total items in subject
    if len(unread_q_ids) < len(all_q_ids): # Meaning some questions have been read
        actually_read_q_ids_list = [qid for qid in all_q_ids if qid in read_q_ids]
        if actually_read_q_ids_list:
            read_questions_obj = question_model.query.filter(question_model.id.in_(actually_read_q_ids_list)).order_by(func.random()).all() # Randomize read
            questions_to_fetch_ordered.extend(read_questions_obj)

    # Manual pagination from the combined list
    total_items = len(questions_to_fetch_ordered)
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    paginated_questions_objects = questions_to_fetch_ordered[start_index:end_index]

    # Attach 'previously_read' status and mark newly displayed as read
    questions_with_status = []
    for q_obj in paginated_questions_objects:
        previously_read = q_obj.id in read_q_ids
        questions_with_status.append({'question': q_obj, 'previously_read': previously_read})

        # Mark as read if not already
        if not previously_read:
            new_read_status = UserReadStatus(
                user_id=user_id,
                question_type=question_model.__tablename__.replace('_question',''),
                question_id=q_obj.id
            )
            db.session.add(new_read_status)
            read_q_ids.add(q_obj.id) # Add to current session's understanding of read IDs

    if paginated_questions_objects: # Only commit if we actually displayed and potentially marked questions as read
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error committing read statuses: {e}")
            # Decide if to flash a message or handle silently

    # For pagination controls, we need total pages based on all_q_ids
    total_pages_for_pagination = (len(all_q_ids) + per_page - 1) // per_page

    return questions_with_status, total_pages_for_pagination


@public_extra_bp.route('/short', methods=['GET'])
@login_required
def view_short_questions():
    params = session.get('extra_q_params')
    if not params or params.get('question_type') != 'short':
        flash('অনুগ্রহ করে প্রথমে সংক্ষিপ্ত প্রশ্নের জন্য বিষয় নির্বাচন করুন।', 'info')
        return redirect(url_for('public_extra.select_extra_questions'))

    subject_id = params['subject_id']
    page = request.args.get('page', 1, type=int)
    per_page = 10 # 10 short questions per page

    subject = Subject.query.get_or_404(subject_id)
    questions_data, total_pages = get_questions_for_view(ShortQuestion, subject_id, current_user.id, per_page, page)

    if not questions_data and page > 1: # If on a page with no questions, redirect to page 1
        return redirect(url_for('public_extra.view_short_questions', page=1))

    if not questions_data and page == 1:
        flash(f"'{subject.name}' বিষয়ে এই মুহূর্তে কোনো সংক্ষিপ্ত প্রশ্ন নেই অথবা সব প্রশ্ন পড়া হয়ে গেছে (এবং নতুন কোনো অপঠিত প্রশ্ন নেই)।", 'info')
        # Optionally, clear session params if no questions at all for this subject
        # session.pop('extra_q_params', None)
        # return redirect(url_for('public_extra.select_extra_questions'))


    return render_template('extra/public/view_extra_questions.html',
                           questions_data=questions_data,
                           subject=subject,
                           question_type_name="সংক্ষিপ্ত প্রশ্ন",
                           question_type_key='short', # for pagination links if needed
                           current_page=page,
                           total_pages=total_pages,
                           per_page=per_page)


@public_extra_bp.route('/comprehension', methods=['GET'])
@login_required
def view_comprehension_questions():
    params = session.get('extra_q_params')
    if not params or params.get('question_type') != 'comprehension':
        flash('অনুগ্রহ করে প্রথমে অনুধাবনমূলক প্রশ্নের জন্য বিষয় নির্বাচন করুন।', 'info')
        return redirect(url_for('public_extra.select_extra_questions'))

    subject_id = params['subject_id']
    page = request.args.get('page', 1, type=int)
    per_page = 5 # 5 comprehension questions per page

    subject = Subject.query.get_or_404(subject_id)
    questions_data, total_pages = get_questions_for_view(ComprehensionQuestion, subject_id, current_user.id, per_page, page)

    if not questions_data and page > 1:
        return redirect(url_for('public_extra.view_comprehension_questions', page=1))

    if not questions_data and page == 1:
        flash(f"'{subject.name}' বিষয়ে এই মুহূর্তে কোনো অনুধাবনমূলক প্রশ্ন নেই অথবা সব প্রশ্ন পড়া হয়ে গেছে।", 'info')

    return render_template('extra/public/view_extra_questions.html',
                           questions_data=questions_data,
                           subject=subject,
                           question_type_name="অনুধাবনমূলক প্রশ্ন",
                           question_type_key='comprehension',
                           current_page=page,
                           total_pages=total_pages,
                           per_page=per_page)


@public_extra_bp.route('/creative', methods=['GET'])
@login_required
def view_creative_questions():
    params = session.get('extra_q_params')
    if not params or params.get('question_type') != 'creative':
        flash('অনুগ্রহ করে প্রথমে সৃজনশীল প্রশ্নের জন্য বিষয় নির্বাচন করুন।', 'info')
        return redirect(url_for('public_extra.select_extra_questions'))

    subject_id = params['subject_id']
    page = request.args.get('page', 1, type=int)
    per_page = 1 # 1 creative question per page

    subject = Subject.query.get_or_404(subject_id)
    # CreativeQuestion needs joinedload for stimulus

    # Slightly different handling for get_questions_for_view if it needs specific options
    # For now, assuming base model fetching is okay.
    # We will load stimulus and parts in the template or adapt get_questions_for_view if needed.

    questions_data, total_pages = get_questions_for_view(CreativeQuestion, subject_id, current_user.id, per_page, page)

    if not questions_data and page > 1:
        return redirect(url_for('public_extra.view_creative_questions', page=1))

    if not questions_data and page == 1:
        flash(f"'{subject.name}' বিষয়ে এই মুহূর্তে কোনো সৃজনশীল প্রশ্ন নেই অথবা সব প্রশ্ন পড়া হয়ে গেছে।", 'info')

    # Enhance questions_data with stimulus and parts for creative questions
    # This can also be done in the template using question.stimulus and question.get_parts_data_dict_list()

    return render_template('extra/public/view_creative_question.html', # Specific template for creative
                           questions_data=questions_data, # Will contain one item typically
                           subject=subject,
                           question_type_name="সৃজনশীল প্রশ্ন",
                           question_type_key='creative',
                           current_page=page,
                           total_pages=total_pages,
                           per_page=per_page)