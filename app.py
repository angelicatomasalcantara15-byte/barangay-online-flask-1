from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import mysql.connector
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import os
import time
import datetime
import random
import glob

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'

# ===== DATABASE CONNECTION =====
def get_db():
    return mysql.connector.connect(
        host='127.0.0.1',
        port=3307,
        user='root',
        password='bsit2026@123',
        database='barangay_online_services'
    )

# ===== HOME/INDEX ROUTE =====
@app.route('/')
def index():
    return redirect(url_for('login'))

# ===== LOGIN ROUTE (MAY LOCKOUT) =====
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('login_attempts', 0) >= 3:
        lockout_time = session.get('lockout_time', 0)
        current_time = time.time()
        if current_time < lockout_time:
            remaining = int(lockout_time - current_time)
            lockout_msg = f"Too many failed attempts. Please wait {remaining} seconds before trying again."
            return render_template('login.html', login_error=True, lockout_message=lockout_msg)
        else:
            session['login_attempts'] = 0
            session['lockout_time'] = 0

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'resident')
        
        if not email or not password:
            flash('Please fill in all fields.', 'warning')
            return render_template('login.html')
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            if not check_password_hash(user['password'], password):
                session['login_attempts'] = session.get('login_attempts', 0) + 1
                if session['login_attempts'] >= 3:
                    session['lockout_time'] = time.time() + 30
                    lockout_msg = "Too many failed attempts. Please wait 30 seconds before trying again."
                    return render_template('login.html', login_error=True, lockout_message=lockout_msg)
                else:
                    return render_template('login.html', login_error=True)
            
            session['login_attempts'] = 0
            session['lockout_time'] = 0
            
            if role == 'admin' and user['role'] not in ['admin', 'head_admin']:
                flash('You are not authorized as admin.', 'danger')
                return render_template('login.html')
            
            session['user_id'] = user['id']
            session['fullname'] = f"{user['first_name']} {user['last_name']}"
            session['email'] = user['email']
            session['role'] = user['role']
            
            if user['role'] == 'head_admin':
                return redirect(url_for('head_admin_dashboard'))
            elif user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            session['login_attempts'] = session.get('login_attempts', 0) + 1
            if session['login_attempts'] >= 3:
                session['lockout_time'] = time.time() + 30
                lockout_msg = "Too many failed attempts. Please wait 30 seconds before trying again."
                return render_template('login.html', login_error=True, lockout_message=lockout_msg)
            else:
                return render_template('login.html', login_error=True)
    
    return render_template('login.html')

# ===== REGISTER ROUTE =====
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        contact_number = request.form.get('contact_number', '').strip()
        address = request.form.get('address', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not first_name or not last_name or not email or not password:
            flash('Please fill in all required fields.', 'danger')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('register.html')
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            flash('Email address already registered. Please login.', 'danger')
            return render_template('register.html')
        
        hashed_password = generate_password_hash(password)
        
        cursor.execute("""
            INSERT INTO users (first_name, last_name, email, password, contact_number, address, role, is_verified)
            VALUES (%s, %s, %s, %s, %s, %s, 'resident', TRUE)
        """, (first_name, last_name, email, hashed_password, contact_number, address))
        conn.commit()
        conn.close()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# ============================================================
# ===== RESIDENT ROUTES =====
# ============================================================

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) as total FROM document_requests WHERE user_id = %s", (session['user_id'],))
    total_docs = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as pending FROM document_requests WHERE user_id = %s AND status = 'pending'", (session['user_id'],))
    pending_docs = cursor.fetchone()['pending']
    
    cursor.execute("SELECT COUNT(*) as approved FROM document_requests WHERE user_id = %s AND status = 'approved'", (session['user_id'],))
    approved_docs = cursor.fetchone()['approved']
    
    cursor.execute("SELECT COUNT(*) as rejected FROM document_requests WHERE user_id = %s AND status = 'rejected'", (session['user_id'],))
    rejected_docs = cursor.fetchone()['rejected']
    
    cursor.execute("SELECT COUNT(*) as total FROM event_permits WHERE user_id = %s", (session['user_id'],))
    total_events = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as pending FROM event_permits WHERE user_id = %s AND status = 'pending'", (session['user_id'],))
    pending_events = cursor.fetchone()['pending']
    
    cursor.execute("SELECT COUNT(*) as approved FROM event_permits WHERE user_id = %s AND status = 'approved'", (session['user_id'],))
    approved_events = cursor.fetchone()['approved']
    
    cursor.execute("SELECT COUNT(*) as rejected FROM event_permits WHERE user_id = %s AND status = 'rejected'", (session['user_id'],))
    rejected_events = cursor.fetchone()['rejected']
    
    cursor.execute("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 5")
    announcements = cursor.fetchall()
    
    cursor.execute("SELECT * FROM document_requests WHERE user_id = %s ORDER BY created_at DESC LIMIT 5", (session['user_id'],))
    recent_docs = cursor.fetchall()
    
    cursor.execute("""
        SELECT id, event_name, event_date, start_time, end_time, venue, 
               status, reference_number, queuing_number, created_at
        FROM event_permits 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT 5
    """, (session['user_id'],))
    recent_events = cursor.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                         user=user,
                         total_docs=total_docs,
                         pending_docs=pending_docs,
                         approved_docs=approved_docs,
                         rejected_docs=rejected_docs,
                         total_events=total_events,
                         pending_events=pending_events,
                         approved_events=approved_events,
                         rejected_events=rejected_events,
                         announcements=announcements,
                         recent_docs=recent_docs,
                         recent_events=recent_events)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    return render_template('profile.html', user=user)

@app.route('/user-update-profile', methods=['POST'])
def user_update_profile():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    contact_number = request.form.get('contact_number', '').strip()
    address = request.form.get('address', '').strip()
    
    if not first_name or not last_name or not email:
        flash('Please fill in all required fields.', 'danger')
        return redirect(url_for('settings'))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET 
            first_name = %s, 
            last_name = %s, 
            email = %s, 
            contact_number = %s, 
            address = %s
        WHERE id = %s
    """, (first_name, last_name, email, contact_number, address, session['user_id']))
    conn.commit()
    conn.close()
    
    session['fullname'] = f"{first_name} {last_name}"
    session['email'] = email
    
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/user-change-password', methods=['POST'])
def user_change_password():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    if not current_password or not new_password or not confirm_password:
        flash('Please fill in all fields.', 'danger')
        return redirect(url_for('settings'))
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('settings'))
    
    if len(new_password) < 8:
        flash('New password must be at least 8 characters.', 'danger')
        return redirect(url_for('settings'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT password FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not check_password_hash(user['password'], current_password):
        conn.close()
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('settings'))
    
    hashed_password = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Password changed successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/events')
def events():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT e.*, u.first_name, u.last_name 
        FROM event_permits e
        JOIN users u ON e.user_id = u.id
        WHERE e.status = 'approved'
        ORDER BY e.event_date DESC
    """)
    events = cursor.fetchall()
    conn.close()
    
    return render_template('events_calendar.html', events=events)

# ===== ADD EVENTS API =====
@app.route('/api/events', methods=['GET'])
def api_get_events():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first.'}), 401
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT e.*, u.first_name, u.last_name 
        FROM event_permits e
        JOIN users u ON e.user_id = u.id
        WHERE e.status = 'approved'
        ORDER BY e.event_date DESC
    """)
    events = cursor.fetchall()
    conn.close()
    
    for event in events:
        if event.get('event_date'):
            if hasattr(event['event_date'], 'strftime'):
                event['event_date'] = event['event_date'].strftime('%Y-%m-%d')
        if event.get('created_at'):
            if hasattr(event['created_at'], 'strftime'):
                event['created_at'] = event['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        if event.get('start_time'):
            event['start_time'] = str(event['start_time'])
        if event.get('end_time'):
            event['end_time'] = str(event['end_time'])
    
    return jsonify({'success': True, 'events': events})

@app.route('/api/events', methods=['POST'])
def api_create_event():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first.'}), 401
    
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    event_name = data.get('event_name', '').strip()
    event_description = data.get('event_description', '').strip()
    purpose = data.get('purpose', '').strip()
    event_date = data.get('event_date', '').strip()
    start_time = data.get('start_time', '').strip()
    end_time = data.get('end_time', '').strip()
    estimated_attendees = data.get('estimated_attendees', 0)
    venue = data.get('venue', '').strip()
    
    if not event_name or not event_date or not start_time or not end_time or not venue:
        return jsonify({'error': 'Please fill in all required fields.'}), 400
    
    if start_time >= end_time:
        return jsonify({'error': 'End time must be after start time.'}), 400
    
    if start_time < '08:00' or start_time > '22:00':
        return jsonify({'error': 'Start time must be between 8:00 AM and 10:00 PM.'}), 400
    
    if end_time < '08:00' or end_time > '22:00':
        return jsonify({'error': 'End time must be between 8:00 AM and 10:00 PM.'}), 400
    
    try:
        selected_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
        today = datetime.date.today()
        diff_days = (selected_date - today).days
        
        if diff_days < 10:
            return jsonify({'error': 'Please apply at least 10 days before the event date.'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid date format.'}), 400
    
    ref_num = f"BP-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
    queue_num = f"Q-{random.randint(1, 999):03d}"
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO event_permits (
                user_id, event_name, event_description, purpose, event_date, 
                start_time, end_time, estimated_attendees, venue, 
                status, reference_number, queuing_number
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)
        """, (
            session['user_id'], event_name, event_description, purpose, event_date,
            start_time, end_time, estimated_attendees if estimated_attendees else 0,
            venue, ref_num, queue_num
        ))
        conn.commit()
        event_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type)
            VALUES (%s, %s, %s, 'permit_submitted')
        """, (
            session['user_id'], 'Permit Application Submitted',
            f'Your event permit "{event_name}" has been submitted for review. Reference: {ref_num} | Queue: {queue_num}'
        ))
        conn.commit()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Event permit submitted successfully',
            'event_id': event_id,
            'reference_number': ref_num,
            'queuing_number': queue_num
        }), 201
        
    except mysql.connector.Error as e:
        conn.close()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/events/<int:event_id>', methods=['GET'])
def api_get_event(event_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first.'}), 401
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT e.*, u.first_name, u.last_name, u.email 
        FROM event_permits e
        JOIN users u ON e.user_id = u.id
        WHERE e.id = %s
    """, (event_id,))
    event = cursor.fetchone()
    conn.close()
    
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    
    if event.get('event_date'):
        if hasattr(event['event_date'], 'strftime'):
            event['event_date'] = event['event_date'].strftime('%Y-%m-%d')
    if event.get('created_at'):
        if hasattr(event['created_at'], 'strftime'):
            event['created_at'] = event['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    if event.get('start_time'):
        event['start_time'] = str(event['start_time'])
    if event.get('end_time'):
        event['end_time'] = str(event['end_time'])
    
    return jsonify({'success': True, 'event': event})

@app.route('/api/events/<int:event_id>', methods=['PUT'])
def api_update_event(event_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first.'}), 401
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM event_permits WHERE id = %s AND user_id = %s", (event_id, session['user_id']))
    event = cursor.fetchone()
    
    if not event:
        conn.close()
        return jsonify({'error': 'Event not found or you do not have permission'}), 404
    
    if event['status'] != 'pending':
        conn.close()
        return jsonify({'error': 'Only pending events can be edited'}), 400
    
    data = request.get_json()
    
    event_name = data.get('event_name', event['event_name']).strip()
    event_description = data.get('event_description', event['event_description']).strip()
    purpose = data.get('purpose', event['purpose']).strip()
    event_date = data.get('event_date', str(event['event_date'])).strip()
    start_time = data.get('start_time', str(event['start_time'])).strip()
    end_time = data.get('end_time', str(event['end_time'])).strip()
    estimated_attendees = data.get('estimated_attendees', event['estimated_attendees'])
    venue = data.get('venue', event['venue']).strip()
    
    if not event_name or not event_date or not start_time or not end_time or not venue:
        conn.close()
        return jsonify({'error': 'Please fill in all required fields.'}), 400
    
    if start_time >= end_time:
        conn.close()
        return jsonify({'error': 'End time must be after start time.'}), 400
    
    cursor.execute("""
        UPDATE event_permits SET
            event_name = %s,
            event_description = %s,
            purpose = %s,
            event_date = %s,
            start_time = %s,
            end_time = %s,
            estimated_attendees = %s,
            venue = %s
        WHERE id = %s
    """, (event_name, event_description, purpose, event_date, start_time, end_time, estimated_attendees, venue, event_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Event updated successfully'})

@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def api_delete_event(event_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first.'}), 401
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM event_permits WHERE id = %s AND user_id = %s", (event_id, session['user_id']))
    event = cursor.fetchone()
    
    if not event:
        conn.close()
        return jsonify({'error': 'Event not found or you do not have permission'}), 404
    
    if event['status'] != 'pending':
        conn.close()
        return jsonify({'error': 'Only pending events can be deleted'}), 400
    
    cursor.execute("DELETE FROM event_permits WHERE id = %s", (event_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Event deleted successfully'})

@app.route('/my-requests')
def my_requests():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Document requests
    cursor.execute("""
        SELECT * FROM document_requests 
        WHERE user_id = %s 
        ORDER BY created_at DESC
    """, (session['user_id'],))
    document_requests = cursor.fetchall()
    
    # Event permits
    cursor.execute("""
        SELECT * FROM event_permits 
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (session['user_id'],))
    event_permits = cursor.fetchall()
    
    # Document stats
    cursor.execute("SELECT COUNT(*) as total FROM document_requests WHERE user_id = %s", (session['user_id'],))
    total_docs = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as pending FROM document_requests WHERE user_id = %s AND status = 'pending'", (session['user_id'],))
    pending_docs = cursor.fetchone()['pending']
    
    cursor.execute("SELECT COUNT(*) as approved FROM document_requests WHERE user_id = %s AND status = 'approved'", (session['user_id'],))
    approved_docs = cursor.fetchone()['approved']
    
    cursor.execute("SELECT COUNT(*) as rejected FROM document_requests WHERE user_id = %s AND status = 'rejected'", (session['user_id'],))
    rejected_docs = cursor.fetchone()['rejected']
    
    # Event permit stats
    cursor.execute("SELECT COUNT(*) as total FROM event_permits WHERE user_id = %s", (session['user_id'],))
    total_events = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as pending FROM event_permits WHERE user_id = %s AND status = 'pending'", (session['user_id'],))
    pending_events = cursor.fetchone()['pending']
    
    cursor.execute("SELECT COUNT(*) as approved FROM event_permits WHERE user_id = %s AND status = 'approved'", (session['user_id'],))
    approved_events = cursor.fetchone()['approved']
    
    cursor.execute("SELECT COUNT(*) as rejected FROM event_permits WHERE user_id = %s AND status = 'rejected'", (session['user_id'],))
    rejected_events = cursor.fetchone()['rejected']
    
    conn.close()
    
    return render_template('my_requests.html', 
                         document_requests=document_requests,
                         event_permits=event_permits,
                         total_docs=total_docs,
                         pending_docs=pending_docs,
                         approved_docs=approved_docs,
                         rejected_docs=rejected_docs,
                         total_events=total_events,
                         pending_events=pending_events,
                         approved_events=approved_events,
                         rejected_events=rejected_events)

@app.route('/my_request')
def my_request():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT * FROM document_requests 
        WHERE user_id = %s 
        ORDER BY created_at DESC
    """, (session['user_id'],))
    document_requests = cursor.fetchall()
    
    cursor.execute("""
        SELECT * FROM event_permits 
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (session['user_id'],))
    event_permits = cursor.fetchall()
    
    conn.close()
    
    return render_template('my_request.html', 
                         document_requests=document_requests,
                         event_permits=event_permits)

@app.route('/request-document', methods=['GET'])
def request_document():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    return render_template('request_document.html')

# ============================================================
# ===== SUBMIT DOCUMENT REQUEST - FINAL FIX =====
# ============================================================
@app.route('/submit-document-request', methods=['POST'])
def submit_document_request():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first.'}), 401
    
    try:
        data = request.form.to_dict()
        
        print("=" * 50)
        print("📝 DATA RECEIVED:")
        for key, value in data.items():
            print(f"  {key}: {value}")
        print("=" * 50)
        
        conn = get_db()
        cursor = conn.cursor()
        
        # 1. TIGNAN MUNA NATIN ANG ACTUAL COLUMNS NG TABLE
        cursor.execute("DESCRIBE document_requests")
        columns = cursor.fetchall()
        print("📋 ACTUAL COLUMNS OF document_requests:")
        col_names = []
        for col in columns:
            print(f"  {col[0]}")
            col_names.append(col[0])
        print("=" * 50)
        
        # 2. I-CHECK KUNG MAY MISSING COLUMNS
        required_columns = ['user_id', 'document_type', 'reference_number', 'status']
        missing_columns = [col for col in required_columns if col not in col_names]
        
        if missing_columns:
            error_msg = f"MISSING COLUMNS SA DATABASE: {', '.join(missing_columns)}. Idagdag mo muna ito sa MySQL!"
            print("❌ ERROR:", error_msg)
            conn.close()
            return jsonify({'error': error_msg}), 500
        
        # 3. Generate reference number at queue number
        ref_num = f"DOC-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        queue_num = f"Q-{random.randint(1, 999):03d}"
        
        # 4. I-INSERT LANG YUNG MGA MAY COLUMNS NA (para safe)
        insert_cols = ['user_id', 'document_type', 'reference_number', 'status']
        insert_vals = [session['user_id'], data.get('document_type', 'clearance'), ref_num, 'pending']
        
        if 'queuing_number' in col_names:
            insert_cols.append('queuing_number')
            insert_vals.append(queue_num)
        
        for key, value in data.items():
            if key in col_names and key not in insert_cols and key != 'type' and key != 'fileInput':
                insert_cols.append(key)
                insert_vals.append(value)
        
        placeholders = ', '.join(['%s'] * len(insert_cols))
        columns_str = ', '.join(insert_cols)
        
        sql = f"INSERT INTO document_requests ({columns_str}) VALUES ({placeholders})"
        print(f"🔧 SQL: {sql}")
        print(f"🔧 VALUES: {insert_vals}")
        print("=" * 50)
        
        cursor.execute(sql, tuple(insert_vals))
        conn.commit()
        
        cursor.execute("SELECT * FROM document_requests ORDER BY id DESC LIMIT 1")
        last_row = cursor.fetchone()
        print("✅ LAST ROW SA DATABASE:")
        print(last_row)
        print("=" * 50)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Document request submitted successfully',
            'reference_number': ref_num,
            'queuing_number': queue_num if 'queuing_number' in col_names else 'N/A'
        })
        
    except Exception as e:
        print("❌ ERROR:", str(e))
        print("=" * 50)
        try:
            conn.close()
        except:
            pass
        return jsonify({'error': str(e)}), 500

# ===== APPLY FOR PERMIT =====
@app.route('/apply-permit', methods=['GET'])
def apply_permit():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    return render_template('apply_permit.html')

@app.route('/apply-permit', methods=['POST'])
def apply_permit_post():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    
    event_name = request.form.get('event_name', '').strip()
    event_description = request.form.get('event_description', '').strip()
    purpose = request.form.get('purpose', '').strip()
    event_date = request.form.get('event_date', '').strip()
    start_time = request.form.get('start_time', '').strip()
    end_time = request.form.get('end_time', '').strip()
    estimated_attendees = request.form.get('estimated_attendees', '').strip()
    venue = request.form.get('venue', '').strip()
    
    if not event_name or not event_date or not start_time or not end_time or not venue:
        flash('Please fill in all required fields.', 'danger')
        return redirect(url_for('apply_permit'))
    
    if start_time >= end_time:
        flash('End time must be after start time.', 'danger')
        return redirect(url_for('apply_permit'))
    
    if start_time < '08:00' or start_time > '22:00':
        flash('Start time must be between 8:00 AM and 10:00 PM.', 'danger')
        return redirect(url_for('apply_permit'))
    
    if end_time < '08:00' or end_time > '22:00':
        flash('End time must be between 8:00 AM and 10:00 PM.', 'danger')
        return redirect(url_for('apply_permit'))
    
    try:
        selected_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
        today = datetime.date.today()
        diff_days = (selected_date - today).days
        
        if diff_days < 10:
            flash('Please apply at least 10 days before the event date.', 'danger')
            return redirect(url_for('apply_permit'))
    except ValueError:
        flash('Invalid date format.', 'danger')
        return redirect(url_for('apply_permit'))
    
    file_data = None
    if 'requirement' in request.files:
        file = request.files['requirement']
        if file and file.filename:
            file_data = file.filename
    
    ref_num = f"BP-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
    queue_num = f"Q-{random.randint(1, 999):03d}"
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO event_permits (
                user_id, event_name, event_description, purpose, event_date, 
                start_time, end_time, estimated_attendees, venue, 
                status, requirements_file, reference_number, queuing_number
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s)
        """, (
            session['user_id'], event_name, event_description, purpose, event_date,
            start_time, end_time, estimated_attendees if estimated_attendees else 0,
            venue, file_data, ref_num, queue_num
        ))
        conn.commit()
        permit_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type)
            VALUES (%s, %s, %s, 'permit_submitted')
        """, (
            session['user_id'], 'Permit Application Submitted',
            f'Your event permit "{event_name}" has been submitted for review. Reference: {ref_num} | Queue: {queue_num}'
        ))
        conn.commit()
        
        flash('Permit application submitted successfully!', 'success')
        return redirect(url_for('dashboard'))
        
    except mysql.connector.Error as e:
        flash(f'Database error: {str(e)}', 'danger')
        return redirect(url_for('apply_permit'))
    finally:
        conn.close()


# ============================================================
# ===== CREATE PERMIT VIA API (JSON) =====
# ============================================================
@app.route('/api/permits', methods=['POST'])
def api_create_permit():
    if 'user_id' not in session:
        return jsonify({'message': 'Please login first.'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Walang data na natanggap.'}), 400
        
        event_name = (data.get('event_name') or '').strip()
        event_description = (data.get('event_description') or '').strip()
        purpose = (data.get('purpose') or '').strip()
        event_date = (data.get('event_date') or '').strip()
        start_time = (data.get('start_time') or '').strip()[:5]
        end_time = (data.get('end_time') or '').strip()[:5]
        venue = (data.get('venue') or '').strip()
        attendees = data.get('estimated_attendees', 0)
        requirement_name = data.get('requirement')
        
        # Basic validation
        if not event_name:
            return jsonify({'message': 'Kailangan ang event name.'}), 400
        if not venue:
            return jsonify({'message': 'Kailangan ang venue.'}), 400
        if not event_date or not start_time or not end_time:
            return jsonify({'message': 'Kailangan ang date at time.'}), 400
        
        # Attendees validation
        try:
            attendees = int(attendees)
        except (ValueError, TypeError):
            return jsonify({'message': 'Invalid attendees value.'}), 400
        
        if attendees < 1 or attendees > 300:
            return jsonify({'message': 'Ang attendees ay dapat 1 hanggang 300 lamang.'}), 400
        
        # Time validation
        if start_time >= end_time:
            return jsonify({'message': 'End time dapat pagkatapos ng start time.'}), 400
        
        if start_time < '08:00' or start_time > '22:00':
            return jsonify({'message': 'Start time dapat 8:00 AM – 10:00 PM.'}), 400
        
        if end_time < '08:00' or end_time > '22:00':
            return jsonify({'message': 'End time dapat 8:00 AM – 10:00 PM.'}), 400
        
        # 10-day rule
        try:
            selected_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
            today = datetime.date.today()
            diff_days = (selected_date - today).days
            
            if diff_days < 10:
                return jsonify({
                    'message': 'Please apply at least 10 days before the event date.'
                }), 400
        except ValueError:
            return jsonify({'message': 'Invalid date format.'}), 400
        
        # Double-check overlap
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id FROM event_permits 
            WHERE venue = %s 
              AND event_date = %s 
              AND status IN ('pending', 'approved')
              AND start_time < %s 
              AND end_time > %s
            LIMIT 1
        """, (venue, event_date, end_time, start_time))
        
        conflict = cursor.fetchone()
        
        if conflict:
            conn.close()
            return jsonify({
                'message': 'Paumanhin, may naka-book na sa slot na ito.'
            }), 409
        
        # Generate reference + queue
        ref_num = f"BP-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        queue_num = f"Q-{random.randint(1, 999):03d}"
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO event_permits (
                user_id, event_name, event_description, purpose, event_date, 
                start_time, end_time, estimated_attendees, venue, 
                status, requirements_file, reference_number, queuing_number
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s)
        """, (
            session['user_id'], event_name, event_description, purpose, event_date,
            start_time, end_time, attendees, venue,
            requirement_name, ref_num, queue_num
        ))
        conn.commit()
        event_id = cursor.lastrowid
        
        # Notification
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type)
            VALUES (%s, %s, %s, 'permit_submitted')
        """, (
            session['user_id'], 'Permit Application Submitted',
            f'Your event permit "{event_name}" has been submitted for review. Reference: {ref_num} | Queue: {queue_num}'
        ))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Permit submitted successfully.',
            'event_id': event_id,
            'reference_number': ref_num,
            'queuing_number': queue_num
        }), 201
        
    except mysql.connector.Error as e:
        try:
            conn.close()
        except:
            pass
        import traceback
        traceback.print_exc()
        return jsonify({'message': f'Database error: {str(e)}'}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

# ============================================================
# ===== HEAD ADMIN DASHBOARD =====
# ============================================================

@app.route('/head-admin-dashboard')
def head_admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Please login as Head Admin.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT COUNT(*) as total FROM users")
    total_users = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role = 'resident'")
    total_residents = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role = 'admin'")
    total_admins = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM document_requests")
    total_requests = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM event_permits")
    total_events = cursor.fetchone()['total']
    
    cursor.execute("""
        SELECT d.*, u.first_name, u.last_name 
        FROM document_requests d
        JOIN users u ON d.user_id = u.id
        ORDER BY d.created_at DESC
        LIMIT 5
    """)
    recent_requests = cursor.fetchall()
    
    conn.close()
    
    return render_template('admin/head_admin_dashboard.html',
                         total_users=total_users,
                         total_residents=total_residents,
                         total_admins=total_admins,
                         total_requests=total_requests,
                         total_events=total_events,
                         recent_requests=recent_requests)

# ============================================================
# ===== SECONDARY ADMIN DASHBOARD =====
# ============================================================

@app.route('/admin-dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    
    if session.get('role') not in ['admin', 'head_admin']:
        flash('Unauthorized access. Admin only.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT COUNT(*) as total FROM document_requests WHERE status = 'pending'")
    pending_requests = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM event_permits WHERE status = 'pending'")
    pending_events = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM document_requests")
    total_requests = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM event_permits")
    total_events_total = cursor.fetchone()['total']
    
    cursor.execute("""
        SELECT d.*, u.first_name, u.last_name, u.email 
        FROM document_requests d
        JOIN users u ON d.user_id = u.id
        WHERE d.status = 'pending'
        ORDER BY d.created_at DESC
        LIMIT 5
    """)
    pending_documents = cursor.fetchall()
    
    cursor.execute("""
        SELECT e.*, u.first_name, u.last_name, u.email 
        FROM event_permits e
        JOIN users u ON e.user_id = u.id
        WHERE e.status = 'pending'
        ORDER BY e.created_at DESC
        LIMIT 5
    """)
    pending_events_list = cursor.fetchall()
    
    conn.close()
    
    return render_template('admin/sec_admin_dashboard.html',
                         pending_requests=pending_requests,
                         pending_events=pending_events,
                         total_requests=total_requests,
                         total_events=total_events_total,
                         pending_documents=pending_documents,
                         pending_events_list=pending_events_list)

# ============================================================
# ===== ADMIN DOCUMENT REVIEW =====
# ============================================================

@app.route('/admin/documents')
def admin_documents():
    if 'user_id' not in session or session.get('role') not in ['admin', 'head_admin']:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT d.*, u.first_name, u.last_name, u.email, u.contact_number 
        FROM document_requests d
        JOIN users u ON d.user_id = u.id
        ORDER BY d.created_at DESC
    """)
    documents = cursor.fetchall()
    conn.close()
    
    return render_template('admin/sec_admin_documents.html', documents=documents)

@app.route('/api/document/<int:doc_id>/update-status', methods=['POST'])
def update_document_status(doc_id):
    if 'user_id' not in session or session.get('role') not in ['admin', 'head_admin']:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    status = data.get('status')
    remarks = data.get('remarks', '').strip()
    
    if status not in ['approved', 'rejected']:
        return jsonify({'error': 'Invalid status'}), 400
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        UPDATE document_requests 
        SET status = %s, admin_remarks = %s 
        WHERE id = %s
    """, (status, remarks, doc_id))
    conn.commit()
    
    cursor.execute("""
        SELECT u.email, u.first_name, u.last_name, d.document_type 
        FROM document_requests d
        JOIN users u ON d.user_id = u.id
        WHERE d.id = %s
    """, (doc_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': f'Document {status} successfully',
        'user_data': user_data
    })

@app.route('/admin/document/<int:doc_id>/details')
def admin_document_details(doc_id):
    if 'user_id' not in session or session.get('role') not in ['admin', 'head_admin']:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT d.*, u.first_name, u.last_name, u.email, u.contact_number, u.address 
        FROM document_requests d
        JOIN users u ON d.user_id = u.id
        WHERE d.id = %s
    """, (doc_id,))
    document = cursor.fetchone()
    conn.close()
    
    if not document:
        return jsonify({'error': 'Document not found'}), 404
    
    return jsonify(document)

# ============================================================
# ===== ADMIN EVENT REVIEW =====
# ============================================================

@app.route('/admin/events')
def admin_events():
    if 'user_id' not in session or session.get('role') not in ['admin', 'head_admin']:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT e.*, u.first_name, u.last_name, u.email, u.contact_number 
        FROM event_permits e
        JOIN users u ON e.user_id = u.id
        ORDER BY e.id DESC
    """)
    events = cursor.fetchall()
    conn.close()
    
    return render_template('admin/sec_admin_events.html', events=events)

@app.route('/api/event/<int:event_id>/update-status', methods=['POST'])
def update_event_status(event_id):
    if 'user_id' not in session or session.get('role') not in ['admin', 'head_admin']:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    status = data.get('status')
    remarks = data.get('remarks', '').strip()
    
    if status not in ['approved', 'rejected']:
        return jsonify({'error': 'Invalid status'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE event_permits 
        SET status = %s, admin_remarks = %s 
        WHERE id = %s
    """, (status, remarks, event_id))
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': f'Event permit {status} successfully'
    })

@app.route('/admin/event/<int:event_id>/details')
def admin_event_details(event_id):
    if 'user_id' not in session or session.get('role') not in ['admin', 'head_admin']:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT e.*, u.first_name, u.last_name, u.email, u.contact_number, u.address 
        FROM event_permits e
        JOIN users u ON e.user_id = u.id
        WHERE e.id = %s
    """, (event_id,))
    event = cursor.fetchone()
    conn.close()
    
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    
    return jsonify(event)

# ============================================================
# ===== USER SETTINGS (para sa regular users) =====
# ============================================================

@app.route('/settings')
def settings():
    # 1. Siguraduhing naka-login
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    
    # 2. Kunin ang user info
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    # 3. Kung HEAD ADMIN, ibalik sa admin settings
    if session.get('role') == 'head_admin':
        return redirect(url_for('admin_settings'))
    
    # 4. Para sa regular user/resident -> templates/settings.html
    return render_template('settings.html',
                         user=user,
                         show_settings=True)


# ============================================================
# ===== ADMIN SETTINGS (para sa head admin lang) =====
# ============================================================

@app.route('/admin-settings')
def admin_settings():
    if 'user_id' not in session or session.get('role') not in ['admin', 'head_admin']:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            id INT PRIMARY KEY AUTO_INCREMENT,
            barangay_name VARCHAR(255),
            barangay_address VARCHAR(255),
            contact_number VARCHAR(50),
            email_notifications VARCHAR(20) DEFAULT 'enabled',
            maintenance_mode BOOLEAN DEFAULT FALSE,
            maintenance_message TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    
    cursor.execute("SELECT * FROM system_config LIMIT 1")
    config = cursor.fetchone()
    
    if not config:
        cursor.execute("""
            INSERT INTO system_config (barangay_name, barangay_address, contact_number, email_notifications, maintenance_mode)
            VALUES ('Barangay Sto. Nino', 'Paranaque City', 'N/A', 'enabled', FALSE)
        """)
        conn.commit()
        cursor.execute("SELECT * FROM system_config LIMIT 1")
        config = cursor.fetchone()
    
    conn.close()
    
    maintenance_mode = config.get('maintenance_mode', False) if config else False
    
    return render_template('admin_settings.html',
                         config=config,
                         maintenance_mode=maintenance_mode,
                         user=None,
                         show_settings=True)

@app.route('/update-profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    
    if not first_name or not last_name or not email:
        flash('Please fill in all fields.', 'danger')
        return redirect(url_for('admin_settings'))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET first_name = %s, last_name = %s, email = %s
        WHERE id = %s
    """, (first_name, last_name, email, session['user_id']))
    conn.commit()
    conn.close()
    
    session['fullname'] = f"{first_name} {last_name}"
    session['email'] = email
    
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('admin_settings'))

@app.route('/change-password', methods=['POST'])
def change_password():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    if not current_password or not new_password or not confirm_password:
        flash('Please fill in all fields.', 'danger')
        return redirect(url_for('admin_settings'))
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('admin_settings'))
    
    if len(new_password) < 8:
        flash('New password must be at least 8 characters.', 'danger')
        return redirect(url_for('admin_settings'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT password FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not check_password_hash(user['password'], current_password):
        conn.close()
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('admin_settings'))
    
    hashed_password = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Password changed successfully!', 'success')
    return redirect(url_for('admin_settings'))

@app.route('/system-config', methods=['POST'])
def system_config():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    barangay_name = request.form.get('barangay_name', '').strip()
    barangay_address = request.form.get('barangay_address', '').strip()
    contact_number = request.form.get('contact_number', '').strip()
    email_notifications = request.form.get('email_notifications', 'enabled')
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM system_config LIMIT 1")
    config_exists = cursor.fetchone()
    
    if config_exists:
        cursor.execute("""
            UPDATE system_config 
            SET barangay_name = %s, barangay_address = %s, contact_number = %s, email_notifications = %s
            WHERE id = 1
        """, (barangay_name, barangay_address, contact_number, email_notifications))
    else:
        cursor.execute("""
            INSERT INTO system_config (barangay_name, barangay_address, contact_number, email_notifications)
            VALUES (%s, %s, %s, %s)
        """, (barangay_name, barangay_address, contact_number, email_notifications))
    
    conn.commit()
    conn.close()
    
    flash('System configuration updated successfully!', 'success')
    return redirect(url_for('admin_settings'))

@app.route('/toggle-maintenance', methods=['POST'])
def toggle_maintenance():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    maintenance_message = request.form.get('maintenance_message', 'System is currently under maintenance. Please check back later.')
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT maintenance_mode FROM system_config WHERE id = 1")
    config = cursor.fetchone()
    
    if config:
        new_mode = not config['maintenance_mode']
        cursor.execute("""
            UPDATE system_config 
            SET maintenance_mode = %s, maintenance_message = %s
            WHERE id = 1
        """, (new_mode, maintenance_message))
    else:
        new_mode = True
        cursor.execute("""
            INSERT INTO system_config (maintenance_mode, maintenance_message)
            VALUES (TRUE, %s)
        """, (maintenance_message,))
    
    conn.commit()
    conn.close()
    
    status = 'ON' if new_mode else 'OFF'
    flash(f'Maintenance mode turned {status}!', 'success')
    return redirect(url_for('admin_settings'))

# ============================================================
# ===== USER MANAGEMENT =====
# ============================================================

@app.route('/users')
def user_management():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Please login as Head Admin.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, first_name, last_name, email, contact_number, address, role, is_verified, created_at FROM users WHERE role = 'resident' ORDER BY created_at DESC")
    users = cursor.fetchall()
    conn.close()
    
    for user in users:
        if user.get('created_at'):
            if hasattr(user['created_at'], 'strftime'):
                user['created_at'] = user['created_at'].strftime('%b %d, %Y')
    
    return render_template('admin/user_management.html', users=users)

@app.route('/update-role/<int:user_id>', methods=['POST'])
def update_user_role(user_id):
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    if user_id == session['user_id']:
        flash('You cannot change your own role.', 'danger')
        return redirect(url_for('user_management'))
    
    new_role = request.form.get('role')
    
    if new_role not in ['resident', 'admin', 'head_admin']:
        flash('Invalid role selected.', 'danger')
        return redirect(url_for('user_management'))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
    conn.commit()
    conn.close()
    
    flash(f'User role updated to {new_role.replace("_", " ").title()} successfully!', 'success')
    return redirect(url_for('user_management'))

@app.route('/api/user/<int:user_id>')
def api_get_user(user_id):
    if 'user_id' not in session or session.get('role') != 'head_admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, first_name, last_name, email, contact_number, address, role, is_verified, created_at FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user.get('created_at'):
        if hasattr(user['created_at'], 'strftime'):
            user['created_at'] = user['created_at'].strftime('%b %d, %Y')
    
    return jsonify(user)

@app.route('/api/user/<int:user_id>/toggle-block', methods=['POST'])
def api_toggle_block(user_id):
    if 'user_id' not in session or session.get('role') != 'head_admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    if user_id == session['user_id']:
        return jsonify({'error': 'You cannot block yourself'}), 400
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, is_verified FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    
    new_status = not user['is_verified']
    cursor.execute("UPDATE users SET is_verified = %s WHERE id = %s", (new_status, user_id))
    conn.commit()
    conn.close()
    
    status_text = 'unblocked' if new_status else 'blocked'
    return jsonify({'message': f'User {status_text} successfully', 'status': new_status})

@app.route('/api/user/<int:user_id>/delete', methods=['DELETE'])
def api_delete_user(user_id):
    if 'user_id' not in session or session.get('role') != 'head_admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    if user_id == session['user_id']:
        return jsonify({'error': 'You cannot delete your own account'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'User deleted successfully'})

# ===== ADMIN MANAGEMENT =====
@app.route('/admins')
def admin_management():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Please login as Head Admin.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT id, first_name, last_name, email, contact_number, address, role, is_verified, created_at FROM users WHERE role IN ('admin', 'head_admin') ORDER BY role DESC, created_at DESC")
    admins = cursor.fetchall()
    conn.close()
    
    for admin in admins:
        if admin.get('created_at'):
            if hasattr(admin['created_at'], 'strftime'):
                admin['created_at'] = admin['created_at'].strftime('%b %d, %Y')
    
    return render_template('admin/admin_management.html', admins=admins)

@app.route('/api/residents')
def api_get_residents():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, first_name, last_name, email FROM users WHERE role = 'resident' ORDER BY first_name ASC")
    residents = cursor.fetchall()
    conn.close()
    
    return jsonify(residents)

@app.route('/api/user/<int:user_id>/promote', methods=['POST'])
def api_promote_admin(user_id):
    if 'user_id' not in session or session.get('role') != 'head_admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    if user_id == session['user_id']:
        return jsonify({'error': 'You cannot change your own role'}), 400
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, role FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    
    if user['role'] == 'admin':
        conn.close()
        return jsonify({'error': 'User is already an admin'}), 400
    
    if user['role'] == 'head_admin':
        conn.close()
        return jsonify({'error': 'Cannot change head_admin role'}), 400
    
    cursor.execute("UPDATE users SET role = 'admin' WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'User promoted to Admin successfully'})

@app.route('/api/user/<int:user_id>/demote', methods=['POST'])
def api_demote_admin(user_id):
    if 'user_id' not in session or session.get('role') != 'head_admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    if user_id == session['user_id']:
        return jsonify({'error': 'You cannot demote yourself'}), 400
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, role FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    
    if user['role'] == 'head_admin':
        conn.close()
        return jsonify({'error': 'Cannot demote head_admin'}), 400
    
    if user['role'] != 'admin':
        conn.close()
        return jsonify({'error': 'User is not an admin'}), 400
    
    cursor.execute("UPDATE users SET role = 'resident' WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Admin demoted to Resident successfully'})

@app.route('/create-admin', methods=['POST'])
def create_admin():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'admin')
    
    if not first_name or not last_name or not email or not password:
        flash('Please fill in all fields.', 'danger')
        return redirect(url_for('admin_management'))
    
    if role not in ['admin', 'head_admin']:
        flash('Invalid role selected.', 'danger')
        return redirect(url_for('admin_management'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    existing = cursor.fetchone()
    
    if existing:
        conn.close()
        flash('Email address already registered.', 'danger')
        return redirect(url_for('admin_management'))
    
    hashed_password = generate_password_hash(password)
    
    cursor.execute("""
        INSERT INTO users (first_name, last_name, email, password, role, is_verified)
        VALUES (%s, %s, %s, %s, %s, TRUE)
    """, (first_name, last_name, email, hashed_password, role))
    conn.commit()
    conn.close()
    
    flash('Admin created successfully!', 'success')
    return redirect(url_for('admin_management'))

# ============================================================
# ===== ANNOUNCEMENTS =====
# ============================================================

@app.route('/announcements')
def announcements():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Please login as Head Admin.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT a.*, u.first_name, u.last_name 
        FROM announcements a 
        LEFT JOIN users u ON a.created_by = u.id 
        ORDER BY a.created_at DESC
    """)
    announcements = cursor.fetchall()
    conn.close()
    
    return render_template('admin/announcements.html', announcements=announcements)

@app.route('/create-announcement', methods=['POST'])
def create_announcement():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    
    if not title or not content:
        flash('Please fill in all fields.', 'danger')
        return redirect(url_for('announcements'))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO announcements (title, content, created_by)
        VALUES (%s, %s, %s)
    """, (title, content, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Announcement posted successfully!', 'success')
    return redirect(url_for('announcements'))

@app.route('/edit-announcement/<int:announcement_id>', methods=['POST'])
def edit_announcement(announcement_id):
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    
    if not title or not content:
        flash('Please fill in all fields.', 'danger')
        return redirect(url_for('announcements'))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE announcements SET title = %s, content = %s
        WHERE id = %s
    """, (title, content, announcement_id))
    conn.commit()
    conn.close()
    
    flash('Announcement updated successfully!', 'success')
    return redirect(url_for('announcements'))

@app.route('/delete-announcement/<int:announcement_id>', methods=['DELETE'])
def delete_announcement(announcement_id):
    if 'user_id' not in session or session.get('role') != 'head_admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM announcements WHERE id = %s", (announcement_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Announcement deleted successfully'})

# ============================================================
# ===== API: INCREMENT ANNOUNCEMENT VIEW COUNT =====
# ============================================================

@app.route('/api/announcement/<int:announcement_id>/view', methods=['POST'])
def increment_announcement_view(announcement_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE announcements 
            SET view_count = COALESCE(view_count, 0) + 1 
            WHERE id = %s
        """, (announcement_id,))
        conn.commit()
        
        cursor.execute("SELECT view_count FROM announcements WHERE id = %s", (announcement_id,))
        result = cursor.fetchone()
        conn.close()
        
        return jsonify({
            'success': True,
            'view_count': result[0] if result else 0
        })
        
    except Exception as e:
        print("Error updating view count:", str(e))
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/send-email-all', methods=['POST'])
def send_email_all():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    subject = request.form.get('subject', '').strip()
    message = request.form.get('message', '').strip()
    
    if not subject or not message:
        flash('Please fill in all fields.', 'danger')
        return redirect(url_for('announcements'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT email FROM users")
    users = cursor.fetchall()
    conn.close()
    
    flash(f'Email sent to {len(users)} users!', 'success')
    return redirect(url_for('announcements'))

# ============================================================
# ===== DATABASE BACKUP API =====
# ============================================================

@app.route('/api/backup-database', methods=['POST'])
def backup_database():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        backup_dir = 'backups'
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{backup_dir}/barangay_backup_{timestamp}.sql"
        
        cmd = f"mysqldump -u root -pbsit2026@123 barangay_online_services > {filename}"
        os.system(cmd)
        
        return jsonify({
            'success': True,
            'message': 'Database backup created successfully',
            'filename': filename
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-backup')
def download_backup():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    backup_files = glob.glob('backups/barangay_backup_*.sql')
    
    if not backup_files:
        flash('No backup files found.', 'danger')
        return redirect(url_for('admin_settings'))
    
    latest_backup = max(backup_files, key=os.path.getctime)
    
    return send_file(latest_backup, as_attachment=True, download_name=f"barangay_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.sql")

# ============================================================
# ===== CHECK SESSION =====
# ============================================================

@app.route('/check-session')
def check_session():
    if 'user_id' in session:
        return f"""
        <h1>Session Info</h1>
        <p><strong>User ID:</strong> {session['user_id']}</p>
        <p><strong>Name:</strong> {session['fullname']}</p>
        <p><strong>Email:</strong> {session['email']}</p>
        <p><strong>Role:</strong> {session['role']}</p>
        <hr>
        <a href="/head-admin-dashboard">Head Admin Dashboard</a><br>
        <a href="/admin-dashboard">Admin Dashboard</a><br>
        <a href="/dashboard">Resident Dashboard</a><br>
        <a href="/users">User Management</a><br>
        <a href="/admins">Admin Management</a><br>
        <a href="/announcements">Announcements</a><br>
        <a href="/admin/documents">Document Review</a><br>
        <a href="/admin/events">Event Review</a><br>
        <a href="/logout">Logout</a>
        """
    else:
        return "No active session. <a href='/login'>Login</a>"

# ===== LOGOUT =====
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ============================================================
# ===== FORGOT PASSWORD ROUTE =====
# ============================================================
@app.route('/forgot-password', methods=['GET', 'POST'])
@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.form.get('email', '').strip()
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    if not email or not current_password or not new_password or not confirm_password:
        flash('Please fill in all fields.', 'danger')
        return redirect(url_for('login'))
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('login'))
    
    if len(new_password) < 8:
        flash('New password must be at least 8 characters long.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, password FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        flash('Email address not found.', 'danger')
        return redirect(url_for('login'))
    
    if not check_password_hash(user['password'], current_password):
        conn.close()
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('login'))
    
    hashed_password = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, email))
    conn.commit()
    conn.close()
    
    flash('Password reset successfully! You can now login with your new password.', 'success')
    return redirect(url_for('login'))

# ===== CHECK PERMIT AVAILABILITY =====
@app.route('/api/permits/check-availability', methods=['GET'])
def check_permit_availability():
    if 'user_id' not in session:
        return jsonify({'available': False, 'message': 'Please login first.'}), 401
    
    try:
        date_str = request.args.get('date')
        start_str = request.args.get('start_time')
        end_str = request.args.get('end_time')
        venue = request.args.get('venue')
        
        # Validate presence
        if not all([date_str, start_str, end_str, venue]):
            return jsonify({
                'available': False,
                'message': 'Kulang ang parameters.'
            })
        
        # Normalize time (pwedeng "08:00" o "08:00:00")
        start_time = start_str[:5]  # "08:00"
        end_time = end_str[:5]      # "10:00"
        
        # Server-side validation ng business rules
        if start_time >= end_time:
            return jsonify({
                'available': False,
                'message': 'End time dapat pagkatapos ng start time.'
            })
        
        if start_time < '08:00' or start_time > '22:00':
            return jsonify({
                'available': False,
                'message': 'Start time dapat 8:00 AM – 10:00 PM.'
            })
        
        if end_time < '08:00' or end_time > '22:00':
            return jsonify({
                'available': False,
                'message': 'End time dapat 8:00 AM – 10:00 PM.'
            })
        
        # Check overlap sa existing permits (pending + approved)
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, start_time, end_time 
            FROM event_permits 
            WHERE venue = %s 
              AND event_date = %s 
              AND status IN ('pending', 'approved')
              AND start_time < %s 
              AND end_time > %s
            LIMIT 1
        """, (venue, date_str, end_time, start_time))
        
        conflict = cursor.fetchone()
        conn.close()
        
        if conflict:
            conflict_start = str(conflict['start_time'])[:5]
            conflict_end = str(conflict['end_time'])[:5]
            return jsonify({
                'available': False,
                'message': f'May naka-book na sa {venue} mula {conflict_start} hanggang {conflict_end}.'
            })
        
        return jsonify({'available': True})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'available': False,
            'message': f'Server error: {str(e)}'
        }), 500

# ===== API: UNREAD ANNOUNCEMENTS COUNT =====
@app.route('/api/announcements/unread_count', methods=['GET'])
def api_unread_announcements_count():
    if 'user_id' not in session:
        return jsonify({'unread_count': 0})
    
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Simple: count ng announcements sa last 7 days
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM announcements
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        return jsonify({'unread_count': result['count'] if result else 0})
        
    except Exception as e:
        print(f"Error fetching unread count: {e}")
        return jsonify({'unread_count': 0})
    # ===== USER ANNOUNCEMENTS (Para sa Residents) =====
@app.route('/user-announcements')
def user_announcements():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT a.*, u.first_name, u.last_name 
        FROM announcements a 
        LEFT JOIN users u ON a.created_by = u.id 
        ORDER BY a.created_at DESC
    """)
    announcements = cursor.fetchall()
    conn.close()
    
    return render_template('user_announcements.html', announcements=announcements)

if __name__ == '__main__':
    app.run(debug=True)