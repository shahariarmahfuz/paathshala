# public_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func 
from database import db, Subject, MCQ, UserAttempt, Stimulus, ClassLevel # ClassLevel ইম্পোর্ট করা হয়েছে
import random
import time

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
@login_required
def home():
    return render_template('home.html', username=current_user.username)

# --- নতুন AJAX রুট: একটি শ্রেণীর অধীনে থাকা বিষয়গুলো পাওয়ার জন্য ---
@public_bp.route('/ajax/public/get-subjects-for-class/<int:class_id>')
@login_required # এই রুটটি লগইন করা ব্যবহারকারীরা অ্যাক্সেস করতে পারবে
def ajax_public_get_subjects_for_class(class_id):
    class_level = ClassLevel.query.get_or_404(class_id)
    subjects_data = [{'id': subject.id, 'name': subject.name} for subject in class_level.subjects]
    return jsonify(subjects_data)
# --- AJAX রুট শেষ ---

@public_bp.route('/mcq/select', methods=['GET', 'POST'])
@login_required
def mcq_selection():
    classes = ClassLevel.query.order_by(ClassLevel.name).all() # শ্রেণীগুলো GET রিকোয়েস্টের জন্য

    if request.method == 'POST':
        try:
            # --- শ্রেণী এবং বিষয় আইডি ফর্ম থেকে নেওয়া হবে ---
            class_id_str = request.form.get('class_id_selector_public') # HTML এ এই আইডি ব্যবহার করা হবে
            subject_id_str = request.form.get('subject_id_public') # HTML এ এই আইডি ব্যবহার করা হবে
            # --- পরিবর্তন শেষ ---

            mode = request.form.get('mode') 
            num_questions_str = request.form.get('num_questions')
            time_per_question_str = request.form.get('time_per_question')

            if not class_id_str or not subject_id_str : # শ্রেণী এবং বিষয় উভয়ই আবশ্যক
                flash('অনুগ্রহ করে শ্রেণী এবং বিষয় নির্বাচন করুন।', 'warning')
                return redirect(url_for('public.mcq_selection'))

            class_id = int(class_id_str)
            subject_id = int(subject_id_str)

            if not num_questions_str or not num_questions_str.isdigit() or int(num_questions_str) <= 0:
                flash('প্রশ্নের সংখ্যা সঠিকভাবে দিন (একটি ধনাত্মক সংখ্যা)।', 'warning')
                return redirect(url_for('public.mcq_selection'))
            num_questions_req = int(num_questions_str)

            time_per_q = None
            if mode == 'timed':
                if not time_per_question_str or time_per_question_str not in ['30', '60']:
                    flash('টাইমড মোডের জন্য সময়সীমা (৩০ বা ৬০ সেকেন্ড) নির্বাচন করুন।', 'warning')
                    return redirect(url_for('public.mcq_selection'))
                time_per_q = int(time_per_question_str) 

            # সেশনে এখন class_id এবং subject_id দুটোই রাখা যেতে পারে, অথবা শুধু subject_id
            # যেহেতু subject_id একটি নির্দিষ্ট শ্রেণীর সাথেই যুক্ত, তাই শুধু subject_id রাখাই যথেষ্ট হতে পারে
            # তবে স্পষ্টতার জন্য দুটোই রাখা যেতে পারে
            session['mcq_params'] = {
                'class_id': class_id, # নতুন যোগ করা হলো
                'subject_id': subject_id,
                'mode': mode,
                'num_questions_requested': num_questions_req,
                'time_per_question': time_per_q 
            }

            # MCQ গুলো এখন নির্বাচিত subject_id অনুযায়ী আসবে, যা একটি নির্দিষ্ট শ্রেণীর অংশ
            all_mcqs_in_subject_list = MCQ.query.filter_by(subject_id=subject_id).all()
            if not all_mcqs_in_subject_list:
                selected_subject_obj = Subject.query.get(subject_id)
                flash(f"'{selected_subject_obj.name if selected_subject_obj else 'নির্বাচিত'}' বিষয়ে বর্তমানে কোনো MCQ নেই।", 'info')
                return redirect(url_for('public.mcq_selection'))

            # --- MCQ স্ট্যাটাস নির্ণয়ের লজিক (সর্বশেষ চেষ্টার উপর ভিত্তি করে) অপরিবর্তিত ---
            latest_attempt_timestamps_subquery = db.session.query(
                UserAttempt.mcq_id,
                func.max(UserAttempt.attempt_timestamp).label('latest_timestamp')
            ).join(MCQ, UserAttempt.mcq_id == MCQ.id)\
            .filter(UserAttempt.user_id == current_user.id)\
            .filter(MCQ.subject_id == subject_id)\
            .group_by(UserAttempt.mcq_id).subquery()

            latest_attempts_query = db.session.query(UserAttempt).join(
                latest_attempt_timestamps_subquery,
                db.and_(
                    UserAttempt.mcq_id == latest_attempt_timestamps_subquery.c.mcq_id,
                    UserAttempt.attempt_timestamp == latest_attempt_timestamps_subquery.c.latest_timestamp,
                    UserAttempt.user_id == current_user.id
                )
            ).all()

            latest_attempt_status_map = {attempt.mcq_id: attempt.is_correct for attempt in latest_attempts_query}

            unattempted_mcqs = []
            incorrect_on_latest_attempt_mcqs = [] 
            correct_on_latest_attempt_mcqs = []   

            for mcq_obj in all_mcqs_in_subject_list:
                if mcq_obj.id not in latest_attempt_status_map: 
                    unattempted_mcqs.append(mcq_obj)
                elif not latest_attempt_status_map[mcq_obj.id]: 
                    incorrect_on_latest_attempt_mcqs.append(mcq_obj)
                else: 
                    correct_on_latest_attempt_mcqs.append(mcq_obj)

            random.shuffle(unattempted_mcqs)
            random.shuffle(incorrect_on_latest_attempt_mcqs)
            random.shuffle(correct_on_latest_attempt_mcqs)

            selected_mcqs_for_session = []
            temp_selected_ids = set() 

            priority_mcq_sources = [
                (unattempted_mcqs, 'নতুন'),
                (incorrect_on_latest_attempt_mcqs, 'পূর্বে করেছেন (শেষবার ভুল ছিল)'),
                (correct_on_latest_attempt_mcqs, 'পূর্বে করেছেন (শেষবার সঠিক ছিল)')
            ]

            target_num = num_questions_req 

            for mcq_list, status_msg in priority_mcq_sources:
                for mcq_obj in mcq_list:
                    if len(selected_mcqs_for_session) < target_num and mcq_obj.id not in temp_selected_ids:
                        selected_mcqs_for_session.append({'id': mcq_obj.id, 'status': status_msg})
                        temp_selected_ids.add(mcq_obj.id)
                    if len(selected_mcqs_for_session) >= target_num: break
                if len(selected_mcqs_for_session) >= target_num: break

            if not selected_mcqs_for_session:
                flash('আপনার জন্য কোনো উপযুক্ত MCQ খুঁজে পাওয়া যায়নি।', 'info')
                return redirect(url_for('public.mcq_selection'))

            if len(selected_mcqs_for_session) < target_num:
                 flash(f"আপনার অনুরোধ অনুযায়ী {target_num}টি প্রশ্ন পাওয়া যায়নি। বর্তমানে {len(selected_mcqs_for_session)}টি প্রশ্ন দেখানো হচ্ছে।", "info")

            session['current_mcq_set'] = selected_mcqs_for_session
            session['current_mcq_index'] = 0
            session['user_answers_summary'] = [] 

            if mode == 'timed':
                session['mcq_start_times'] = {} 
            else:
                session.pop('mcq_start_times', None) 

            session.modified = True
            return redirect(url_for('public.mcq_show'))

        except ValueError: flash('অবৈধ ইনপুট। অনুগ্রহ করে সঠিকভাবে তথ্য দিন।', 'danger')
        except Exception as e: 
            print(f"Error in mcq_selection (User side): {e}") 
            flash(f'একটি ত্রুটি ঘটেছে। অনুগ্রহ করে আবার চেষ্টা করুন।', 'danger')
        return redirect(url_for('public.mcq_selection'))

    # GET রিকোয়েস্টের জন্য শুধু শ্রেণীগুলো পাঠানো হচ্ছে
    # বিষয়গুলো AJAX দিয়ে লোড হবে
    return render_template('mcq_html/mcq_selection.html', classes=classes)

# mcq_show, submit_answer, এবং mcq_summary ফাংশনগুলো আগের মতোই থাকবে
# কারণ তাদের লজিক mcq_params এ থাকা subject_id এর উপর নির্ভরশীল, যা mcq_selection এ সেট করা হয়।

@public_bp.route('/mcq/show', methods=['GET'])
@login_required
def mcq_show():
    # ... (এই ফাংশনটি আগের উত্তরে যেমন ছিল, তেমনই থাকবে) ...
    # এখানে কোনো পরিবর্তন প্রয়োজন নেই, কারণ এটি session['current_mcq_set'] থেকে mcq.id নিয়ে কাজ করে
    # এবং session['mcq_params'] থেকে mode ও time_limit নেয়, যা mcq_selection এ সেট করা হয়েছে।
    # mcq_start_times এর লজিকও আগের মতোই থাকবে।
    print("\nDEBUG (mcq_show - START)")
    if 'current_mcq_set' not in session or not session['current_mcq_set'] or \
       session['current_mcq_index'] >= len(session['current_mcq_set']):
        if session.get('user_answers_summary'): 
             return redirect(url_for('public.mcq_summary'))
        flash('পরীক্ষার জন্য কোনো প্রশ্ন সেট করা নেই অথবা পরীক্ষা সম্পন্ন হয়েছে।', 'info')
        return redirect(url_for('public.mcq_selection'))

    mcq_s_info = session['current_mcq_set'][session['current_mcq_index']]
    mcq = MCQ.query.get(mcq_s_info['id'])
    if not mcq:
        flash('প্রশ্ন খুঁজে পাওয়া যায়নি। পরবর্তী প্রশ্নে যাওয়া হচ্ছে।', 'danger')
        session['current_mcq_index'] += 1; session.modified = True
        return redirect(url_for('public.mcq_show'))

    print(f"DEBUG (mcq_show): Showing MCQ ID: {mcq.id}")

    stimulus_text = mcq.stimulus.text if mcq.stimulus_id and mcq.stimulus else None
    opts_data_dict = mcq.get_options_data_dict()
    curr_mcq_params = session.get('mcq_params', {})
    mode = curr_mcq_params.get('mode')
    time_limit = curr_mcq_params.get('time_per_question') if mode == 'timed' else None

    if mode == 'timed':
        if 'mcq_start_times' not in session: 
            session['mcq_start_times'] = {}
            print("WARNING (mcq_show): session['mcq_start_times'] was missing, re-initialized.")

        current_time = time.time()
        session['mcq_start_times'][str(mcq.id)] = current_time 
        session.modified = True
        print(f"DEBUG (mcq_show): Set/updated start_time for MCQ ID {mcq.id} to {current_time} in session['mcq_start_times']")

    print(f"DEBUG (mcq_show): Rendering template for MCQ ID: {mcq.id} with time_limit: {time_limit} (type: {type(time_limit)})")
    print(f"DEBUG (mcq_show): Status for display: {mcq_s_info.get('status', '')}")
    print("DEBUG (mcq_show - END)\n")

    return render_template('mcq_html/mcq_show.html', 
                           mcq=mcq, options_data=opts_data_dict, stimulus_text=stimulus_text,
                           current_q_number=session['current_mcq_index'] + 1,
                           total_questions=len(session['current_mcq_set']),
                           mode=mode, time_limit=time_limit, 
                           previously_done_status=mcq_s_info.get('status', ''))


@public_bp.route('/mcq/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    # ... (এই ফাংশনটি আগের উত্তরে যেমন ছিল, তেমনই থাকবে) ...
    # এখানে কোনো পরিবর্তন প্রয়োজন নেই
    print("\n--- DEBUG: submit_answer - START ---")
    if 'current_mcq_set' not in session or session['current_mcq_index'] >= len(session['current_mcq_set']):
        print("DEBUG: No active MCQ session or all questions answered.")
        return jsonify({'error': 'সেশন শেষ বা কোনো প্রশ্ন নেই।', 'next_url': url_for('public.mcq_summary')}), 400

    mcq_s_info = session['current_mcq_set'][session['current_mcq_index']]
    mcq = MCQ.query.get(mcq_s_info['id'])
    if not mcq: 
        print(f"DEBUG: MCQ not found for ID: {mcq_s_info.get('id')}")
        return jsonify({'error': 'প্রশ্ন খুঁজে পাওয়া যায়নি।', 'next_url': url_for('public.mcq_show')}), 404

    print(f"DEBUG: Processing MCQ ID: {mcq.id}")
    opts_data_dict = mcq.get_options_data_dict()
    user_ans_key = request.form.get('answer')
    is_client_timeout = request.form.get('timeout') == 'true'
    print(f"DEBUG: User Answer Key: {user_ans_key}, Is Client Timeout: {is_client_timeout}")

    is_correct = False; time_taken = None 
    curr_mcq_params = session.get('mcq_params', {})
    print(f"DEBUG: Current MCQ Params from session: {curr_mcq_params}")

    if curr_mcq_params.get('mode') == 'timed':
        print("DEBUG: Timed mode detected.")
        start_time = session.get('mcq_start_times', {}).get(str(mcq.id)) 

        if start_time:
            time_taken = int(time.time() - start_time) 
            print(f"DEBUG: Calculated time_taken: {time_taken} (type: {type(time_taken)})")
        else:
            print(f"WARNING: MCQ ID {mcq.id} (str: '{str(mcq.id)}') এর জন্য start_time পাওয়া যায়নি session['mcq_start_times'] এ। Keys: {list(session.get('mcq_start_times', {}).keys())}")
            time_taken = None 

        time_limit_from_s = curr_mcq_params.get('time_per_question')
        print(f"DEBUG: Raw time_limit_from_session: {time_limit_from_s} (type: {type(time_limit_from_s)})")

        time_limit_int = None 
        if time_limit_from_s is not None:
            if isinstance(time_limit_from_s, (int, float)):
                time_limit_int = int(time_limit_from_s)
            elif isinstance(time_limit_from_s, str):
                try:
                    time_limit_int = int(time_limit_from_s)
                except ValueError:
                    print(f"CRITICAL ERROR: সেশনে time_limit ভুল ফরম্যাটে (string not convertible to int): '{time_limit_from_s}'")
                    flash("সেশন ডেটাতে গুরুতর ত্রুটি (টাইম লিমিট)। অ্যাডমিনের সাথে যোগাযোগ করুন।", "danger")
                    return jsonify({'error': 'সেশন ত্রুটি (টাইম লিমিট)।', 'next_url': url_for('public.mcq_summary')}), 500
            else: 
                print(f"CRITICAL ERROR: সেশনে time_limit অপ্রত্যাশিত টাইপের: {time_limit_from_s} (type: {type(time_limit_from_s)})")
                flash("সেশন ডেটাতে অপ্রত্যাশিত টাইম লিমিট টাইপ।", "danger")
                return jsonify({'error': 'সেশন ডেটাতে অপ্রত্যাশিত টাইম লিমিট টাইপ।', 'next_url': url_for('public.mcq_summary')}), 500

        print(f"DEBUG: Final time_limit_int for comparison: {time_limit_int} (type: {type(time_limit_int)})")

        is_server_timeout = False
        if time_limit_int is not None and time_taken is not None:
            print(f"DEBUG: Attempting comparison: time_taken ({time_taken}) > time_limit_int ({time_limit_int})")
            try:
                if time_taken > time_limit_int: 
                    is_server_timeout = True
                    print("DEBUG: Server-side timeout detected.")
            except TypeError as e:
                print(f"!!!!!!!! CRITICAL TypeError CAUGHT DURING COMPARISON !!!!!!!!")
                print(f"Error details: {e}")
                print(f"Values: time_taken = {time_taken} (type: {type(time_taken)}), time_limit_int = {time_limit_int} (type: {type(time_limit_int)})")
                print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                flash("পরীক্ষার সময় গণনায় একটি মারাত্মক ত্রুটি হয়েছে। অ্যাডমিনের সাথে যোগাযোগ করুন।", "danger")
                return jsonify({'error': 'অভ্যন্তরীণ সার্ভার ত্রুটি (সময় গণনা)।', 'next_url': url_for('public.mcq_summary')}), 500
        else:
            print(f"DEBUG: Server timeout check skipped. time_limit_int: {time_limit_int}, time_taken: {time_taken}")

        if is_client_timeout or is_server_timeout:
            is_correct = False; user_ans_key = "TIMEOUT"
        elif user_ans_key == opts_data_dict.get('correct_option'): is_correct = True
        else: 
            is_correct = False
            if user_ans_key is None: user_ans_key = "NO_ANSWER"

    elif user_ans_key == opts_data_dict.get('correct_option'): is_correct = True
    else:
        is_correct = False
        if user_ans_key is None: user_ans_key = "NO_ANSWER"

    db.session.add(UserAttempt(user_id=current_user.id, mcq_id=mcq.id, selected_option=user_ans_key,
                               is_correct=is_correct, time_taken_seconds=time_taken))
    db.session.commit()
    print("DEBUG: UserAttempt saved to DB.")

    session['user_answers_summary'].append({
        'mcq_id': mcq.id, 'question_text': mcq.question_text,
        'stimulus_text': mcq.stimulus.text if mcq.stimulus_id and mcq.stimulus else None,
        'options_data': opts_data_dict, 'user_answer': user_ans_key,
        'is_correct': is_correct, 'correct_option_key': opts_data_dict.get('correct_option'),
        # 'explanation': mcq.explanation, # Explanation বাদ দেওয়া হয়েছে
        'time_taken': time_taken, 'question_type': mcq.question_type
    })

    session['current_mcq_index'] += 1; session.modified = True
    next_url = url_for('public.mcq_show') if session['current_mcq_index'] < len(session['current_mcq_set']) else url_for('public.mcq_summary')

    print(f"DEBUG: Next URL: {next_url}, Is Correct: {is_correct}")
    print("--- DEBUG: submit_answer - END ---\n")

    return jsonify({'correct': is_correct, 'correct_answer_key': opts_data_dict.get('correct_option'), 
                    'next_url': next_url, 'user_selected_key': user_ans_key})

@public_bp.route('/mcq/summary')
@login_required
def mcq_summary():
    # ... (এই ফাংশনটি আগের উত্তরে যেমন ছিল, তেমনই থাকবে) ...
    summary_data = session.get('user_answers_summary')
    if not summary_data:
        flash('কোনো পরীক্ষার সারাংশ পাওয়া যায়নি। একটি নতুন পরীক্ষা শুরু করুন।', 'info')
        return redirect(url_for('public.mcq_selection'))

    total_q = len(summary_data); correct_ans = sum(1 for ans in summary_data if ans['is_correct'])
    score = (correct_ans / total_q) * 100 if total_q > 0 else 0

    avg_time = None
    times = [ans['time_taken'] for ans in summary_data if ans.get('time_taken') is not None]
    if times: avg_time = sum(times) / len(times)

    page_summary_data = list(summary_data)

    session.pop('current_mcq_set', None)
    session.pop('current_mcq_index', None)
    session.pop('mcq_start_times', None)
    session.pop('user_answers_summary', None) 
    session.pop('mcq_params', None)

    return render_template('mcq_html/mcq_summary.html', 
                           summary_data=page_summary_data, 
                           total_questions=total_q, 
                           correct_answers=correct_ans, 
                           score=score, 
                           average_time=avg_time)