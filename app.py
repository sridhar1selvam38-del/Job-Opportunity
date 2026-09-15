import os
import re
import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from db import query_db, execute_db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'jobpost-aggregator-secret-key-2026')

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max

def slugify(text):
    text = re.sub(r'[^\w\s-]', '', text.lower().strip())
    return re.sub(r'[-\s]+', '-', text)

# -------------------------------------------------------------
# AUTH & ACCESS CONTROL DECORATORS
# -------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to access this feature.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Admin access requires login.', 'warning')
            return redirect(url_for('login', next=request.url))
        if session.get('user_role') != 'ADMIN':
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# -------------------------------------------------------------
# CONTEXT PROCESSOR & COMMON HELPERS
# -------------------------------------------------------------
@app.context_processor
def inject_global_vars():
    unread_count = 0
    if session.get('user_id'):
        res = query_db(
            "SELECT COUNT(*) as cnt FROM notifications WHERE user_id = %s AND is_read = 0",
            (session['user_id'],), one=True
        )
        if res:
            unread_count = res['cnt']
    return {
        'unread_notifications': unread_count,
        'current_year': datetime.datetime.now().year
    }

def get_platform_stats():
    total_jobs = query_db("SELECT COUNT(*) as cnt FROM jobs WHERE status = 'ACTIVE'", one=True)['cnt']
    total_sources = query_db("SELECT COUNT(*) as cnt FROM job_sources WHERE is_active = 1", one=True)['cnt']
    total_companies = query_db("SELECT COUNT(*) as cnt FROM companies", one=True)['cnt']
    total_users = query_db("SELECT COUNT(*) as cnt FROM users", one=True)['cnt']
    return {
        'total_jobs': total_jobs,
        'total_sources': total_sources,
        'total_companies': total_companies,
        'total_users': total_users
    }

# -------------------------------------------------------------
# PUBLIC ROUTES
# -------------------------------------------------------------
@app.route('/')
def home():
    stats = get_platform_stats()
    
    # Featured jobs
    user_id = session.get('user_id')
    saved_ids = set()
    if user_id:
        saved_rows = query_db("SELECT job_id FROM saved_jobs WHERE user_id = %s", (user_id,))
        saved_ids = {r['job_id'] for r in saved_rows}

    sql_featured = """
        SELECT j.*, DATE(j.posted_at) as posted_date,
               c.name as company_name, c.logo_url as company_logo_url, c.slug as company_slug,
               s.name as source_name, s.code as source_code, cat.name as category_name
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        JOIN job_sources s ON j.source_id = s.id
        JOIN categories cat ON j.category_id = cat.id
        WHERE j.status = 'ACTIVE' AND j.is_featured = 1
        ORDER BY j.posted_at DESC
        LIMIT 6
    """
    featured_jobs = query_db(sql_featured)
    for job in featured_jobs:
        job['is_saved'] = job['id'] in saved_ids

    # Categories with count
    sql_cats = """
        SELECT cat.*, COUNT(j.id) as job_count
        FROM categories cat
        LEFT JOIN jobs j ON j.category_id = cat.id AND j.status = 'ACTIVE'
        GROUP BY cat.id
        ORDER BY cat.name ASC
    """
    categories = query_db(sql_cats)

    # Active sources with job counts
    sql_sources = """
        SELECT s.*, COUNT(j.id) as total_jobs_count
        FROM job_sources s
        LEFT JOIN jobs j ON j.source_id = s.id AND j.status = 'ACTIVE'
        WHERE s.is_active = 1
        GROUP BY s.id
        ORDER BY s.name ASC
    """
    sources = query_db(sql_sources)

    return render_template(
        'index.html',
        active_page='home',
        stats=stats,
        featured_jobs=featured_jobs,
        categories=categories,
        sources=sources
    )

@app.route('/jobs')
def jobs_list():
    q = request.args.get('q', '').strip()
    location = request.args.get('location', '').strip()
    category_slug = request.args.get('category', '').strip()
    source_code = request.args.get('source', '').strip()
    work_mode = request.args.get('work_mode', '').strip()
    experience = request.args.get('experience', '').strip()
    job_type = request.args.get('job_type', '').strip()
    sort_by = request.args.get('sort', 'newest').strip()

    # Record search history if user is logged in and keyword exists
    user_id = session.get('user_id')
    if user_id and q:
        execute_db(
            "INSERT INTO search_history (user_id, search_term, location) VALUES (%s, %s, %s)",
            (user_id, q, location or None)
        )

    # Base query
    sql = """
        SELECT j.*, DATE(j.posted_at) as posted_date,
               c.name as company_name, c.logo_url as company_logo_url, c.slug as company_slug,
               s.name as source_name, s.code as source_code, cat.name as category_name, cat.slug as category_slug
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        JOIN job_sources s ON j.source_id = s.id
        JOIN categories cat ON j.category_id = cat.id
        WHERE j.status = 'ACTIVE'
    """
    params = []

    if q:
        sql += " AND (j.title LIKE %s OR j.skills_required LIKE %s OR c.name LIKE %s OR j.description LIKE %s)"
        pattern = f"%{q}%"
        params.extend([pattern, pattern, pattern, pattern])

    if location:
        sql += " AND (j.location LIKE %s)"
        params.append(f"%{location}%")

    if category_slug:
        sql += " AND cat.slug = %s"
        params.append(category_slug)

    if source_code:
        sql += " AND s.code = %s"
        params.append(source_code)

    if work_mode:
        sql += " AND j.work_mode = %s"
        params.append(work_mode)

    if experience:
        sql += " AND j.experience_level = %s"
        params.append(experience)

    if job_type:
        sql += " AND j.job_type = %s"
        params.append(job_type)

    if sort_by == 'salary_high':
        sql += " ORDER BY j.salary_max DESC, j.salary_min DESC"
    elif sort_by == 'popular':
        sql += " ORDER BY j.views_count DESC, j.posted_at DESC"
    else:
        sql += " ORDER BY j.posted_at DESC"

    jobs = query_db(sql, params)

    # Saved jobs mapping
    saved_ids = set()
    if user_id:
        saved_rows = query_db("SELECT job_id FROM saved_jobs WHERE user_id = %s", (user_id,))
        saved_ids = {r['job_id'] for r in saved_rows}

    for j in jobs:
        j['is_saved'] = j['id'] in saved_ids

    # Categories with count
    sql_cats = """
        SELECT cat.*, COUNT(j.id) as job_count
        FROM categories cat
        LEFT JOIN jobs j ON j.category_id = cat.id AND j.status = 'ACTIVE'
        GROUP BY cat.id
        ORDER BY cat.name ASC
    """
    categories = query_db(sql_cats)

    # Active sources with job counts
    sql_sources = """
        SELECT s.*, COUNT(j.id) as total_jobs_count
        FROM job_sources s
        LEFT JOIN jobs j ON j.source_id = s.id AND j.status = 'ACTIVE'
        WHERE s.is_active = 1
        GROUP BY s.id
        ORDER BY s.name ASC
    """
    sources = query_db(sql_sources)

    # Search history for current user
    search_history = []
    if user_id:
        search_history = query_db(
            "SELECT DISTINCT search_term, location FROM search_history WHERE user_id = %s ORDER BY created_at DESC LIMIT 6",
            (user_id,)
        )

    current_filters = {
        'q': q,
        'location': location,
        'category': category_slug,
        'source': source_code,
        'work_mode': work_mode,
        'experience': experience,
        'job_type': job_type,
        'sort': sort_by
    }

    return render_template(
        'jobs.html',
        active_page='jobs',
        jobs=jobs,
        categories=categories,
        sources=sources,
        current_filters=current_filters,
        search_history=search_history
    )

@app.route('/job/<int:job_id>')
def job_detail(job_id):
    # Increment view counter
    execute_db("UPDATE jobs SET views_count = views_count + 1 WHERE id = %s", (job_id,))

    sql = """
        SELECT j.*, DATE(j.posted_at) as posted_date,
               c.name as company_name, c.description as company_description,
               c.logo_url as company_logo_url, c.website as company_website,
               c.location as company_location, c.company_size, c.industry as company_industry,
               c.rating as company_rating, c.slug as company_slug,
               s.name as source_name, s.code as source_code, s.base_url as source_base_url,
               cat.name as category_name, cat.slug as category_slug
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        JOIN job_sources s ON j.source_id = s.id
        JOIN categories cat ON j.category_id = cat.id
        WHERE j.id = %s
    """
    job = query_db(sql, (job_id,), one=True)
    if not job:
        flash('The requested job posting was not found or has been removed.', 'danger')
        return redirect(url_for('jobs_list'))

    # Check saved status
    user_id = session.get('user_id')
    is_saved = False
    user_application = None

    if user_id:
        saved = query_db("SELECT id FROM saved_jobs WHERE user_id = %s AND job_id = %s", (user_id, job_id), one=True)
        is_saved = bool(saved)
        user_application = query_db(
            "SELECT * FROM job_applications WHERE user_id = %s AND job_id = %s",
            (user_id, job_id), one=True
        )

    # Check for duplicate clustered jobs from other sources
    duplicate_sources = []
    if job['duplicate_cluster_id']:
        sql_dups = """
            SELECT j.id, j.title, s.name as source_name, s.code as source_code, DATE(j.posted_at) as posted_date
            FROM jobs j
            JOIN job_sources s ON j.source_id = s.id
            WHERE j.duplicate_cluster_id = %s AND j.id != %s AND j.status = 'ACTIVE'
        """
        duplicate_sources = query_db(sql_dups, (job['duplicate_cluster_id'], job_id))

    return render_template(
        'job_detail.html',
        active_page='jobs',
        job=job,
        is_saved=is_saved,
        user_application=user_application,
        duplicate_sources=duplicate_sources
    )

# -------------------------------------------------------------
# CURATED PORTALS (INTERNSHIPS, FRESHER, REMOTE, COMPANIES)
# -------------------------------------------------------------
@app.route('/internships')
def internships():
    sql = """
        SELECT j.*, DATE(j.posted_at) as posted_date,
               c.name as company_name, c.logo_url as company_logo_url, c.slug as company_slug,
               s.name as source_name, s.code as source_code
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        JOIN job_sources s ON j.source_id = s.id
        WHERE j.status = 'ACTIVE' AND (j.is_internship = 1 OR j.job_type = 'Internship')
        ORDER BY j.posted_at DESC
    """
    jobs = query_db(sql)
    return render_template('internships.html', active_page='internships', jobs=jobs)

@app.route('/fresher')
def fresher_jobs():
    sql = """
        SELECT j.*, DATE(j.posted_at) as posted_date,
               c.name as company_name, c.logo_url as company_logo_url, c.slug as company_slug,
               s.name as source_name, s.code as source_code
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        JOIN job_sources s ON j.source_id = s.id
        WHERE j.status = 'ACTIVE' AND (j.is_fresher = 1 OR j.experience_level = 'Fresher')
        ORDER BY j.posted_at DESC
    """
    jobs = query_db(sql)
    return render_template('fresher_jobs.html', active_page='fresher', jobs=jobs)

@app.route('/remote')
def remote_jobs():
    sql = """
        SELECT j.*, DATE(j.posted_at) as posted_date,
               c.name as company_name, c.logo_url as company_logo_url, c.slug as company_slug,
               s.name as source_name, s.code as source_code
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        JOIN job_sources s ON j.source_id = s.id
        WHERE j.status = 'ACTIVE' AND (j.is_remote = 1 OR j.work_mode = 'Remote')
        ORDER BY j.posted_at DESC
    """
    jobs = query_db(sql)
    return render_template('remote_jobs.html', active_page='remote', jobs=jobs)

@app.route('/companies')
def companies_directory():
    sql = """
        SELECT c.*, COUNT(j.id) as active_jobs_count
        FROM companies c
        LEFT JOIN jobs j ON j.company_id = c.id AND j.status = 'ACTIVE'
        GROUP BY c.id
        ORDER BY c.name ASC
    """
    companies = query_db(sql)
    return render_template('companies.html', active_page='companies', companies=companies)

@app.route('/company/<slug>')
def company_detail(slug):
    company = query_db("SELECT * FROM companies WHERE slug = %s", (slug,), one=True)
    if not company:
        flash('Company profile not found.', 'danger')
        return redirect(url_for('companies_directory'))

    sql_jobs = """
        SELECT j.*, DATE(j.posted_at) as posted_date, s.name as source_name, s.code as source_code
        FROM jobs j
        JOIN job_sources s ON j.source_id = s.id
        WHERE j.company_id = %s AND j.status = 'ACTIVE'
        ORDER BY j.posted_at DESC
    """
    jobs = query_db(sql_jobs, (company['id'],))
    return render_template('company_detail.html', active_page='companies', company=company, jobs=jobs)

@app.route('/about')
def about():
    return render_template('about.html', active_page='about')

# -------------------------------------------------------------
# AUTHENTICATION (LOGIN / REGISTER / LOGOUT)
# -------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        next_url = request.form.get('next', '').strip()

        user = query_db("SELECT * FROM users WHERE email = %s", (email,), one=True)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            session['user_email'] = user['email']
            session['user_role'] = user['role']
            flash(f"Welcome back, {user['full_name']}!", 'success')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(url_for('admin_panel' if user['role'] == 'ADMIN' else 'dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('auth.html', mode='login', next=request.args.get('next', ''))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        location = request.form.get('location', '').strip()
        experience_level = request.form.get('experience_level', 'Fresher').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        admin_code = request.form.get('admin_code', '').strip()

        if not full_name or not email or not password:
            flash('All required fields must be completed.', 'danger')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))

        existing = query_db("SELECT id FROM users WHERE email = %s", (email,), one=True)
        if existing:
            flash('An account with this email address already exists. Please log in.', 'warning')
            return redirect(url_for('login'))

        role = 'ADMIN' if admin_code == 'admin123' else 'USER'
        hashed = generate_password_hash(password)

        new_user_id = execute_db("""
            INSERT INTO users (full_name, email, password_hash, phone, location, experience_level, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (full_name, email, hashed, phone or None, location, experience_level, role))

        # Welcome notification
        execute_db("""
            INSERT INTO notifications (user_id, title, message, link)
            VALUES (%s, %s, %s, %s)
        """, (
            new_user_id,
            'Welcome to JobPost Aggregator!',
            'Discover verified job opportunities from multiple authorized feeds in one place.',
            '/jobs'
        ))

        session['user_id'] = new_user_id
        session['user_name'] = full_name
        session['user_email'] = email
        session['user_role'] = role

        flash(f"Account registered successfully as {role}! Welcome to JobPost Aggregator.", 'success')
        return redirect(url_for('admin_panel' if role == 'ADMIN' else 'dashboard'))

    return render_template('auth.html', mode='register')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been safely logged out.', 'info')
    return redirect(url_for('home'))

# -------------------------------------------------------------
# USER DASHBOARD & TRACKING
# -------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    user = query_db("SELECT * FROM users WHERE id = %s", (user_id,), one=True)

    # 1. Applications Pipeline
    sql_apps = """
        SELECT ja.*, DATE(ja.applied_at) as applied_date,
               j.title as job_title, c.name as company_name, j.location, s.name as source_name
        FROM job_applications ja
        JOIN jobs j ON ja.job_id = j.id
        JOIN companies c ON j.company_id = c.id
        JOIN job_sources s ON j.source_id = s.id
        WHERE ja.user_id = %s
        ORDER BY ja.applied_at DESC
    """
    applications = query_db(sql_apps, (user_id,))
    pipeline = {
        'Applied': [a for a in applications if a['status'] == 'Applied'],
        'Reviewing': [a for a in applications if a['status'] == 'Reviewing'],
        'Interviewing': [a for a in applications if a['status'] == 'Interviewing'],
        'Offered': [a for a in applications if a['status'] == 'Offered'],
        'Rejected': [a for a in applications if a['status'] == 'Rejected']
    }

    # 2. Saved Jobs
    sql_saved = """
        SELECT sj.*, j.title, j.location, j.job_type, j.salary_min, j.salary_max,
               c.name as company_name, c.slug as company_slug, s.name as source_name, s.code as source_code
        FROM saved_jobs sj
        JOIN jobs j ON sj.job_id = j.id
        JOIN companies c ON j.company_id = c.id
        JOIN job_sources s ON j.source_id = s.id
        WHERE sj.user_id = %s
        ORDER BY sj.created_at DESC
    """
    saved_jobs = query_db(sql_saved, (user_id,))

    # 3. Job Alerts
    alerts = query_db("SELECT * FROM job_alerts WHERE user_id = %s ORDER BY created_at DESC", (user_id,))

    # 4. Notifications
    notifications = query_db("SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC LIMIT 20", (user_id,))

    # 5. Search History
    search_history = query_db("SELECT * FROM search_history WHERE user_id = %s ORDER BY created_at DESC LIMIT 15", (user_id,))

    return render_template(
        'dashboard.html',
        active_page='dashboard',
        user=user,
        applications=applications,
        pipeline=pipeline,
        saved_jobs=saved_jobs,
        alerts=alerts,
        notifications=notifications,
        search_history=search_history
    )

@app.route('/dashboard/profile', methods=['POST'])
@login_required
def update_profile():
    user_id = session['user_id']
    full_name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    location = request.form.get('location', '').strip()
    experience_level = request.form.get('experience_level', 'Fresher').strip()
    headline = request.form.get('headline', '').strip()
    skills = request.form.get('skills', '').strip()
    bio = request.form.get('bio', '').strip()

    resume_filename = None
    if 'resume' in request.files:
        file = request.files['resume']
        if file and file.filename != '':
            filename = secure_filename(f"user_{user_id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            resume_filename = filename

    if resume_filename:
        execute_db("""
            UPDATE users 
            SET full_name=%s, phone=%s, location=%s, experience_level=%s, headline=%s, skills=%s, bio=%s, resume_url=%s
            WHERE id=%s
        """, (full_name, phone, location, experience_level, headline, skills, bio, resume_filename, user_id))
    else:
        execute_db("""
            UPDATE users 
            SET full_name=%s, phone=%s, location=%s, experience_level=%s, headline=%s, skills=%s, bio=%s
            WHERE id=%s
        """, (full_name, phone, location, experience_level, headline, skills, bio, user_id))

    session['user_name'] = full_name
    flash('Profile and resume updated successfully.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/dashboard/alerts/create', methods=['POST'])
@login_required
def create_alert():
    user_id = session['user_id']
    title = request.form.get('title', '').strip()
    keyword = request.form.get('keyword', '').strip()
    location = request.form.get('location', '').strip()
    frequency = request.form.get('frequency', 'Daily').strip()

    if not title:
        flash('Please provide an alert name.', 'danger')
        return redirect(url_for('dashboard'))

    execute_db("""
        INSERT INTO job_alerts (user_id, title, keyword, location, frequency)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, title, keyword or None, location or None, frequency))

    flash(f"Job alert '{title}' created successfully!", 'success')
    return redirect(url_for('dashboard'))

@app.route('/dashboard/alerts/delete', methods=['POST'])
@login_required
def delete_alert():
    user_id = session['user_id']
    alert_id = request.form.get('alert_id')
    execute_db("DELETE FROM job_alerts WHERE id = %s AND user_id = %s", (alert_id, user_id))
    flash('Job alert removed.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/dashboard/history/clear', methods=['POST'])
@login_required
def clear_search_history():
    user_id = session['user_id']
    execute_db("DELETE FROM search_history WHERE user_id = %s", (user_id,))
    flash('Recent search history cleared.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/dashboard/notifications/read-all', methods=['POST'])
@login_required
def mark_notifications_read():
    user_id = session['user_id']
    execute_db("UPDATE notifications SET is_read = 1 WHERE user_id = %s", (user_id,))
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('dashboard'))

# -------------------------------------------------------------
# RESTFUL JSON API ENDPOINTS (FOR CLIENT JAVASCRIPT)
# -------------------------------------------------------------
@app.route('/api/jobs/<int:job_id>/save', methods=['POST'])
def api_toggle_save(job_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Login required'}), 401

    existing = query_db("SELECT id FROM saved_jobs WHERE user_id = %s AND job_id = %s", (user_id, job_id), one=True)
    if existing:
        execute_db("DELETE FROM saved_jobs WHERE id = %s", (existing['id'],))
        return jsonify({'saved': False, 'message': 'Removed from saved jobs'})
    else:
        execute_db("INSERT INTO saved_jobs (user_id, job_id) VALUES (%s, %s)", (user_id, job_id))
        return jsonify({'saved': True, 'message': 'Saved to bookmarks'})

@app.route('/api/jobs/<int:job_id>/track', methods=['POST'])
def api_track_application(job_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Login required'}), 401

    data = request.get_json() or {}
    status = data.get('status', 'Applied')
    notes = data.get('notes', '')

    existing = query_db("SELECT id FROM job_applications WHERE user_id = %s AND job_id = %s", (user_id, job_id), one=True)
    if existing:
        execute_db("""
            UPDATE job_applications 
            SET status = %s, notes = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (status, notes, existing['id']))
    else:
        execute_db("""
            INSERT INTO job_applications (user_id, job_id, status, notes)
            VALUES (%s, %s, %s, %s)
        """, (user_id, job_id, status, notes))

    return jsonify({'success': True, 'status': status})

@app.route('/api/jobs/<int:job_id>/report', methods=['POST'])
def api_report_job(job_id):
    user_id = session.get('user_id')
    data = request.get_json() or {}
    reason = data.get('reason', 'Other')
    details = data.get('details', '')

    execute_db("""
        INSERT INTO job_reports (job_id, user_id, reason, details)
        VALUES (%s, %s, %s, %s)
    """, (job_id, user_id or None, reason, details))

    return jsonify({'success': True, 'message': 'Report received'})

# -------------------------------------------------------------
# ADMIN CONSOLE & ACTIONS
# -------------------------------------------------------------
@app.route('/admin')
@admin_required
def admin_panel():
    stats = get_platform_stats()

    # All sources
    sources = query_db("""
        SELECT s.*, COUNT(j.id) as total_jobs_count
        FROM job_sources s
        LEFT JOIN jobs j ON j.source_id = s.id
        GROUP BY s.id
        ORDER BY s.id ASC
    """)

    # All jobs
    jobs = query_db("""
        SELECT j.*, DATE(j.posted_at) as posted_date,
               c.name as company_name, s.name as source_name, s.code as source_code
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        JOIN job_sources s ON j.source_id = s.id
        ORDER BY j.id DESC
        LIMIT 100
    """)

    # Duplicate clusters
    duplicates = query_db("""
        SELECT j.*, DATE(j.posted_at) as posted_date,
               c.name as company_name, s.name as source_name, s.code as source_code
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        JOIN job_sources s ON j.source_id = s.id
        WHERE j.duplicate_cluster_id IS NOT NULL AND j.status = 'ACTIVE'
        ORDER BY j.duplicate_cluster_id, j.id
    """)

    # User reports
    reports = query_db("""
        SELECT jr.*, j.title as job_title, u.full_name as reporter_name
        FROM job_reports jr
        JOIN jobs j ON jr.job_id = j.id
        LEFT JOIN users u ON jr.user_id = u.id
        ORDER BY jr.created_at DESC
    """)

    # Companies and Categories for dropdowns
    companies = query_db("SELECT * FROM companies ORDER BY name ASC")
    categories = query_db("SELECT * FROM categories ORDER BY name ASC")

    # Harvest logs
    sync_logs = query_db("""
        SELECT sl.*, s.name as source_name
        FROM sync_logs sl
        JOIN job_sources s ON sl.source_id = s.id
        ORDER BY sl.synced_at DESC
        LIMIT 10
    """)

    return render_template(
        'admin.html',
        active_page='admin',
        stats=stats,
        sources=sources,
        jobs=jobs,
        duplicates=duplicates,
        reports=reports,
        companies=companies,
        categories=categories,
        sync_logs=sync_logs
    )

@app.route('/admin/jobs/add', methods=['POST'])
@admin_required
def admin_add_job():
    title = request.form.get('title', '').strip()
    company_id = request.form.get('company_id')
    category_id = request.form.get('category_id')
    source_id = request.form.get('source_id')
    job_type = request.form.get('job_type', 'Full-time')
    work_mode = request.form.get('work_mode', 'Remote')
    location = request.form.get('location', 'Remote')
    salary_min = request.form.get('salary_min') or None
    salary_max = request.form.get('salary_max') or None
    experience_level = request.form.get('experience_level', '3-5 years')
    original_url = request.form.get('original_url')
    description = request.form.get('description', '')
    skills_required = request.form.get('skills_required', '')
    is_featured = 1 if request.form.get('is_featured') else 0
    is_remote = 1 if work_mode == 'Remote' else 0
    is_internship = 1 if (request.form.get('is_internship') or job_type == 'Internship') else 0
    is_fresher = 1 if (request.form.get('is_fresher') or experience_level == 'Fresher') else 0

    slug = slugify(f"{title}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")

    execute_db("""
        INSERT INTO jobs (
            title, slug, company_id, category_id, source_id, job_type, work_mode, location,
            salary_min, salary_max, experience_level, original_url, description,
            skills_required, is_featured, is_remote, is_internship, is_fresher, posted_at, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 'ACTIVE')
    """, (
        title, slug, company_id, category_id, source_id, job_type, work_mode, location,
        salary_min, salary_max, experience_level, original_url, description,
        skills_required, is_featured, is_remote, is_internship, is_fresher
    ))

    flash(f"Job '{title}' published directly to aggregator index!", 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/jobs/delete', methods=['POST'])
@admin_required
def admin_delete_job():
    job_id = request.form.get('job_id')
    execute_db("DELETE FROM jobs WHERE id = %s", (job_id,))
    flash(f"Job #{job_id} deleted.", 'info')
    return redirect(url_for('admin_panel'))

@app.route('/admin/sources/toggle', methods=['POST'])
@admin_required
def admin_toggle_source():
    source_id = request.form.get('source_id')
    src = query_db("SELECT is_active, name FROM job_sources WHERE id = %s", (source_id,), one=True)
    if src:
        new_state = 0 if src['is_active'] else 1
        execute_db("UPDATE job_sources SET is_active = %s WHERE id = %s", (new_state, source_id))
        flash(f"Source '{src['name']}' {'enabled' if new_state else 'disabled'}.", 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/sources/add', methods=['POST'])
@admin_required
def admin_add_source():
    name = request.form.get('name', '').strip()
    code = request.form.get('code', '').strip().lower()
    base_url = request.form.get('base_url', '').strip()
    color_hex = request.form.get('color_hex', '#2563eb').strip()

    if name and code and base_url:
        execute_db("""
            INSERT INTO job_sources (name, code, base_url, color_hex, is_active)
            VALUES (%s, %s, %s, %s, 1)
        """, (name, code, base_url, color_hex))
        flash(f"Source '{name}' added successfully.", 'success')
    else:
        flash('All fields are required to register a source.', 'danger')
    return redirect(url_for('admin_panel'))

@app.route('/admin/reports/resolve', methods=['POST'])
@admin_required
def admin_resolve_report():
    report_id = request.form.get('report_id')
    action = request.form.get('action')  # 'resolve' or 'delete_job'

    rep = query_db("SELECT job_id FROM job_reports WHERE id = %s", (report_id,), one=True)
    if rep and action == 'delete_job':
        execute_db("DELETE FROM jobs WHERE id = %s", (rep['job_id'],))
        execute_db("UPDATE job_reports SET status = 'Action_Taken' WHERE id = %s", (report_id,))
        flash(f"Job #{rep['job_id']} deleted and report marked as Action Taken.", 'success')
    elif rep:
        execute_db("UPDATE job_reports SET status = 'Dismissed' WHERE id = %s", (report_id,))
        flash("Report dismissed.", 'info')

    return redirect(url_for('admin_panel'))

@app.route('/api/admin/jobs/<int:job_id>', methods=['DELETE'])
@admin_required
def api_admin_delete_job(job_id):
    execute_db("DELETE FROM jobs WHERE id = %s", (job_id,))
    return jsonify({'success': True, 'message': 'Job deleted successfully'})

@app.route('/api/admin/clean-expired', methods=['POST'])
@admin_required
def api_clean_expired():
    # Find active jobs whose expires_at is before today
    count = execute_db("""
        UPDATE jobs 
        SET status = 'EXPIRED' 
        WHERE status = 'ACTIVE' AND expires_at IS NOT NULL AND expires_at < CURRENT_DATE
    """)
    return jsonify({'success': True, 'expired_count': count or 0})

@app.route('/api/admin/sync-sources', methods=['POST'])
@admin_required
def api_sync_sources():
    sources = query_db("SELECT * FROM job_sources WHERE is_active = 1")
    new_jobs_added = 0
    duplicates_found = 0

    sample_feed_harvest = [
        {
            'source_code': 'remotehub',
            'title': 'Senior Python Backend Architect',
            'company_slug': 'cloudscale-labs',
            'category_slug': 'software-engineering',
            'job_type': 'Full-time',
            'work_mode': 'Remote',
            'location': 'Remote (Global)',
            'salary_min': 155000,
            'salary_max': 195000,
            'experience_level': '5+ years',
            'original_url': 'https://remotehub.io/jobs/cloudscale-python-architect-2026',
            'description': 'Design distributed microservices, asynchronous task pipelines with Celery and Redis, and real-time streaming architectures with high reliability.',
            'skills': 'Python, Flask, FastApi, PostgreSQL, Redis, Kubernetes, Docker',
            'is_remote': 1,
            'is_internship': 0,
            'is_fresher': 0,
            'duplicate_cluster_id': None
        },
        {
            'source_code': 'campushire',
            'title': 'Junior Full Stack Developer',
            'company_slug': 'pixelcraft',
            'category_slug': 'web-development',
            'job_type': 'Full-time',
            'work_mode': 'Hybrid',
            'location': 'Seattle, WA',
            'salary_min': 78000,
            'salary_max': 92000,
            'experience_level': 'Fresher',
            'original_url': 'https://campushire.com/jobs/pixelcraft-junior-fullstack',
            'description': 'Ideal for recent Computer Science graduates wanting hands-on web application development with modern HTML5, CSS3, JavaScript, and Python backend services.',
            'skills': 'JavaScript, HTML5, CSS, Python, Git, SQL',
            'is_remote': 0,
            'is_internship': 0,
            'is_fresher': 1,
            'duplicate_cluster_id': None
        }
    ]

    for item in sample_feed_harvest:
        src = next((s for s in sources if s['code'] == item['source_code']), None)
        if not src:
            continue
        comp = query_db("SELECT id FROM companies WHERE slug = %s", (item['company_slug'],), one=True)
        cat = query_db("SELECT id FROM categories WHERE slug = %s", (item['category_slug'],), one=True)
        if not comp or not cat:
            continue

        exists = query_db(
            "SELECT id FROM jobs WHERE title = %s AND company_id = %s",
            (item['title'], comp['id']), one=True
        )
        if not exists:
            job_slug = slugify(f"{item['title']}-{comp['id']}-{int(datetime.datetime.now().timestamp())}")
            execute_db("""
                INSERT INTO jobs (
                    title, slug, company_id, category_id, source_id, job_type, work_mode, location,
                    salary_min, salary_max, experience_level, original_url, description,
                    skills_required, is_remote, is_internship, is_fresher, posted_at, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 'ACTIVE')
            """, (
                item['title'], job_slug, comp['id'], cat['id'], src['id'], item['job_type'],
                item['work_mode'], item['location'], item['salary_min'], item['salary_max'],
                item['experience_level'], item['original_url'], item['description'],
                item['skills'], item['is_remote'], item['is_internship'], item['is_fresher']
            ))
            new_jobs_added += 1

    # Update last_synced_at on sources and write sync logs
    for s in sources:
        execute_db("UPDATE job_sources SET last_synced_at = CURRENT_TIMESTAMP WHERE id = %s", (s['id'],))
        execute_db("""
            INSERT INTO sync_logs (source_id, status, jobs_fetched, new_jobs_added, duplicates_detected)
            VALUES (%s, 'SUCCESS', 2, %s, %s)
        """, (s['id'], new_jobs_added, duplicates_found))

    return jsonify({
        'success': True,
        'new_jobs': new_jobs_added,
        'duplicates': duplicates_found
    })

# -------------------------------------------------------------
# RUN SERVER
# -------------------------------------------------------------
if __name__ == '__main__':
    print("=========================================================")
    print(" JOBPOST AGGREGATOR - Smart Career Discovery System")
    print(" Tagline: 'Search. Discover. Apply.'")
    print(" Server running on port 3000 (Python 3 / Flask / MySQL)")
    print("=========================================================")
    app.run(host='0.0.0.0', port=3000, debug=True)
