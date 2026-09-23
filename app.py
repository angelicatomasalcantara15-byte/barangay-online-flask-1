from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, send_from_directory
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

# ============================================================
# ROLE DEFINITIONS
# ============================================================

ADMIN_ROLES = ['head_admin', 'admin_court_1', 'admin_court_2', 'admin_court_3', 'admin_court_4', 'admin_documents']
COURT_ROLES = ['admin_court_1', 'admin_court_2', 'admin_court_3', 'admin_court_4']
ALL_ROLES = ['resident', 'head_admin', 'admin_court_1', 'admin_court_2', 'admin_court_3', 'admin_court_4', 'admin_documents']

# ============================================================
# COURT CONFIGURATION
# ============================================================

COURT_CONFIG = {
    'admin_court_1': {
        'venue': 'Sto. Nino Sports Complex',
        'dashboard_template': 'admin/admin_court1_dashboard.html',
        'calendar_template': 'admin/admin_court1_calendar.html',
        'pending_template': 'admin/admin_court1_pending.html',
        'label': 'Court 1',
        'icon': 'fa-building',
        'subtitle': 'Sto. Nino Sports Complex'
    },
    'admin_court_2': {
        'venue': 'Sto. Nino Basketball Court',
        'dashboard_template': 'admin/admin_court2_dashboard.html',
        'calendar_template': 'admin/admin_court2_calendar.html',
        'pending_template': 'admin/admin_court2_pending.html',
        'label': 'Court 2',
        'icon': 'fa-basketball-ball',
        'subtitle': 'Sto. Nino Basketball Court'
    },
    'admin_court_3': {
        'venue': 'Sampaguita Covered Court',
        'dashboard_template': 'admin/admin_court3_dashboard.html',
        'calendar_template': 'admin/admin_court3_calendar.html',
        'pending_template': 'admin/admin_court3_pending.html',
        'label': 'Court 3',
        'icon': 'fa-tree',
        'subtitle': 'Sampaguita Covered Court'
    },
    'admin_court_4': {
        'venue': '2nd Street Covered Court',
        'dashboard_template': 'admin/admin_court4_dashboard.html',
        'calendar_template': 'admin/admin_court4_calendar.html',
        'pending_template': 'admin/admin_court4_pending.html',
        'label': 'Court 4',
        'icon': 'fa-road',
        'subtitle': '2nd Street Covered Court'
    }
}

# ============================================================
# FILE UPLOAD CONFIGURATION
# ============================================================

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)

# ============================================================
# HOME/INDEX ROUTE
# ============================================================

@app.route('/')
def index():
    return redirect(url_for('login'))

# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():
    return mysql.connector.connect(
        host='127.0.0.1',
        port=3307,
        user='root',
        password='bsit2026@123',
        database='barangay_online_services'
    )

def get_next_queue_number(table_name):
    """Kunin ang susunod na queue number base sa existing records ngayong araw."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    today = datetime.date.today()
    
    if table_name == 'event_permits':
        cursor.execute("""
            SELECT COUNT(*) as total FROM event_permits 
            WHERE DATE(created_at) = %s
        """, (today,))
    else:
        cursor.execute("""
            SELECT COUNT(*) as total FROM document_requests 
            WHERE DATE(created_at) = %s
        """, (today,))
    
    result = cursor.fetchone()
    conn.close()
    
    count = (result['total'] if result else 0) + 1
    return f"Q-{count:03d}"

# ============================================================
# LOGIN ROUTE
# ============================================================

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
            
            if role == 'admin' and user['role'] not in ADMIN_ROLES:
                flash('You are not authorized as admin.', 'danger')
                return render_template('login.html')
            
            session['user_id'] = user['id']
            session['fullname'] = f"{user['first_name']} {user['last_name']}"
            session['email'] = user['email']
            session['role'] = user['role']
            
            # REDIRECT BASED ON ROLE
            if user['role'] == 'head_admin':
                return redirect(url_for('head_admin_dashboard'))
            elif user['role'] == 'admin_documents':
                return redirect(url_for('sec_admin_dashboard'))
            elif user['role'] == 'admin_court_1':
                return redirect(url_for('court1_dashboard'))
            elif user['role'] == 'admin_court_2':
                return redirect(url_for('court2_dashboard'))
            elif user['role'] == 'admin_court_3':
                return redirect(url_for('court3_dashboard'))
            elif user['role'] == 'admin_court_4':
                return redirect(url_for('court4_dashboard'))
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

# ============================================================
# REGISTER ROUTE
# ============================================================

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
# RESIDENT ROUTES
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

# ============================================================
# EVENTS CALENDAR (RESIDENT)
# ============================================================

@app.route('/events-calendar')
def events_calendar():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    
    return render_template('events_calendar.html')

@app.route('/events')
def events():
    return redirect(url_for('events_calendar'))

# ============================================================
# EVENT CRUD API
# ============================================================

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
    contact_person = data.get('contact_person', '').strip()
    contact_phone = data.get('contact_phone', '').strip()
    event_date = data.get('event_date', '').strip()
    start_time = data.get('start_time', '').strip()[:5]
    end_time = data.get('end_time', '').strip()[:5]
    estimated_attendees = data.get('estimated_attendees', 0)
    venue = data.get('venue', '').strip()
    
    # ===== VALIDATION (Required fields) =====
    if not event_name or not event_date or not start_time or not end_time or not venue:
        return jsonify({'error': 'Please fill in all required fields.'}), 400
    
    if not purpose or not purpose.strip():
        return jsonify({'error': 'Purpose is required.'}), 400
    
    if not contact_person or not contact_person.strip():
        return jsonify({'error': 'Contact person name is required.'}), 400
    
    if not contact_phone or not contact_phone.strip():
        return jsonify({'error': 'Contact phone number is required.'}), 400
    
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
    queue_num = get_next_queue_number('event_permits')
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # ===== SERVER-SIDE HARD BLOCK: Approved conflict =====
        cursor.execute("""
            SELECT id FROM event_permits 
            WHERE venue = %s 
              AND event_date = %s 
              AND status = 'approved'
              AND start_time < %s 
              AND end_time > %s
            LIMIT 1
        """, (venue, event_date, end_time, start_time))
        
        approved_conflict = cursor.fetchone()
        if approved_conflict:
            conn.close()
            return jsonify({'error': 'This time slot is already taken by an approved event at this venue.'}), 409
        
        # Insert (soft warning for pending is allowed)
        cursor.execute("""
            INSERT INTO event_permits (
                user_id, event_name, event_description, purpose, 
                contact_person, contact_phone,
                event_date, start_time, end_time, 
                estimated_attendees, venue, 
                status, reference_number, queuing_number
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)
        """, (
            session['user_id'], event_name, event_description, purpose,
            contact_person, contact_phone,
            event_date, start_time, end_time,
            estimated_attendees if estimated_attendees else 0,
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
    purpose = data.get('purpose', event.get('purpose', '')).strip()
    contact_person = data.get('contact_person', event.get('contact_person', '')).strip()
    contact_phone = data.get('contact_phone', event.get('contact_phone', '')).strip()
    event_date = data.get('event_date', str(event['event_date'])).strip()
    start_time = data.get('start_time', str(event['start_time'])).strip()[:5]
    end_time = data.get('end_time', str(event['end_time'])).strip()[:5]
    estimated_attendees = data.get('estimated_attendees', event['estimated_attendees'])
    venue = data.get('venue', event['venue']).strip()
    
    if not event_name or not event_date or not start_time or not end_time or not venue:
        conn.close()
        return jsonify({'error': 'Please fill in all required fields.'}), 400
    
    if not purpose:
        conn.close()
        return jsonify({'error': 'Purpose is required.'}), 400
    
    if not contact_person:
        conn.close()
        return jsonify({'error': 'Contact person is required.'}), 400
    
    if not contact_phone:
        conn.close()
        return jsonify({'error': 'Contact phone is required.'}), 400
    
    if start_time >= end_time:
        conn.close()
        return jsonify({'error': 'End time must be after start time.'}), 400
    
    cursor.execute("""
        UPDATE event_permits SET
            event_name = %s,
            event_description = %s,
            purpose = %s,
            contact_person = %s,
            contact_phone = %s,
            event_date = %s,
            start_time = %s,
            end_time = %s,
            estimated_attendees = %s,
            venue = %s
        WHERE id = %s
    """, (event_name, event_description, purpose, contact_person, contact_phone,
          event_date, start_time, end_time, estimated_attendees, venue, event_id))
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
    
    cursor.execute("SELECT * FROM document_requests WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
    document_requests = cursor.fetchall()
    
    cursor.execute("SELECT * FROM event_permits WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
    event_permits = cursor.fetchall()
    
    # Stats
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
    
    cursor.execute("SELECT * FROM document_requests WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
    document_requests = cursor.fetchall()
    
    cursor.execute("SELECT * FROM event_permits WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
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
# REQUEST DOCUMENT (POST)
# ============================================================

@app.route('/request-document', methods=['POST'])
def request_document_post():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    
    document_type = request.form.get('document_type', '').strip()
    surname = request.form.get('surname', '').strip()
    given_name = request.form.get('given_name', '').strip()
    middle_name = request.form.get('middle_name', '').strip()
    address = request.form.get('address', '').strip()
    contact_no = request.form.get('contact_no', '').strip()
    civil_status = request.form.get('civil_status', '').strip()
    age = request.form.get('age', 0)
    dob = request.form.get('dob', '').strip()
    precinct_no = request.form.get('precinct_no', '').strip()
    place_of_birth = request.form.get('place_of_birth', '').strip()
    length_of_stay = request.form.get('length_of_stay', '').strip()
    residency_type = request.form.get('residency_type', '').strip()
    lessor_name = request.form.get('lessor_name', '').strip()
    lessor_address = request.form.get('lessor_address', '').strip()
    rep_position = request.form.get('rep_position', '').strip()
    father_name = request.form.get('father_name', '').strip()
    mother_name = request.form.get('mother_name', '').strip()
    spouse_name = request.form.get('spouse_name', '').strip()
    occupation = request.form.get('occupation', '').strip()
    emergency_name = request.form.get('emergency_name', '').strip()
    emergency_number = request.form.get('emergency_number', '').strip()
    ref1_name = request.form.get('ref1_name', '').strip()
    ref1_address = request.form.get('ref1_address', '').strip()
    ref2_name = request.form.get('ref2_name', '').strip()
    ref2_address = request.form.get('ref2_address', '').strip()
    purpose = request.form.get('purpose', '').strip()
    printed_name = request.form.get('printed_name', '').strip()
    signature_date = request.form.get('signature_date', '').strip()
    
    if not document_type or not surname or not given_name or not address:
        flash('Please fill in all required fields.', 'danger')
        return redirect(url_for('request_document'))
    
    file_data = None
    if 'fileInput' in request.files:
        file = request.files['fileInput']
        if file and file.filename:
            filename = file.filename
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            file_data = filename
    
    ref_num = f"DOC-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
    queue_num = get_next_queue_number('document_requests')
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO document_requests (
                user_id, document_type, surname, given_name, middle_name,
                address, contact_no, civil_status, age, dob,
                precinct_no, place_of_birth, length_of_stay, residency_type,
                lessor_name, lessor_address, rep_position,
                father_name, mother_name, spouse_name, occupation,
                emergency_name, emergency_number,
                ref1_name, ref1_address, ref2_name, ref2_address,
                purpose, printed_name, signature_date,
                reference_number, queuing_number, status,
                document_path
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, 'pending',
                %s
            )
        """, (
            session['user_id'], document_type, surname, given_name, middle_name,
            address, contact_no, civil_status, age, dob,
            precinct_no, place_of_birth, length_of_stay, residency_type,
            lessor_name, lessor_address, rep_position,
            father_name, mother_name, spouse_name, occupation,
            emergency_name, emergency_number,
            ref1_name, ref1_address, ref2_name, ref2_address,
            purpose, printed_name, signature_date,
            ref_num, queue_num,
            file_data
        ))
        conn.commit()
        
        flash('Document request submitted successfully! Reference: ' + ref_num, 'success')
        return redirect(url_for('my_requests'))
        
    except mysql.connector.Error as e:
        flash(f'Database error: {str(e)}', 'danger')
        return redirect(url_for('request_document'))
    finally:
        conn.close()

# ============================================================
# SUBMIT DOCUMENT REQUEST (API)
# ============================================================

@app.route('/submit-document-request', methods=['POST'])
def submit_document_request():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first.'}), 401
    
    try:
        data = request.form.to_dict()
        
        file_data = None
        if 'fileInput' in request.files:
            file = request.files['fileInput']
            if file and file.filename:
                filename = file.filename
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                file_data = filename
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("DESCRIBE document_requests")
        columns = cursor.fetchall()
        col_names = []
        for col in columns:
            col_names.append(col[0])
        
        required_columns = ['user_id', 'document_type', 'reference_number', 'status']
        missing_columns = [col for col in required_columns if col not in col_names]
        
        if missing_columns:
            error_msg = f"MISSING COLUMNS SA DATABASE: {', '.join(missing_columns)}. Idagdag mo muna ito sa MySQL!"
            conn.close()
            return jsonify({'error': error_msg}), 500
        
        ref_num = f"DOC-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        queue_num = get_next_queue_number('document_requests')
        
        insert_cols = ['user_id', 'document_type', 'reference_number', 'status']
        insert_vals = [session['user_id'], data.get('document_type', 'clearance'), ref_num, 'pending']
        
        if 'queuing_number' in col_names:
            insert_cols.append('queuing_number')
            insert_vals.append(queue_num)
        
        if file_data and 'document_path' in col_names:
            insert_cols.append('document_path')
            insert_vals.append(file_data)
        
        for key, value in data.items():
            if key in col_names and key not in insert_cols and key != 'type' and key != 'fileInput':
                insert_cols.append(key)
                insert_vals.append(value)
        
        placeholders = ', '.join(['%s'] * len(insert_cols))
        columns_str = ', '.join(insert_cols)
        
        sql = f"INSERT INTO document_requests ({columns_str}) VALUES ({placeholders})"
        
        cursor.execute(sql, tuple(insert_vals))
        conn.commit()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Document request submitted successfully',
            'reference_number': ref_num,
            'queuing_number': queue_num if 'queuing_number' in col_names else 'N/A'
        })
        
    except Exception as e:
        try:
            conn.close()
        except:
            pass
        return jsonify({'error': str(e)}), 500

# ============================================================
# APPLY FOR PERMIT
# ============================================================

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
    contact_person = request.form.get('contact_person', '').strip()
    contact_phone = request.form.get('contact_phone', '').strip()
    event_date = request.form.get('event_date', '').strip()
    start_time = request.form.get('start_time', '').strip()[:5]
    end_time = request.form.get('end_time', '').strip()[:5]
    estimated_attendees = request.form.get('estimated_attendees', '').strip()
    venue = request.form.get('venue', '').strip()
    
    # ===== REQUIRED FIELDS =====
    if not event_name or not event_date or not start_time or not end_time or not venue:
        flash('Please fill in all required fields.', 'danger')
        return redirect(url_for('apply_permit'))
    
    if not purpose:
        flash('Purpose is required.', 'danger')
        return redirect(url_for('apply_permit'))
    
    if not contact_person:
        flash('Contact person name is required.', 'danger')
        return redirect(url_for('apply_permit'))
    
    if not contact_phone:
        flash('Contact phone number is required.', 'danger')
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
            filename = file.filename
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            file_data = filename
    
    ref_num = f"BP-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
    queue_num = get_next_queue_number('event_permits')
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # ===== SERVER-SIDE HARD BLOCK: Approved conflict =====
        cursor.execute("""
            SELECT id FROM event_permits 
            WHERE venue = %s 
              AND event_date = %s 
              AND status = 'approved'
              AND start_time < %s 
              AND end_time > %s
            LIMIT 1
        """, (venue, event_date, end_time, start_time))
        approved_conflict = cursor.fetchone()
        if approved_conflict:
            flash('This time slot is already taken by an approved event at this venue.', 'danger')
            return redirect(url_for('apply_permit'))
        
        cursor.execute("""
            INSERT INTO event_permits (
                user_id, event_name, event_description, purpose, 
                contact_person, contact_phone,
                event_date, start_time, end_time, estimated_attendees, venue, 
                status, requirements_file, reference_number, queuing_number
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s)
        """, (
            session['user_id'], event_name, event_description, purpose,
            contact_person, contact_phone,
            event_date, start_time, end_time,
            estimated_attendees if estimated_attendees else 0,
            venue, file_data, ref_num, queue_num
        ))
        conn.commit()
        
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type)
            VALUES (%s, %s, %s, 'permit_submitted')
        """, (
            session['user_id'], 'Permit Application Submitted',
            f'Your event permit "{event_name}" has been submitted for review. Reference: {ref_num} | Queue: {queue_num}'
        ))
        conn.commit()
        
        flash('Permit application submitted successfully! Reference: ' + ref_num, 'success')
        return redirect(url_for('my_requests'))
        
    except mysql.connector.Error as e:
        flash(f'Database error: {str(e)}', 'danger')
        return redirect(url_for('apply_permit'))
    finally:
        conn.close()

# ============================================================
# CHECK PERMIT AVAILABILITY (UPDATED - HARD BLOCK / SOFT WARNING)
# ============================================================
@app.route('/api/permits/check-availability', methods=['GET'])
def check_permit_availability():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Please login first.'}), 401
    
    try:
        date_str = request.args.get('date')
        start_str = request.args.get('start_time')
        end_str = request.args.get('end_time')
        venue = request.args.get('venue')
        
        # Debug print
        print(f"\n🔍 CHECK: date={date_str}, start={start_str}, end={end_str}, venue={venue}")
        
        if not all([date_str, start_str, end_str, venue]):
            return jsonify({'status': 'error', 'message': 'Missing parameters.'})
        
        # Normalize time to HH:MM
        start_time = start_str[:5]
        end_time = end_str[:5]
        
        # Basic validation
        if start_time >= end_time:
            return jsonify({'status': 'error', 'message': 'End time must be after start time.'})
        
        if start_time < '08:00' or start_time > '22:00':
            return jsonify({'status': 'error', 'message': 'Start time must be between 8:00 AM and 10:00 PM.'})
        
        if end_time < '08:00' or end_time > '22:00':
            return jsonify({'status': 'error', 'message': 'End time must be between 8:00 AM and 10:00 PM.'})
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # ===== CHECK APPROVED (HARD BLOCK) =====
        # Simpleng overlap check: 
        # conflict kung (existing_start < new_end) AND (existing_end > new_start)
        cursor.execute("""
            SELECT id, start_time, end_time 
            FROM event_permits 
            WHERE venue = %s 
              AND event_date = %s 
              AND status = 'approved'
              AND start_time < %s 
              AND end_time > %s
            LIMIT 1
        """, (venue, date_str, end_time, start_time))
        
        approved_conflict = cursor.fetchone()
        print(f"   approved_conflict: {approved_conflict}")
        
        if approved_conflict:
            cs = str(approved_conflict['start_time'])[:5]
            ce = str(approved_conflict['end_time'])[:5]
            conn.close()
            return jsonify({
                'status': 'blocked',
                'message': f'This slot is already taken by an approved event ({cs} - {ce}).'
            })
        
        # ===== CHECK PENDING (SOFT WARNING) =====
        cursor.execute("""
            SELECT id, start_time, end_time 
            FROM event_permits 
            WHERE venue = %s 
              AND event_date = %s 
              AND status = 'pending'
              AND start_time < %s 
              AND end_time > %s
            LIMIT 1
        """, (venue, date_str, end_time, start_time))
        
        pending_conflict = cursor.fetchone()
        print(f"   pending_conflict: {pending_conflict}")
        
        conn.close()
        
        if pending_conflict:
            cs = str(pending_conflict['start_time'])[:5]
            ce = str(pending_conflict['end_time'])[:5]
            return jsonify({
                'status': 'pending_conflict',
                'message': f'There is a pending permit for this slot ({cs} - {ce}). You may still apply, but it could conflict if approved.'
            })
        
        print(f"   ✅ AVAILABLE")
        return jsonify({'status': 'available'})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'Server error: {str(e)}'}), 500

# ============================================================
# HEAD ADMIN DASHBOARD
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
    
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role IN ('head_admin', 'admin_court_1', 'admin_court_2', 'admin_court_3', 'admin_court_4', 'admin_documents')")
    total_admins = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM document_requests")
    total_requests = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM event_permits")
    total_events = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM document_requests WHERE status = 'pending'")
    pending_docs = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM event_permits WHERE status = 'pending'")
    pending_events = cursor.fetchone()['total']
    
    pending_total = pending_docs + pending_events
    
    cursor.execute("SELECT COUNT(*) as total FROM document_requests WHERE status = 'approved'")
    approved_docs = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM event_permits WHERE status = 'approved'")
    approved_events = cursor.fetchone()['total']
    
    approved_total = approved_docs + approved_events
    
    cursor.execute("SELECT COUNT(*) as total FROM document_requests WHERE status = 'rejected'")
    rejected_docs = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM event_permits WHERE status = 'rejected'")
    rejected_events = cursor.fetchone()['total']
    
    rejected_total = rejected_docs + rejected_events
    
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
    
    return render_template('admin/head_admin_dashboard.html',
                         total_users=total_users,
                         total_residents=total_residents,
                         total_admins=total_admins,
                         total_requests=total_requests,
                         total_events=total_events,
                         pending_docs=pending_docs,
                         pending_events=pending_events,
                         pending_total=pending_total,
                         approved_total=approved_total,
                         rejected_total=rejected_total,
                         pending_documents=pending_documents,
                         pending_events_list=pending_events_list)

# ============================================================
# HEAD ADMIN ALL DOCUMENTS
# ============================================================

@app.route('/head-admin/all-documents')
def head_admin_all_documents():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Unauthorized access. Head Admin only.', 'danger')
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
    
    return render_template('admin/head_admin_all_documents.html', documents=documents)

# ============================================================
# HEAD ADMIN ALL EVENTS
# ============================================================

@app.route('/head-admin/events')
def head_admin_events():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Unauthorized access. Head Admin only.', 'danger')
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
    
    return render_template('admin/head_admin_events.html', events=events)

@app.route('/head-admin/events/calendar')
def head_admin_events_calendar():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Unauthorized access. Head Admin only.', 'danger')
        return redirect(url_for('login'))
    
    return render_template('admin/head_admin_events_calendar.html')

# ============================================================
# API: APPROVED EVENTS (WITH EVENT NAME + ATTENDEES)
# ============================================================

@app.route('/api/events/approved')
def api_approved_events():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Isama ang event_name at estimated_attendees
    cursor.execute("""
        SELECT e.id, e.event_name, e.event_date, e.start_time, e.end_time, 
               e.venue, e.estimated_attendees
        FROM event_permits e
        WHERE e.status = 'approved'
        ORDER BY e.event_date ASC, e.start_time ASC
    """)
    events = cursor.fetchall()
    conn.close()
    
    result = []
    for event in events:
        # Format date
        event_date = event['event_date'].strftime('%Y-%m-%d') if event.get('event_date') else None
        
        # Format start time (handle timedelta or time)
        start_time = ''
        if event.get('start_time'):
            if hasattr(event['start_time'], 'total_seconds'):
                total_seconds = int(event['start_time'].total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                start_time = f"{hours:02d}:{minutes:02d}"
            else:
                start_time = str(event['start_time'])[:5]
        
        # Format end time
        end_time = ''
        if event.get('end_time'):
            if hasattr(event['end_time'], 'total_seconds'):
                total_seconds = int(event['end_time'].total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                end_time = f"{hours:02d}:{minutes:02d}"
            else:
                end_time = str(event['end_time'])[:5]
        
        result.append({
            'id': event['id'],
            'title': event.get('event_name') or 'Untitled Event',  # <-- EVENT NAME
            'date': event_date,
            'start_time': start_time,
            'end_time': end_time,
            'venue': event.get('venue') or 'N/A',
            'attendees': event.get('estimated_attendees') or 0,   # <-- ATTENDEES
        })
    
    return jsonify(result)

# ============================================================
# SECONDARY ADMIN DASHBOARD (DOCUMENTS ADMIN ONLY)
# ============================================================

@app.route('/sec-admin-dashboard')
def sec_admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin_documents':
        flash('Please login as Documents Admin.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT COUNT(*) as total FROM document_requests")
    total_documents = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM document_requests WHERE status = 'pending'")
    pending_documents = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM document_requests WHERE status = 'approved'")
    approved_documents = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM document_requests WHERE status = 'rejected'")
    rejected_documents = cursor.fetchone()['total']
    
    weekly_data = []
    for i in range(6, -1, -1):
        date = datetime.date.today() - datetime.timedelta(days=i)
        cursor.execute("""
            SELECT COUNT(*) as total FROM document_requests 
            WHERE DATE(created_at) = %s
        """, (date,))
        weekly_data.append(cursor.fetchone()['total'])
    
    cursor.execute("""
        SELECT d.*, u.first_name, u.last_name 
        FROM document_requests d
        JOIN users u ON d.user_id = u.id
        WHERE d.status = 'pending'
        ORDER BY d.created_at DESC
        LIMIT 5
    """)
    recent_pending = cursor.fetchall()
    
    conn.close()
    
    return render_template('admin/sec_admin_dashboard.html',
                         total_documents=total_documents,
                         pending_documents=pending_documents,
                         approved_documents=approved_documents,
                         rejected_documents=rejected_documents,
                         weekly_data=weekly_data,
                         recent_pending=recent_pending)

# ============================================================
# ADMIN DOCUMENT REVIEW (ALL)
# ============================================================

@app.route('/admin/documents')
def admin_documents():
    if 'user_id' not in session or session.get('role') not in ADMIN_ROLES:
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

@app.route('/admin/documents/clearance')
def admin_documents_clearance():
    if 'user_id' not in session or session.get('role') not in ADMIN_ROLES:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT d.*, u.first_name, u.last_name, u.email, u.contact_number 
        FROM document_requests d
        JOIN users u ON d.user_id = u.id
        WHERE d.document_type = 'clearance'
        ORDER BY d.created_at DESC
    """)
    documents = cursor.fetchall()
    conn.close()
    
    return render_template('admin/sec_admin_documents_clearance.html', documents=documents)

@app.route('/admin/documents/indigency')
def admin_documents_indigency():
    if 'user_id' not in session or session.get('role') not in ADMIN_ROLES:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT d.*, u.first_name, u.last_name, u.email, u.contact_number 
        FROM document_requests d
        JOIN users u ON d.user_id = u.id
        WHERE d.document_type = 'indigency'
        ORDER BY d.created_at DESC
    """)
    documents = cursor.fetchall()
    conn.close()
    
    return render_template('admin/sec_admin_documents_indigency.html', documents=documents)

@app.route('/admin/documents/residency')
def admin_documents_residency():
    if 'user_id' not in session or session.get('role') not in ADMIN_ROLES:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT d.*, u.first_name, u.last_name, u.email, u.contact_number 
        FROM document_requests d
        JOIN users u ON d.user_id = u.id
        WHERE d.document_type = 'proof_residency'
        ORDER BY d.created_at DESC
    """)
    documents = cursor.fetchall()
    conn.close()
    
    return render_template('admin/sec_admin_documents_residency.html', documents=documents)

# ============================================================
# COURT DASHBOARDS (HELPER FUNCTION)
# ============================================================

def _render_court_dashboard(role):
    if 'user_id' not in session or session.get('role') != role:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    config = COURT_CONFIG.get(role)
    if not config:
        flash('Invalid court role.', 'danger')
        return redirect(url_for('login'))
    
    VENUE = config['venue']
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT COUNT(*) as total FROM event_permits WHERE venue = %s", (VENUE,))
    total_events = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM event_permits WHERE venue = %s AND status = 'pending'", (VENUE,))
    pending_events = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM event_permits WHERE venue = %s AND status = 'approved'", (VENUE,))
    approved_events = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM event_permits WHERE venue = %s AND status = 'rejected'", (VENUE,))
    rejected_events = cursor.fetchone()['total']
    
    monthly_data = []
    current_year = datetime.date.today().year
    for month in range(1, 7):
        cursor.execute("""
            SELECT COUNT(*) as total FROM event_permits 
            WHERE venue = %s 
            AND MONTH(event_date) = %s 
            AND YEAR(event_date) = %s
        """, (VENUE, month, current_year))
        monthly_data.append(cursor.fetchone()['total'])
    
    cursor.execute("""
        SELECT e.*, u.first_name, u.last_name 
        FROM event_permits e
        JOIN users u ON e.user_id = u.id
        WHERE e.venue = %s AND e.status = 'pending'
        ORDER BY e.id DESC
    """, (VENUE,))
    pending_events_list = cursor.fetchall()
    
    conn.close()
    
    return render_template(config['dashboard_template'],
                         total_events=total_events,
                         pending_events=pending_events,
                         approved_events=approved_events,
                         rejected_events=rejected_events,
                         monthly_data=monthly_data,
                         pending_events_list=pending_events_list,
                         court_config=config)

# ============================================================
# COURT PENDING EVENTS (HELPER FUNCTION)
# ============================================================

def _render_court_pending(role):
    if 'user_id' not in session or session.get('role') != role:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    config = COURT_CONFIG.get(role)
    if not config:
        flash('Invalid court role.', 'danger')
        return redirect(url_for('login'))
    
    VENUE = config['venue']
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT e.*, u.first_name, u.last_name, u.email, u.contact_number
        FROM event_permits e
        JOIN users u ON e.user_id = u.id
        WHERE e.venue = %s AND e.status = 'pending'
        ORDER BY e.event_date ASC
    """, (VENUE,))
    pending_events = cursor.fetchall()
    
    conn.close()
    
    # ✅ FIX: I-convert ang timedelta at date objects sa string
    # (Ito ang DINAGDAG para sa TypeError: Object of type timedelta is not JSON serializable)
    for event in pending_events:
        # Convert date objects to string
        if event.get('event_date'):
            if hasattr(event['event_date'], 'strftime'):
                event['event_date'] = event['event_date'].strftime('%Y-%m-%d')
        
        # Convert timedelta objects to string (HH:MM)
        if event.get('start_time'):
            if hasattr(event['start_time'], 'total_seconds'):
                total_seconds = int(event['start_time'].total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                event['start_time'] = f"{hours:02d}:{minutes:02d}"
            else:
                event['start_time'] = str(event['start_time'])[:5]
        
        if event.get('end_time'):
            if hasattr(event['end_time'], 'total_seconds'):
                total_seconds = int(event['end_time'].total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                event['end_time'] = f"{hours:02d}:{minutes:02d}"
            else:
                event['end_time'] = str(event['end_time'])[:5]
        
        # Convert datetime objects to string
        if event.get('created_at'):
            if hasattr(event['created_at'], 'strftime'):
                event['created_at'] = event['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        if event.get('updated_at'):
            if hasattr(event['updated_at'], 'strftime'):
                event['updated_at'] = event['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
    
    return render_template(config['pending_template'],
                         pending_events=pending_events,
                         court_config=config)

# COURT 1
@app.route('/court1/dashboard')
def court1_dashboard():
    return _render_court_dashboard('admin_court_1')

@app.route('/court1/pending')
def court1_pending():
    return _render_court_pending('admin_court_1')

@app.route('/court1/calendar')
def court1_calendar():
    if 'user_id' not in session or session.get('role') != 'admin_court_1':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    return render_template('admin/admin_court1_calendar.html')

# COURT 2
@app.route('/court2/dashboard')
def court2_dashboard():
    return _render_court_dashboard('admin_court_2')

@app.route('/court2/pending')
def court2_pending():
    return _render_court_pending('admin_court_2')

@app.route('/court2/calendar')
def court2_calendar():
    if 'user_id' not in session or session.get('role') != 'admin_court_2':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    return render_template('admin/admin_court2_calendar.html')

# COURT 3
@app.route('/court3/dashboard')
def court3_dashboard():
    return _render_court_dashboard('admin_court_3')

@app.route('/court3/pending')
def court3_pending():
    return _render_court_pending('admin_court_3')

@app.route('/court3/calendar')
def court3_calendar():
    if 'user_id' not in session or session.get('role') != 'admin_court_3':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    return render_template('admin/admin_court3_calendar.html')

# COURT 4
@app.route('/court4/dashboard')
def court4_dashboard():
    return _render_court_dashboard('admin_court_4')

@app.route('/court4/pending')
def court4_pending():
    return _render_court_pending('admin_court_4')

@app.route('/court4/calendar')
def court4_calendar():
    if 'user_id' not in session or session.get('role') != 'admin_court_4':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    return render_template('admin/admin_court4_calendar.html')

# ============================================================
# API: COURT EVENTS (Para sa Calendar - APPROVED ONLY)
# ============================================================

@app.route('/api/court1/events')
def api_court1_events():
    if 'user_id' not in session or session.get('role') != 'admin_court_1':
        return jsonify({'error': 'Unauthorized'}), 401
    return _get_court_events('admin_court_1')

@app.route('/api/court2/events')
def api_court2_events():
    if 'user_id' not in session or session.get('role') != 'admin_court_2':
        return jsonify({'error': 'Unauthorized'}), 401
    return _get_court_events('admin_court_2')

@app.route('/api/court3/events')
def api_court3_events():
    if 'user_id' not in session or session.get('role') != 'admin_court_3':
        return jsonify({'error': 'Unauthorized'}), 401
    return _get_court_events('admin_court_3')

@app.route('/api/court4/events')
def api_court4_events():
    if 'user_id' not in session or session.get('role') != 'admin_court_4':
        return jsonify({'error': 'Unauthorized'}), 401
    return _get_court_events('admin_court_4')


def _get_court_events(role):
    config = COURT_CONFIG.get(role)
    if not config:
        return jsonify({'error': 'Invalid court'}), 400
    
    VENUE = config['venue']
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT e.*, u.first_name, u.last_name 
        FROM event_permits e
        JOIN users u ON e.user_id = u.id
        WHERE e.venue = %s AND e.status = 'approved'
        ORDER BY e.event_date ASC
    """, (VENUE,))
    events = cursor.fetchall()
    conn.close()
    
    result = []
    for event in events:
        result.append({
            'id': event['id'],
            'title': event['event_name'],
            'start': event['event_date'].strftime('%Y-%m-%d') if event['event_date'] else None,
            'extendedProps': {
                'status': event['status'],
                'reference': event['reference_number'] or 'N/A',
                'organizer': f"{event['first_name']} {event['last_name']}",
                'venue': event['venue'] or 'N/A',
                'attendees': event['estimated_attendees'] or 0,
                'start_time': str(event['start_time']) if event['start_time'] else '',
                'end_time': str(event['end_time']) if event['end_time'] else '',
                'purpose': event['purpose'] or 'N/A',
                'contact_person': event.get('contact_person') or 'N/A',
                'contact_phone': event.get('contact_phone') or 'N/A',
                'remarks': event.get('admin_remarks', '') or ''
            }
        })
    
    return jsonify(result)

# ============================================================
# API: UPDATE EVENT STATUS (Approve/Reject) - COURT SPECIFIC
# ============================================================

@app.route('/api/court1/event/<int:event_id>/update-status', methods=['POST'])
def court1_update_event_status(event_id):
    if 'user_id' not in session or session.get('role') != 'admin_court_1':
        return jsonify({'error': 'Unauthorized'}), 401
    return _update_event_status(event_id)

@app.route('/api/court2/event/<int:event_id>/update-status', methods=['POST'])
def court2_update_event_status(event_id):
    if 'user_id' not in session or session.get('role') != 'admin_court_2':
        return jsonify({'error': 'Unauthorized'}), 401
    return _update_event_status(event_id)

@app.route('/api/court3/event/<int:event_id>/update-status', methods=['POST'])
def court3_update_event_status(event_id):
    if 'user_id' not in session or session.get('role') != 'admin_court_3':
        return jsonify({'error': 'Unauthorized'}), 401
    return _update_event_status(event_id)

@app.route('/api/court4/event/<int:event_id>/update-status', methods=['POST'])
def court4_update_event_status(event_id):
    if 'user_id' not in session or session.get('role') != 'admin_court_4':
        return jsonify({'error': 'Unauthorized'}), 401
    return _update_event_status(event_id)


def _update_event_status(event_id):
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
        'message': f'Event {status} successfully'
    })

# ============================================================
# ACTIVITY LOGS
# ============================================================

@app.route('/admin/activity-logs')
def admin_activity_logs():
    if 'user_id' not in session or session.get('role') not in ADMIN_ROLES:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT l.*, u.first_name, u.last_name
        FROM admin_activity_logs l
        JOIN users u ON l.admin_id = u.id
        WHERE l.admin_id = %s
        ORDER BY l.created_at DESC
        LIMIT 50
    """, (session['user_id'],))
    logs = cursor.fetchall()
    conn.close()
    
    return render_template('admin/sec_admin_activity_logs.html', logs=logs)

@app.route('/api/document/<int:doc_id>/update-status', methods=['POST'])
def update_document_status(doc_id):
    if 'user_id' not in session or session.get('role') not in ADMIN_ROLES:
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
        INSERT INTO admin_activity_logs (admin_id, action, document_id, details)
        VALUES (%s, %s, %s, %s)
    """, (session['user_id'], status, doc_id, f'Document {status} - Remarks: {remarks}'))
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
    if 'user_id' not in session or session.get('role') not in ADMIN_ROLES:
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
    
    if document.get('created_at'):
        if hasattr(document['created_at'], 'strftime'):
            document['created_at_formatted'] = document['created_at'].strftime('%b %d, %Y')
        else:
            document['created_at_formatted'] = str(document['created_at'])
    
    if document.get('dob'):
        if hasattr(document['dob'], 'strftime'):
            document['dob'] = document['dob'].strftime('%Y-%m-%d')
    
    if document.get('signature_date'):
        if hasattr(document['signature_date'], 'strftime'):
            document['signature_date'] = document['signature_date'].strftime('%Y-%m-%d')
    
    return jsonify(document)

# ============================================================
# ADMIN EVENT REVIEW
# ============================================================

@app.route('/admin/events')
def admin_events():
    if 'user_id' not in session or session.get('role') not in ADMIN_ROLES:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    role = session.get('role')
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    if role in COURT_CONFIG:
        VENUE = COURT_CONFIG[role]['venue']
        cursor.execute("""
            SELECT e.*, u.first_name, u.last_name, u.email, u.contact_number 
            FROM event_permits e
            JOIN users u ON e.user_id = u.id
            WHERE e.venue = %s
            ORDER BY e.id DESC
        """, (VENUE,))
    else:
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
    if 'user_id' not in session or session.get('role') not in ADMIN_ROLES:
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
    if 'user_id' not in session or session.get('role') not in ADMIN_ROLES:
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
    
    if event.get('start_time'):
        if hasattr(event['start_time'], 'strftime'):
            event['start_time'] = event['start_time'].strftime('%H:%M:%S')
        else:
            event['start_time'] = str(event['start_time'])
    
    if event.get('end_time'):
        if hasattr(event['end_time'], 'strftime'):
            event['end_time'] = event['end_time'].strftime('%H:%M:%S')
        else:
            event['end_time'] = str(event['end_time'])
    
    if event.get('event_date'):
        if hasattr(event['event_date'], 'strftime'):
            event['event_date'] = event['event_date'].strftime('%Y-%m-%d')
    
    if event.get('created_at'):
        if hasattr(event['created_at'], 'strftime'):
            event['created_at'] = event['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    
    if event.get('applied_at'):
        if hasattr(event['applied_at'], 'strftime'):
            event['applied_at'] = event['applied_at'].strftime('%Y-%m-%d %H:%M:%S')
    
    if event.get('approved_at'):
        if hasattr(event['approved_at'], 'strftime'):
            event['approved_at'] = event['approved_at'].strftime('%Y-%m-%d %H:%M:%S')
    
    return jsonify(event)

# ============================================================
# SECONDARY ADMIN SETTINGS
# ============================================================

@app.route('/sec-admin-settings')
def sec_admin_settings():
    if 'user_id' not in session or session.get('role') not in ADMIN_ROLES:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    return render_template('admin/sec_admin_settings.html')

@app.route('/admin-update-profile', methods=['POST'])
def admin_update_profile():
    if 'user_id' not in session or session.get('role') not in ADMIN_ROLES:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    
    if not first_name or not last_name or not email:
        flash('Please fill in all fields.', 'danger')
        return redirect(url_for('sec_admin_settings'))
    
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
    return redirect(url_for('sec_admin_settings'))

@app.route('/admin-change-password', methods=['POST'])
def admin_change_password():
    if 'user_id' not in session or session.get('role') not in ADMIN_ROLES:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    if not current_password or not new_password or not confirm_password:
        flash('Please fill in all fields.', 'danger')
        return redirect(url_for('sec_admin_settings'))
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('sec_admin_settings'))
    
    if len(new_password) < 8:
        flash('New password must be at least 8 characters.', 'danger')
        return redirect(url_for('sec_admin_settings'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT password FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not check_password_hash(user['password'], current_password):
        conn.close()
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('sec_admin_settings'))
    
    hashed_password = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Password changed successfully!', 'success')
    return redirect(url_for('sec_admin_settings'))

# ============================================================
# USER MANAGEMENT
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
    
    if new_role not in ALL_ROLES:
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

# ============================================================
# ADMIN MANAGEMENT
# ============================================================

@app.route('/admins')
def admin_management():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Please login as Head Admin.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT id, first_name, last_name, email, contact_number, address, role, is_verified, created_at 
        FROM users 
        WHERE role IN ('head_admin', 'admin_court_1', 'admin_court_2', 'admin_court_3', 'admin_court_4', 'admin_documents')
        ORDER BY role DESC, created_at DESC
    """)
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

@app.route('/create-admin', methods=['POST'])
def create_admin():
    if 'user_id' not in session or session.get('role') != 'head_admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'admin_court_1')
    
    if not first_name or not last_name or not email or not password:
        flash('Please fill in all fields.', 'danger')
        return redirect(url_for('admin_management'))
    
    if role not in ADMIN_ROLES:
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

@app.route('/api/user/<int:user_id>/update-role', methods=['POST'])
def api_update_user_role(user_id):
    if 'user_id' not in session or session.get('role') != 'head_admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    if user_id == session['user_id']:
        return jsonify({'error': 'You cannot change your own role'}), 400
    
    data = request.json
    new_role = data.get('role')
    
    if new_role not in ADMIN_ROLES:
        return jsonify({'error': 'Invalid role'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': f'Role updated to {new_role}'
    })

# ============================================================
# PROMOTE / DEMOTE ADMIN
# ============================================================

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
    
    if user['role'] in ADMIN_ROLES:
        conn.close()
        return jsonify({'error': 'User is already an admin'}), 400
    
    cursor.execute("UPDATE users SET role = 'admin_documents' WHERE id = %s", (user_id,))
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
    
    if user['role'] not in ADMIN_ROLES:
        conn.close()
        return jsonify({'error': 'User is not an admin'}), 400
    
    cursor.execute("UPDATE users SET role = 'resident' WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Admin demoted to Resident successfully'})

# ============================================================
# ANNOUNCEMENTS
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
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================
# USER ANNOUNCEMENTS
# ============================================================

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

# ============================================================
# API: UNREAD ANNOUNCEMENTS COUNT
# ============================================================

@app.route('/api/announcements/unread_count', methods=['GET'])
def api_unread_announcements_count():
    if 'user_id' not in session:
        return jsonify({'unread_count': 0})
    
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
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
# API: PERMITS
# ============================================================

@app.route('/api/permits', methods=['GET', 'POST'])
def api_permits():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'GET':
        cursor.execute("""
            SELECT * FROM event_permits 
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (session['user_id'],))
        permits = cursor.fetchall()
        conn.close()
        return jsonify(permits)
    
    if request.method == 'POST':
        data = request.json
        
        event_name = data.get('event_name', '').strip()
        purpose = data.get('purpose', '').strip()
        contact_person = data.get('contact_person', '').strip()
        contact_phone = data.get('contact_phone', '').strip()
        event_date = data.get('event_date', '').strip()
        start_time = data.get('start_time', '').strip()[:5]
        end_time = data.get('end_time', '').strip()[:5]
        venue = data.get('venue', '').strip()
        
        # Validation
        if not event_name or not event_date or not start_time or not end_time or not venue:
            conn.close()
            return jsonify({'error': 'Please fill in all required fields.'}), 400
        
        if not purpose:
            conn.close()
            return jsonify({'error': 'Purpose is required.'}), 400
        
        if not contact_person:
            conn.close()
            return jsonify({'error': 'Contact person is required.'}), 400
        
        if not contact_phone:
            conn.close()
            return jsonify({'error': 'Contact phone is required.'}), 400
        
        # HARD BLOCK: Approved conflicts
        cursor.execute("""
            SELECT id FROM event_permits 
            WHERE venue = %s 
              AND event_date = %s 
              AND status = 'approved'
              AND start_time < %s 
              AND end_time > %s
            LIMIT 1
        """, (venue, event_date, end_time, start_time))
        
        approved_conflict = cursor.fetchone()
        if approved_conflict:
            conn.close()
            return jsonify({'error': 'This time slot is already taken by an approved event at this venue.'}), 409
        
        ref_num = f"BP-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        queue_num = get_next_queue_number('event_permits')
        
        cursor.execute("""
            INSERT INTO event_permits (
                user_id, event_name, event_description, purpose, 
                contact_person, contact_phone,
                event_date, start_time, end_time, estimated_attendees, venue, 
                status, requirements_file, reference_number, queuing_number
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s)
        """, (
            session['user_id'],
            event_name,
            data.get('event_description', ''),
            purpose,
            contact_person,
            contact_phone,
            event_date,
            start_time,
            end_time,
            data.get('estimated_attendees', 0),
            venue,
            data.get('requirement', None),
            ref_num,
            queue_num
        ))
        conn.commit()
        permit_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type)
            VALUES (%s, %s, %s, 'permit_submitted')
        """, (
            session['user_id'],
            'Permit Application Submitted',
            f'Your event permit "{event_name}" has been submitted for review. Reference: {ref_num} | Queue: {queue_num}'
        ))
        conn.commit()
        
        conn.close()
        
        return jsonify({
            'message': 'Permit submitted successfully',
            'id': permit_id,
            'reference_number': ref_num,
            'queuing_number': queue_num
        }), 201

# ============================================================
# API: NOTIFICATIONS
# ============================================================

@app.route('/api/permits/notifications', methods=['GET'])
def api_notifications():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT * FROM notifications 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT 50
    """, (session['user_id'],))
    notifications = cursor.fetchall()
    conn.close()
    
    return jsonify(notifications)

@app.route('/api/permits/notifications/unread_count', methods=['GET'])
def api_unread_count():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT COUNT(*) as unread_count 
        FROM notifications 
        WHERE user_id = %s AND is_read = FALSE
    """, (session['user_id'],))
    result = cursor.fetchone()
    conn.close()
    
    return jsonify({'unread_count': result['unread_count']})

@app.route('/api/permits/notifications/<int:notif_id>/mark_read', methods=['POST'])
def api_mark_read(notif_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE notifications 
        SET is_read = TRUE 
        WHERE id = %s AND user_id = %s
    """, (notif_id, session['user_id']))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Marked as read'})

@app.route('/api/permits/notifications/mark_all_read', methods=['POST'])
def api_mark_all_read():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE notifications 
        SET is_read = TRUE 
        WHERE user_id = %s
    """, (session['user_id'],))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'All notifications marked as read'})

# ============================================================
# API: DOCUMENT REQUESTS
# ============================================================

@app.route('/api/document-requests')
def api_document_requests():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT * FROM document_requests 
        WHERE user_id = %s 
        ORDER BY created_at DESC
    """, (session['user_id'],))
    requests = cursor.fetchall()
    conn.close()
    
    return jsonify(requests)

# ============================================================
# SETTINGS (DUAL PURPOSE: HEAD ADMIN + RESIDENT)
# ============================================================
# ✨ ITO YUNG BINAGO — Ngayon, lahat ng roles (resident, admin, etc.)
#     ay makaka-access ng /settings. Pero:
#     - head_admin  → system settings (yung luma, may maintenance mode, backup, etc.)
#     - lahat ng iba → profile settings (Update Profile + Change Password)

@app.route('/settings')
def settings():
    if 'user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    
    role = session.get('role')
    
    # ========== HEAD ADMIN → System Settings (yung dating behavior) ==========
    if role == 'head_admin':
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
        
        return render_template('admin/settings.html', 
                             config=config,
                             maintenance_mode=maintenance_mode)
    
    # ========== RESIDENT / ADMIN / COURT ADMIN → Profile Settings ==========
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    return render_template('settings.html', user=user)

# ============================================================
# HEAD ADMIN SETTINGS HELPERS
# ============================================================

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
        return redirect(url_for('settings'))
    
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
    return redirect(url_for('settings'))

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
    return redirect(url_for('settings'))

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
    return redirect(url_for('settings'))

# ============================================================
# DATABASE BACKUP API
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
        return redirect(url_for('settings'))
    
    latest_backup = max(backup_files, key=os.path.getctime)
    
    return send_file(latest_backup, as_attachment=True, download_name=f"barangay_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.sql")

# ============================================================
# CHECK SESSION
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
        <a href="/sec-admin-dashboard">Documents Admin Dashboard</a><br>
        <a href="/court1/dashboard">Court 1 Dashboard</a><br>
        <a href="/court1/pending">Court 1 Pending</a><br>
        <a href="/court1/calendar">Court 1 Calendar</a><br>
        <a href="/court2/dashboard">Court 2 Dashboard</a><br>
        <a href="/court3/dashboard">Court 3 Dashboard</a><br>
        <a href="/court4/dashboard">Court 4 Dashboard</a><br>
        <a href="/dashboard">Resident Dashboard</a><br>
        <a href="/events-calendar">Events Calendar</a><br>
        <a href="/logout">Logout</a>
        """
    else:
        return "No active session. <a href='/login'>Login</a>"

# ============================================================
# LOGOUT
# ============================================================

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ============================================================
# FORGOT PASSWORD ROUTE
# ============================================================

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

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    app.run(debug=True)