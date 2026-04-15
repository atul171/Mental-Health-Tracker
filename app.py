from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import random
import requests as http_requests
from pymongo import MongoClient
import certifi
from werkzeug.security import generate_password_hash, check_password_hash
from google import genai
from google.genai import types
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv
import markdown
import json
import datetime
import re
from flask import flash

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_secret_key_here')

client_ai = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

client = MongoClient(
    os.getenv('MONGO_URI'),
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=30000,
    connectTimeoutMS=30000,
    socketTimeoutMS=30000,
    retryWrites=True
)

db = client.mental_health_app

chat_history = [
    types.Content(role="user", parts=[types.Part(text="I need you to act as a supportive mental health assistant. You should provide empathetic, helpful responses but clearly state you are not a replacement for professional mental health care.")]),
    types.Content(role="model", parts=[types.Part(text="I'll be your supportive mental health assistant. I'm here to listen and provide thoughtful responses. Please remember I'm not a licensed mental health professional. How can I support you today?")])
]


# ── Helpers ────────────────────────────────────────────────────────────────

def is_quota_exhausted(error):
    error_str = str(error).lower()
    return any(keyword in error_str for keyword in [
        'quota', 'resource_exhausted', '429',
        'rate limit', 'exceeded', 'billing',
        'unavailable', 'high demand', '503',
        'overloaded', 'capacity', 'try again later'
    ])

def send_otp_sms(phone, otp):
    url = "https://www.fast2sms.com/dev/bulkV2"
    headers = {"authorization": os.getenv("FAST2SMS_API_KEY")}
    payload = {
        "route": "otp",
        "variables_values": str(otp),
        "numbers": phone,
    }
    response = http_requests.post(url, headers=headers, data=payload)
    return response.json()


def is_crisis_message(message):
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in CRISIS_KEYWORDS)

def update_user_stats(user_id, stat_type, value=1):
    try:
        db.users.update_one(
            {'_id': ObjectId(user_id)},
            {
                '$inc': {stat_type: value},
                '$set': {'last_login': datetime.datetime.now()}
            }
        )
    except Exception as e:
        print(f"Error updating user stats: {e}")


# ── Auth ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if db.users.find_one({'email': email}):
            return "User already exists!"

        hashed_password = generate_password_hash(password)
        db.users.insert_one({
            'email': email,
            'password': hashed_password,
            'is_admin': False
        })
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'user')

        if role == 'admin':
            user = db.users.find_one({'email': email, 'is_admin': True})
            if user and check_password_hash(user['password'], password):
                session['user_id'] = str(user['_id'])
                session['is_admin'] = True
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid admin credentials!', 'danger')
                return redirect(url_for('login'))
        else:
            user = db.users.find_one({'email': email})
            if user and check_password_hash(user['password'], password):
                session['user_id'] = str(user['_id'])
                session['is_admin'] = user.get('is_admin', False)
                if session.get('is_admin'):
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('index'))
            else:
                flash('Invalid email or password!', 'danger')
                return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ── OTP Password Recovery ──────────────────────────────────────────────────

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()

        # Remove +91 or spaces if user types them
        phone = re.sub(r'[\s\-\+]', '', phone)
        if phone.startswith('91') and len(phone) == 12:
            phone = phone[2:]

        if not re.match(r'^\d{10}$', phone):
            flash('Please enter a valid 10-digit Indian mobile number.', 'danger')
            return render_template('forgot_password.html')

        user = db.users.find_one({'phone': phone})
        if not user:
            flash('No account found with that phone number.', 'danger')
            return render_template('forgot_password.html')

        otp = str(random.randint(100000, 999999))
        expiry = datetime.datetime.now() + datetime.timedelta(minutes=10)

        db.users.update_one(
            {'_id': user['_id']},
            {'$set': {'reset_otp': otp, 'reset_otp_expiry': expiry}}
        )

        try:
            result = send_otp_sms(phone, otp)
            if result.get('return'):
                session['reset_phone'] = phone
                flash('OTP sent to your registered mobile number.', 'success')
                return redirect(url_for('verify_otp'))
            else:
                flash(f"SMS failed: {result.get('message', 'Unknown error')}", 'danger')
        except Exception as e:
            print(f"SMS error: {e}")
            flash('Could not send OTP. Please try again.', 'danger')

    return render_template('forgot_password.html')


@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    phone = session.get('reset_phone')
    if not phone:
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()

        user = db.users.find_one({'phone': phone})
        if not user:
            flash('Session expired. Please try again.', 'danger')
            return redirect(url_for('forgot_password'))

        stored_otp = user.get('reset_otp')
        expiry = user.get('reset_otp_expiry')

        if not stored_otp or not expiry:
            flash('No OTP found. Please request a new one.', 'danger')
            return redirect(url_for('forgot_password'))

        if datetime.datetime.now() > expiry:
            flash('OTP has expired. Please request a new one.', 'danger')
            return redirect(url_for('forgot_password'))

        if entered_otp != stored_otp:
            flash('Incorrect OTP. Please try again.', 'danger')
            return render_template('verify_otp.html')

        # OTP valid — allow password reset
        session['otp_verified_phone'] = phone
        session.pop('reset_phone', None)

        # Clear OTP from DB
        db.users.update_one(
            {'phone': phone},
            {'$unset': {'reset_otp': '', 'reset_otp_expiry': ''}}
        )

        return redirect(url_for('reset_password_otp'))

    return render_template('verify_otp.html')


@app.route('/reset_password_otp', methods=['GET', 'POST'])
def reset_password_otp():
    phone = session.get('otp_verified_phone')
    if not phone:
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if len(new_password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('reset_password_otp.html')

        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password_otp.html')

        hashed = generate_password_hash(new_password)
        db.users.update_one({'phone': phone}, {'$set': {'password': hashed}})

        session.pop('otp_verified_phone', None)
        flash('Password reset successfully. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password_otp.html')

# ── Profile ────────────────────────────────────────────────────────────────

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        user = db.users.find_one({'_id': ObjectId(session['user_id'])})
        if not user:
            session.clear()
            return redirect(url_for('login'))

        user_dict = {
            'id': user['_id'],
            'username': user['email'],
            'email': user['email'],
            'first_name': user.get('first_name', ''),
            'last_name': user.get('last_name', ''),
            'phone': user.get('phone', ''),
            'created_at': user.get('created_at'),
            'assessments_completed': user.get('assessments_completed', 0),
            'chat_sessions': user.get('chat_sessions', 0),
            'meditation_minutes': user.get('meditation_minutes', 0),
            'last_login': user.get('last_login'),
        }

        assessments = list(
            db.assessments.find({'user_id': session['user_id']})
            .sort('date', -1)
            .limit(10)
        )

        for a in assessments:
            pct = a.get('percent', 0)
            if pct <= 20:
                a['severity'] = 'Minimal'
                a['severity_color'] = 'success'
            elif pct <= 40:
                a['severity'] = 'Mild'
                a['severity_color'] = 'info'
            elif pct <= 60:
                a['severity'] = 'Moderate'
                a['severity_color'] = 'warning'
            elif pct <= 80:
                a['severity'] = 'Moderately Severe'
                a['severity_color'] = 'orange'
            else:
                a['severity'] = 'Severe'
                a['severity_color'] = 'danger'

        return render_template('profile.html', user=user_dict, assessments=assessments)

    except Exception as e:
        print(f"Error fetching user profile: {e}")
        return redirect(url_for('login'))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    first_name = request.form.get('first_name', '')
    last_name = request.form.get('last_name', '')
    email = request.form.get('email', '')
    phone = request.form.get('phone', '')

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        flash('Please enter a valid email address.', 'danger')
        return redirect(url_for('profile'))

    try:
        existing_user = db.users.find_one({'email': email, '_id': {'$ne': ObjectId(session['user_id'])}})
        if existing_user:
            flash('Email address is already in use by another account.', 'danger')
            return redirect(url_for('profile'))

        db.users.update_one({'_id': ObjectId(session['user_id'])}, {
            '$set': {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone': phone,
                'last_login': datetime.datetime.now()
            }
        })

        flash('Your profile has been updated successfully.', 'success')
        return redirect(url_for('profile'))

    except Exception as e:
        print(f"Error updating profile: {e}")
        flash('An error occurred while updating your profile. Please try again.', 'danger')
        return redirect(url_for('profile'))

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'You must be logged in to change your password.'}), 401

    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not all([current_password, new_password, confirm_password]):
        return jsonify({'status': 'error', 'message': 'All fields are required.'}), 400

    if new_password != confirm_password:
        return jsonify({'status': 'error', 'message': 'New passwords do not match.'}), 400

    if len(new_password) < 8:
        return jsonify({'status': 'error', 'message': 'Password must be at least 8 characters long.'}), 400

    try:
        user = db.users.find_one({'_id': ObjectId(session['user_id'])})
        if not check_password_hash(user['password'], current_password):
            return jsonify({'status': 'error', 'message': 'Current password is incorrect.'}), 400

        hashed_password = generate_password_hash(new_password)
        db.users.update_one({'_id': ObjectId(session['user_id'])}, {'$set': {'password': hashed_password}})
        return jsonify({'status': 'success', 'message': 'Password updated successfully.'}), 200

    except Exception as e:
        print(f"Error changing password: {e}")
        return jsonify({'status': 'error', 'message': 'An error occurred. Please try again.'}), 500


# ── Static pages ───────────────────────────────────────────────────────────

@app.route('/articles')
def articles():
    return render_template('articles.html', articles=[])

@app.route('/meditation')
def meditation():
    return render_template('meditation.html', meditation=[])

@app.route('/other_quizzes')
def other_quizzes():
    return render_template('other_quizzes.html', quizzes=[])

@app.route('/contact')
def contact():
    counselors_list = list(db.counselors.find())
    return render_template('contact.html', counselors=counselors_list)

@app.route('/contact_submit', methods=['POST'])
def contact_submit():
    contact_request = {
        'name': request.form.get('name'),
        'email': request.form.get('email'),
        'phone': request.form.get('phone', ''),
        'concern': request.form.get('concern'),
        'message': request.form.get('message'),
        'date_submitted': datetime.datetime.now(),
        'status': 'new'
    }
    db.contact_requests.insert_one(contact_request)
    return render_template('contact_success.html')

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    latest_assessment = db.assessments.find_one(
        {'user_id': session['user_id']},
        sort=[('date', -1)]
    )
    return render_template('chatbot.html', assessment=latest_assessment)

# ── Chatbot ────────────────────────────────────────────────────────────────

@app.route('/send_message', methods=['POST'])
def send_message():
    user_message = request.form.get('message')
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    # ── Crisis check via AI ────────────────────────────────────────────
    try:
        crisis_check = client_ai.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"""You are a crisis detection system. Analyze this message and reply with ONLY "YES" or "NO".
Reply YES if the message suggests: suicidal thoughts, self-harm, severe hopelessness, abuse, or any immediate danger to life.
Reply NO for everything else, including general sadness, stress, or venting.

Message: "{user_message}"

Reply with only YES or NO:"""
        )
        is_crisis = crisis_check.text.strip().upper().startswith('YES')
        
    except Exception:
        is_crisis = False

    if is_crisis:
        try:
            tone_response = client_ai.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"""You are a compassionate crisis support assistant. 
A user sent this message: "{user_message}"

Write TWO short paragraphs only:
1. An empathetic opening (2-3 sentences) that directly acknowledges what they said and validates their pain. Mirror the intensity of their emotions — if they seem mildly distressed be gentle, if they seem severely distressed be more urgent and warm.
2. A closing sentence (1-2 sentences) that gently encourages them to reach out to a professional, without being preachy.

Do not include any helpline numbers. Do not use markdown headers. Just plain warm human text."""
            )
            dynamic_text = tone_response.text.strip().split('\n\n')
            opening = dynamic_text[0] if len(dynamic_text) > 0 else "I hear you, and I'm really glad you reached out right now."
            closing = dynamic_text[1] if len(dynamic_text) > 1 else "You deserve real human support right now — please reach out."
        except Exception:
            opening = "I hear you, and I'm really glad you reached out right now. What you're going through sounds incredibly painful, and it takes courage to put those feelings into words."
            closing = "You deserve real human support right now — please reach out to one of these resources."

        crisis_response = f"""
{opening}

Please don't face this alone. Reach out to someone who can help right now:

🆘 **Emergency Services:** Call 112 *(if you are in immediate danger)*

📞 **iCall (India):** 9152987821 *(Mon–Sat, 8am–10pm — trained counselors who will listen without judgment)*

💬 **Vandrevala Foundation:** 1860-2662-345 *(24/7, completely free — you can call anytime, day or night)*

📱 **AASRA:** 91-22-27546669 *(24/7 — you don't have to explain everything, just call)*

🌐 **Chat online at:** icallhelpline.org *(if talking feels too hard right now)*

{closing}

---
💬 **Prefer to talk to one of our professionals?** [Click here to connect with a MindWell counselor](/contact)
        """
        return jsonify({
            'response': markdown.markdown(crisis_response),
            'is_crisis': True
        })
    # ──────────────────────────────────────────────────────────────────

    try:
        # Build personalized context from DB
        assessment_context = ""
        if 'user_id' in session:
            latest = db.assessments.find_one(
                {'user_id': session['user_id']},
                sort=[('date', -1)]
            )
            if latest:
                answers_summary = "\n".join([
                    f"- {a['question']}: {a['answer_label']}"
                    for a in latest.get('answers', [])
                ])
                assessment_context = f"""
The user has previously completed a mental health assessment with the following results:
- Mood described: {latest.get('mood', 'N/A')}
- Score: {latest.get('percent', 0)}% ({latest.get('total_score', 0)}/{latest.get('max_score', 0)})
- AI Analysis: {latest.get('ai_analysis', 'N/A')}
- Their answers:
{answers_summary}

Use this context to provide personalized, relevant support. 
Reference their specific concerns when appropriate but don't repeat 
the assessment back robotically.
"""

        system_prompt = f"""You are a supportive mental health assistant for MindWell, serving users in India.
You provide empathetic, helpful responses but clearly state you are 
not a replacement for professional mental health care.
If a user expresses distress or crisis, always refer them to Indian helplines:
iCall: 9152987821, Vandrevala Foundation: 1860-2662-345, AASRA: 91-22-27546669, Emergency: 112.
Never mention US helplines like 988.
{assessment_context}"""

        history = session.get('chat_messages', [])

        contents = [
            types.Content(role="user", parts=[types.Part(text=system_prompt)]),
            types.Content(role="model", parts=[types.Part(text="Understood. I'll provide personalized support based on the user's history.")]),
        ]

        for msg in history:
            contents.append(
                types.Content(role=msg['role'], parts=[types.Part(text=msg['text'])])
            )

        contents.append(
            types.Content(role="user", parts=[types.Part(text=user_message)])
        )

        response = client_ai.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.9,
                max_output_tokens=1000,
            )
        )

        reply = response.text

        # ── Detect mood shift ──────────────────────────────────────────
        try:
            mood_check = client_ai.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"""You are an emotional state analyzer. Analyze this message and classify the emotional shift.
Reply with ONLY one of these exact labels:

NEG_TO_POS - user was struggling but is now feeling better, relieved, grateful, or hopeful
POS_TO_NEG - user was okay but is now feeling worse, more anxious, sad, or distressed
NEG_TO_MORE_NEG - user was already struggling and things are getting even worse
POS_TO_MORE_POS - user is feeling good and things are continuing to improve
CRISIS_RESOLVED - user was in crisis but now feels safer or calmer
NEUTRAL - no clear emotional shift detected

Message: "{user_message}"

Reply with only the label:"""
            )
            mood_shift = mood_check.text.strip().upper()
        except Exception:
            mood_shift = "NEUTRAL"

        if mood_shift != "NEUTRAL":
            db.mood_shifts.insert_one({
                'user_id': session.get('user_id'),
                'message': user_message,
                'shift': mood_shift,
                'timestamp': datetime.datetime.now()
            })

            if mood_shift == "CRISIS_RESOLVED":
                db.users.update_one(
                    {'_id': ObjectId(session['user_id'])},
                    {'$inc': {'crisis_resolved_count': 1}}
                )

            if mood_shift in ["NEG_TO_MORE_NEG", "POS_TO_NEG"]:
                db.flags.insert_one({
                    'user_id': session.get('user_id'),
                    'reason': mood_shift,
                    'message': user_message,
                    'timestamp': datetime.datetime.now(),
                    'reviewed': False
                })
        # ──────────────────────────────────────────────────────────────

        history.append({'role': 'user', 'text': user_message})
        history.append({'role': 'model', 'text': reply})
        session['chat_messages'] = history[-20:]

        if 'user_id' in session:
            update_user_stats(session['user_id'], 'chat_sessions')

        return jsonify({'response': markdown.markdown(reply)})

    except Exception as e:
        print(f"Error in chat: {e}")
        if is_quota_exhausted(e):
            return jsonify({
                'quota_exhausted': True,
                'error': 'AI service is temporarily unavailable.'
            }), 503
        return jsonify({'error': str(e)}), 500
# ── Assessment ─────────────────────────────────────────────────────────────

@app.route('/assessment')
def assessment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('assessment.html')

@app.route('/generate_assessment', methods=['POST'])
def generate_assessment():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    mood = request.form.get('mood', '').strip()
    if not mood:
        return redirect(url_for('assessment'))

    try:
        prompt = f"""
You are a clinical mental health screening assistant.
A user has described how they are feeling as: "{mood}"

Generate exactly 10 diagnostic mental health questions tailored specifically to what they described.
The questions should help assess their emotional state, severity of symptoms, and any risk factors.
Each question must have 4 options ranging from least to most severe.

Return ONLY a valid JSON array with no extra text, no markdown, no code fences.
Format:
[
  {{
    "question": "Question text here",
    "options": [
      {{"label": "Not at all", "value": 0}},
      {{"label": "Slightly", "value": 1}},
      {{"label": "Moderately", "value": 2}},
      {{"label": "Severely", "value": 3}}
    ]
  }}
]
"""
        response = client_ai.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        questions_text = response.text.strip()
        if questions_text.startswith('```'):
            questions_text = re.sub(r'^```[a-z]*\n?', '', questions_text)
            questions_text = re.sub(r'```$', '', questions_text).strip()

        questions = json.loads(questions_text)
        session['assessment_questions'] = questions
        session['assessment_mood'] = mood

        return render_template('assessment.html', questions=questions, mood=mood)

    except Exception as e:
        print(f"Error generating assessment: {e}")
        if is_quota_exhausted(e):
            return render_template('error.html',
                                   title="Service Unavailable",
                                   message="quota_exhausted")
        return render_template('error.html',
                               title="Assessment Error",
                               message="Could not generate questions. Please try again.")
    
@app.route('/submit_assessment', methods=['POST'])
def submit_assessment():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        questions = session.get('assessment_questions', [])
        mood = session.get('assessment_mood', '')

        answers = []
        total_score = 0
        for i, q in enumerate(questions):
            val = int(request.form.get(f'question_{i}', 0))
            total_score += val
            answers.append({
                'question': q['question'],
                'answer_value': val,
                'answer_label': next((o['label'] for o in q['options'] if o['value'] == val), 'Unknown')
            })

        max_score = len(questions) * 3
        percent = round((total_score / max_score) * 100) if max_score > 0 else 0

        answers_summary = "\n".join([
            f"Q: {a['question']}\nA: {a['answer_label']} (score: {a['answer_value']})"
            for a in answers
        ])

        analysis_prompt = f"""
You are a clinical mental health assistant. A user described their mood as: "{mood}"

They answered the following diagnostic questions:

{answers_summary}

Total score: {total_score} out of {max_score} ({percent}%)

Based on their responses, provide:
1. A clear diagnosis summary of their mental health condition
2. The severity level (Minimal / Mild / Moderate / Severe)
3. Key observations from their answers
4. Specific personalized recommendations
5. Whether they should seek professional help (yes/no and why)

Be empathetic, clear, and clinically informed. Do not use markdown headers or bullet points.
Write in flowing paragraphs as if speaking directly to the user.
"""

        analysis_response = client_ai.models.generate_content(
            model="gemini-2.5-flash",
            contents=analysis_prompt
        )

        analysis = analysis_response.text.strip()
        analysis_html = markdown.markdown(analysis)

        db.assessments.insert_one({
            'user_id': session['user_id'],
            'mood': mood,
            'questions': questions,
            'answers': answers,
            'total_score': total_score,
            'max_score': max_score,
            'percent': percent,
            'ai_analysis': analysis,
            'date': datetime.datetime.now()
        })
        update_user_stats(session['user_id'], 'assessments_completed')

        session['assessment_results'] = {
            'mood': mood,
            'answers': answers,
            'total_score': total_score,
            'max_score': max_score,
            'percent': percent,
            'analysis_html': analysis_html,
        }

        return redirect(url_for('assessment_results'))

    except Exception as e:
        print(f"Assessment submission error: {e}")
        if is_quota_exhausted(e):
            return render_template('error.html',
                                   title="Service Unavailable",
                                   message="quota_exhausted")
        return render_template('error.html',
                               title="Assessment Error",
                               message="Something went wrong processing your assessment. Please try again.")

@app.route('/assessment_results')
def assessment_results():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    data = session.get('assessment_results')
    if not data:
        return redirect(url_for('assessment'))

    return render_template('assessment_results.html', data=data)


# ── Custom quiz (other_quizzes page) ───────────────────────────────────────

@app.route('/generate_custom_quiz', methods=['POST'])
def generate_custom_quiz():
    topic = request.form.get('topic')
    num_questions = int(request.form.get('num_questions', 10))
    difficulty = request.form.get('difficulty', 'intermediate')
    custom_prompt = request.form.get('custom_prompt', '')

    try:
        prompt = f"""
        Create a mental health quiz about {topic} with {num_questions} questions at {difficulty} level.
        {custom_prompt if custom_prompt else ''}

        Format each question as a JSON object with the following structure:
        {{
            "question": "The question text",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_answer": "The correct option text"
        }}

        Return a JSON array of these question objects.
        """

        response = client_ai.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        if response and hasattr(response, 'text'):
            questions_text = response.text.strip()
            if questions_text.startswith('```json'):
                questions_text = questions_text.replace('```json', '', 1)
            if questions_text.endswith('```'):
                questions_text = questions_text[:-3]

            questions = json.loads(questions_text.strip())

            if 'user_id' in session:
                db.custom_quizzes.insert_one({
                    'user_id': session['user_id'],
                    'topic': topic,
                    'difficulty': difficulty,
                    'questions': questions,
                    'created_at': datetime.datetime.now()
                })

            return render_template('custom_quiz.html',
                                   questions=questions,
                                   topic=topic,
                                   difficulty=difficulty)
        else:
            return render_template('error.html',
                                   message="There was an error generating your quiz. Please try again.")

    except Exception as e:
        print(f"Error generating custom quiz: {e}")
        if is_quota_exhausted(e):
            return render_template('error.html',
                                   title="Service Unavailable",
                                   message="quota_exhausted")
        return render_template('error.html',
                               message="There was an error generating your quiz. Please try again.")

# ── Meditation tracking ────────────────────────────────────────────────────

@app.route('/track_meditation', methods=['POST'])
def track_meditation():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'You must be logged in to track meditation.'}), 401

    try:
        minutes = int(request.json.get('minutes', 0))
        if minutes <= 0:
            return jsonify({'status': 'error', 'message': 'Invalid meditation time.'}), 400

        update_user_stats(session['user_id'], 'meditation_minutes', minutes)
        return jsonify({'status': 'success', 'message': f'Successfully logged {minutes} minutes of meditation.'}), 200

    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid meditation time format.'}), 400
    except Exception as e:
        print(f"Error tracking meditation: {e}")
        return jsonify({'status': 'error', 'message': 'An error occurred. Please try again.'}), 500


# ── Admin ──────────────────────────────────────────────────────────────────

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = db.users.find_one({'email': email, 'is_admin': True})
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return "Invalid credentials or not an admin!"
    return render_template('admin_login.html')

# ── Add this route to app.py (inside the Admin section) ───────────────────

@app.route('/admin/assessments')
def admin_assessments():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    try:
        assessments = list(db.assessments.find().sort('date', -1))
        
        for a in assessments:
            user = db.users.find_one({'_id': ObjectId(a['user_id'])})
            a['user'] = user

            pct = a.get('percent', 0)
            if pct <= 20:
                a['severity'] = 'Minimal'
                a['severity_color'] = 'success'
            elif pct <= 40:
                a['severity'] = 'Mild'
                a['severity_color'] = 'info'
            elif pct <= 60:
                a['severity'] = 'Moderate'
                a['severity_color'] = 'warning'
            elif pct <= 80:
                a['severity'] = 'Moderately Severe'
                a['severity_color'] = 'orange'
            else:
                a['severity'] = 'Severe'
                a['severity_color'] = 'danger'

        print(f"DEBUG assessments count: {len(assessments)}")
        return render_template('admin_assessments.html', assessments=assessments)

    except Exception as e:
        import traceback
        print(f"FULL ERROR: {traceback.format_exc()}")
        return f"<pre>ERROR: {traceback.format_exc()}</pre>", 500


@app.route('/admin/assessment/<assessment_id>')
def admin_view_assessment(assessment_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    try:
        assessment = db.assessments.find_one({'_id': ObjectId(assessment_id)})
        if not assessment:
            return render_template('error.html', message="Assessment not found")

        user = db.users.find_one({'_id': ObjectId(assessment.get('user_id'))})
        assessment['user_email'] = user.get('email', 'N/A') if user else 'N/A'

        pct = assessment.get('percent', 0)
        if pct <= 20:
            assessment['severity'] = 'Minimal'
            assessment['severity_color'] = 'success'
        elif pct <= 40:
            assessment['severity'] = 'Mild'
            assessment['severity_color'] = 'info'
        elif pct <= 60:
            assessment['severity'] = 'Moderate'
            assessment['severity_color'] = 'warning'
        elif pct <= 80:
            assessment['severity'] = 'Moderately Severe'
            assessment['severity_color'] = 'orange'
        else:
            assessment['severity'] = 'Severe'
            assessment['severity_color'] = 'danger'

        return render_template('admin_view_assessment.html', assessment=assessment)

    except Exception as e:
        print(f"Error viewing assessment: {e}")
        return render_template('error.html', message="Error loading assessment details")
    
@app.route('/admin/user_assessments/<user_id>')
def admin_user_assessments(user_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    try:
        assessments = list(db.assessments.find({'user_id': user_id}).sort('date', -1))
        user = db.users.find_one({'_id': ObjectId(user_id)})

        for a in assessments:
            a['user'] = user
            pct = a.get('percent', 0)
            if pct <= 20:
                a['severity'] = 'Minimal'
                a['severity_color'] = 'success'
            elif pct <= 40:
                a['severity'] = 'Mild'
                a['severity_color'] = 'info'
            elif pct <= 60:
                a['severity'] = 'Moderate'
                a['severity_color'] = 'warning'
            elif pct <= 80:
                a['severity'] = 'Moderately Severe'
                a['severity_color'] = 'orange'
            else:
                a['severity'] = 'Severe'
                a['severity_color'] = 'danger'

        return render_template('admin_assessments.html', assessments=assessments, user=user)

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return render_template('error.html', message="Error loading user assessments")

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    try:
        total_users = db.users.count_documents({})
        total_assessments = db.assessments.count_documents({})
        total_contacts = db.contact_requests.count_documents({})

        agg = list(db.users.aggregate([
            {'$group': {'_id': None, 'total': {'$sum': '$meditation_minutes'}}}
        ]))
        total_meditation = agg[0]['total'] if agg else 0

        users = list(db.users.find({'is_admin': False}))
        contacts = list(db.contact_requests.find().sort('date_submitted', -1))
        admins = list(db.users.find({'is_admin': True}))

        return render_template('admin_dashboard.html',
                               total_users=total_users,
                               total_assessments=total_assessments,
                               total_contacts=total_contacts,
                               total_meditation=total_meditation,
                               users=users,
                               contacts=contacts,
                               admins=admins)

    except Exception as e:
        print(f"Error loading admin dashboard: {e}")
        return render_template('error.html', message="Error loading admin dashboard")

@app.route('/admin/add_admin', methods=['POST'])
def add_admin():
    if not session.get('is_admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')

        if db.users.find_one({'email': email}):
            return jsonify({'success': False, 'message': 'Email already exists'})

        hashed_password = generate_password_hash(password)
        db.users.insert_one({
            'email': email,
            'password': hashed_password,
            'first_name': first_name,
            'last_name': last_name,
            'is_admin': True,
            'created_at': datetime.datetime.now()
        })
        return jsonify({'success': True})

    except Exception as e:
        print(f"Error adding admin: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/delete_admin/<admin_id>', methods=['POST'])
def delete_admin(admin_id):
    if not session.get('is_admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        if db.users.count_documents({'is_admin': True}) <= 1:
            return jsonify({'success': False, 'message': 'Cannot delete the last admin'})

        result = db.users.delete_one({'_id': ObjectId(admin_id), 'is_admin': True})
        return jsonify({'success': result.deleted_count > 0,
                        'message': '' if result.deleted_count > 0 else 'Admin not found'})

    except Exception as e:
        print(f"Error deleting admin: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/delete_user/<user_id>', methods=['POST'])
def delete_user(user_id):
    if not session.get('is_admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        result = db.users.delete_one({'_id': ObjectId(user_id), 'is_admin': False})
        if result.deleted_count > 0:
            # Also clean up their assessments
            db.assessments.delete_many({'user_id': user_id})
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'User not found'})

    except Exception as e:
        print(f"Error deleting user: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/update_contact_status/<contact_id>', methods=['POST'])
def update_contact_status(contact_id):
    if not session.get('is_admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        new_status = request.json.get('status')
        if new_status not in ['new', 'in_progress', 'resolved']:
            return jsonify({'success': False, 'message': 'Invalid status'})

        result = db.contact_requests.update_one(
            {'_id': ObjectId(contact_id)},
            {'$set': {'status': new_status}}
        )
        return jsonify({'success': result.modified_count > 0,
                        'message': '' if result.modified_count > 0 else 'Contact request not found'})

    except Exception as e:
        print(f"Error updating contact status: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/view_user/<user_id>')
def admin_view_user(user_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    try:
        user = db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            return render_template('error.html', message="User not found")
        return render_template('admin_view_user.html', user=user)
    except Exception as e:
        print(f"Error viewing user: {e}")
        return render_template('error.html', message="Error loading user details")

@app.route('/admin/view_contact/<contact_id>')
def admin_view_contact(contact_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    try:
        contact = db.contact_requests.find_one({'_id': ObjectId(contact_id)})
        if not contact:
            return render_template('error.html', message="Contact request not found")
        return render_template('admin_view_contact.html', contact=contact)
    except Exception as e:
        print(f"Error viewing contact request: {e}")
        return render_template('error.html', message="Error loading contact request details")


# ── Misc ───────────────────────────────────────────────────────────────────

@app.route('/test_db')
def test_db():
    try:
        client.admin.command('ismaster')
        return "Database connection successful!"
    except Exception as e:
        return f"Database connection failed: {e}"

@app.context_processor
def inject_now():
    return {'now': datetime.datetime.now()}

def init_db():
    try:
        for name in ["users", "assessments", "custom_quizzes", "contact_requests"]:
            if name not in db.list_collection_names():
                db.create_collection(name)
                print(f"Created {name} collection")
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)