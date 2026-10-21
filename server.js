import express from 'express';
import nunjucks from 'nunjucks';
import cookieParser from 'cookie-parser';
import multer from 'multer';
import crypto from 'crypto';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { DatabaseSync } from 'node:sqlite';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = parseInt(process.env.PORT || '3000', 10);

// Ensure directories exist
const uploadsDir = path.join(__dirname, 'static', 'uploads');
if (!fs.existsSync(uploadsDir)) {
  fs.mkdirSync(uploadsDir, { recursive: true });
}

// Database Connection
const sqlitePath = path.join(__dirname, 'jobpost_aggregator.sqlite');
const db = new DatabaseSync(sqlitePath);

function queryAll(sql, params = []) {
  try {
    const stmt = db.prepare(sql);
    return stmt.all(...params);
  } catch (err) {
    console.error('[DB Query Error]', err.message, 'SQL:', sql);
    return [];
  }
}

function queryOne(sql, params = []) {
  try {
    const stmt = db.prepare(sql);
    return stmt.get(...params) || null;
  } catch (err) {
    console.error('[DB QueryOne Error]', err.message, 'SQL:', sql);
    return null;
  }
}

function execute(sql, params = []) {
  try {
    const stmt = db.prepare(sql);
    return stmt.run(...params);
  } catch (err) {
    console.error('[DB Execute Error]', err.message, 'SQL:', sql);
    return { changes: 0, lastInsertRowid: 0 };
  }
}

// Password Helpers (100% compatible with PBKDF2 Werkzeug hashes)
function hashPassword(password) {
  const salt = crypto.randomBytes(8).toString('hex');
  const derived = crypto.pbkdf2Sync(password, salt, 260000, 32, 'sha256').toString('hex');
  return `pbkdf2:sha256:260000$${salt}$${derived}`;
}

function checkPassword(password, hash) {
  if (!hash || !password) return false;
  if (hash.startsWith('pbkdf2:sha256:')) {
    const parts = hash.split('$');
    if (parts.length >= 3) {
      const iterations = parseInt(parts[0].split(':')[2], 10) || 260000;
      const salt = parts[1];
      const key = parts[2];
      const derived = crypto.pbkdf2Sync(password, salt, iterations, 32, 'sha256').toString('hex');
      return derived === key;
    }
  }
  return false;
}

function slugify(text) {
  if (!text) return '';
  return text.toLowerCase().trim().replace(/[^\w\s-]/g, '').replace(/[-\s]+/g, '-');
}

// Polyfill String.prototype.format for Python-style "{:,}".format(val) in Jinja templates
if (!String.prototype.format) {
  String.prototype.format = function (...args) {
    if (this == '{:,}') {
      const n = Number(args[0]) || 0;
      return n.toLocaleString('en-US');
    }
    return this.replace(/{(\d+)?}/g, (match, number) => {
      return typeof args[number] !== 'undefined' ? args[number] : match;
    });
  };
}

// Template Engine Setup (Nunjucks for Jinja2 compatibility)
const nunjucksEnv = nunjucks.configure(path.join(__dirname, 'templates'), {
  autoescape: true,
  express: app,
  noCache: process.env.NODE_ENV !== 'production'
});

// Configure Nunjucks filters
nunjucksEnv.addFilter('split', (str, separator) => {
  if (!str) return [];
  return String(str).split(separator || ' ');
});

// Upload configuration
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadsDir),
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname);
    const unique = `${Date.now()}_${Math.random().toString(36).substring(2, 9)}${ext}`;
    cb(null, unique);
  }
});
const upload = multer({
  storage,
  limits: { fileSize: 16 * 1024 * 1024 }
});

// Middleware
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(cookieParser('jobpost-secret-key-2026'));
app.use('/static', express.static(path.join(__dirname, 'static')));
app.use('/uploads', express.static(uploadsDir));

// Session handling with signed cookies
app.use((req, res, next) => {
  let sessionData = {};
  try {
    if (req.signedCookies.jp_session) {
      sessionData = JSON.parse(req.signedCookies.jp_session);
    }
  } catch (e) {
    sessionData = {};
  }

  req.session = sessionData;
  if (!req.session.flashes) req.session.flashes = [];

  req.flash = (category, message) => {
    req.session.flashes.push([category, message]);
  };

  const originalSend = res.send;
  res.send = function (data) {
    try {
      res.cookie('jp_session', JSON.stringify(req.session), {
        signed: true,
        httpOnly: true,
        sameSite: 'none',
        secure: true,
        maxAge: 7 * 24 * 60 * 60 * 1000
      });
    } catch (e) {
      // ignore
    }
    return originalSend.apply(this, arguments);
  };

  const flashesToDisplay = [...req.session.flashes];
  req.session.flashes = [];

  res.locals.get_flashed_messages = (opts) => flashesToDisplay;
  res.locals.session = {
    ...req.session,
    get: function (k, def) {
      return this[k] !== undefined && this[k] !== null ? this[k] : def;
    }
  };
  res.locals.request = {
    path: req.path,
    args: req.query
  };

  next();
});

// Auth Guard Helpers
function loginRequired(req, res, next) {
  if (!req.session.user_id) {
    req.flash('warning', 'Please log in to access this feature.');
    return res.redirect(`/login?next=${encodeURIComponent(req.originalUrl)}`);
  }
  next();
}

function adminRequired(req, res, next) {
  if (!req.session.user_id) {
    req.flash('warning', 'Admin access requires login.');
    return res.redirect(`/login?next=${encodeURIComponent(req.originalUrl)}`);
  }
  if (req.session.user_role !== 'ADMIN') {
    req.flash('danger', 'Access denied. Administrator privileges required.');
    return res.redirect('/dashboard');
  }
  next();
}

// -------------------------------------------------------------
// ROUTES
// -------------------------------------------------------------

// Home Page
app.get('/', (req, res) => {
  const categories = queryAll('SELECT * FROM categories ORDER BY name');
  const companies = queryAll('SELECT * FROM companies ORDER BY name LIMIT 12');
  const featuredJobs = queryAll(`
    SELECT j.*, c.name as company_name, c.logo_url as company_logo, cat.name as category_name
    FROM jobs j
    JOIN companies c ON j.company_id = c.id
    JOIN categories cat ON j.category_id = cat.id
    WHERE j.status = 'ACTIVE'
    ORDER BY j.is_featured DESC, j.created_at DESC
    LIMIT 6
  `);

  const totalJobs = queryOne("SELECT COUNT(*) as count FROM jobs WHERE status = 'ACTIVE'")?.count || 0;
  const companiesCount = queryOne('SELECT COUNT(*) as count FROM companies')?.count || 0;
  const categoriesCount = queryOne('SELECT COUNT(*) as count FROM categories')?.count || 0;
  const sourcesCount = queryOne("SELECT COUNT(*) as count FROM job_sources WHERE is_active = 1")?.count || 0;

  let savedJobIds = [];
  if (req.session.user_id) {
    const bookmarks = queryAll('SELECT job_id FROM saved_jobs WHERE user_id = ?', [req.session.user_id]);
    savedJobIds = bookmarks.map(b => b.job_id);
  }

  res.render('index.html', {
    categories,
    companies,
    featured_jobs: featuredJobs,
    total_jobs: totalJobs,
    companies_count: companiesCount,
    categories_count: categoriesCount,
    sources_count: sourcesCount,
    saved_job_ids: savedJobIds
  });
});

// Jobs Search & Filter
app.get('/jobs', (req, res) => {
  const q = (req.query.q || '').trim();
  const location = (req.query.location || '').trim();
  const jobType = (req.query.type || '').trim();
  const expLevel = (req.query.level || '').trim();
  const workMode = (req.query.mode || '').trim();
  const categoryId = (req.query.cat || '').trim();
  const page = Math.max(1, parseInt(req.query.page || '1', 10));
  const perPage = 10;
  const offset = (page - 1) * perPage;

  let sql = `
    SELECT j.*, c.name as company_name, c.logo_url as company_logo, cat.name as category_name
    FROM jobs j
    JOIN companies c ON j.company_id = c.id
    JOIN categories cat ON j.category_id = cat.id
    WHERE j.status = 'ACTIVE'
  `;
  const params = [];

  if (q) {
    sql += ` AND (j.title LIKE ? OR j.description LIKE ? OR j.skills_required LIKE ? OR c.name LIKE ?)`;
    const term = `%${q}%`;
    params.push(term, term, term, term);
  }
  if (location) {
    sql += ` AND j.location LIKE ?`;
    params.push(`%${location}%`);
  }
  if (jobType) {
    sql += ` AND j.job_type = ?`;
    params.push(jobType);
  }
  if (expLevel) {
    sql += ` AND j.experience_level = ?`;
    params.push(expLevel);
  }
  if (workMode) {
    sql += ` AND j.work_mode = ?`;
    params.push(workMode);
  }
  if (categoryId) {
    sql += ` AND j.category_id = ?`;
    params.push(parseInt(categoryId, 10));
  }

  const countSql = sql.replace('SELECT j.*, c.name as company_name, c.logo_url as company_logo, cat.name as category_name', 'SELECT COUNT(*) as count');
  const totalCount = queryOne(countSql, params)?.count || 0;
  const totalPages = Math.ceil(totalCount / perPage) || 1;

  sql += ` ORDER BY j.is_featured DESC, j.created_at DESC LIMIT ? OFFSET ?`;
  params.push(perPage, offset);

  const jobs = queryAll(sql, params);
  const categories = queryAll('SELECT * FROM categories ORDER BY name');

  let savedJobIds = [];
  if (req.session.user_id) {
    const bookmarks = queryAll('SELECT job_id FROM saved_jobs WHERE user_id = ?', [req.session.user_id]);
    savedJobIds = bookmarks.map(b => b.job_id);
  }

  res.render('jobs.html', {
    jobs,
    categories,
    search_term: q,
    selected_location: location,
    selected_type: jobType,
    selected_level: expLevel,
    selected_mode: workMode,
    selected_cat: categoryId,
    page,
    total_pages: totalPages,
    total_count: totalCount,
    saved_job_ids: savedJobIds
  });
});

// Single Job Details
app.get('/job/:id', (req, res) => {
  const jobId = parseInt(req.params.id, 10);
  execute('UPDATE jobs SET views_count = views_count + 1 WHERE id = ?', [jobId]);

  const job = queryOne(`
    SELECT j.*, c.name as company_name, c.logo_url as company_logo, c.slug as company_slug,
           c.website as company_website, c.description as company_description,
           cat.name as category_name, s.name as source_name
    FROM jobs j
    JOIN companies c ON j.company_id = c.id
    JOIN categories cat ON j.category_id = cat.id
    LEFT JOIN job_sources s ON j.source_id = s.id
    WHERE j.id = ?
  `, [jobId]);

  if (!job) {
    req.flash('danger', 'Job not found.');
    return res.redirect('/jobs');
  }

  const relatedJobs = queryAll(`
    SELECT j.*, c.name as company_name, c.logo_url as company_logo
    FROM jobs j
    JOIN companies c ON j.company_id = c.id
    WHERE j.category_id = ? AND j.id != ? AND j.status = 'ACTIVE'
    ORDER BY j.created_at DESC
    LIMIT 3
  `, [job.category_id, jobId]);

  let isSaved = false;
  let isApplied = false;
  if (req.session.user_id) {
    isSaved = !!queryOne('SELECT id FROM saved_jobs WHERE user_id = ? AND job_id = ?', [req.session.user_id, jobId]);
    isApplied = !!queryOne('SELECT id FROM job_applications WHERE user_id = ? AND job_id = ?', [req.session.user_id, jobId]);
  }

  res.render('job_detail.html', {
    job,
    related_jobs: relatedJobs,
    is_saved: isSaved,
    is_applied: isApplied
  });
});

// Specialized Collections
app.get('/internships', (req, res) => {
  const jobs = queryAll(`
    SELECT j.*, c.name as company_name, c.logo_url as company_logo, cat.name as category_name
    FROM jobs j
    JOIN companies c ON j.company_id = c.id
    JOIN categories cat ON j.category_id = cat.id
    WHERE (j.is_internship = 1 OR j.job_type = 'Internship') AND j.status = 'ACTIVE'
    ORDER BY j.created_at DESC
  `);
  res.render('internships.html', { jobs, saved_job_ids: [] });
});

app.get('/fresher', (req, res) => {
  const jobs = queryAll(`
    SELECT j.*, c.name as company_name, c.logo_url as company_logo, cat.name as category_name
    FROM jobs j
    JOIN companies c ON j.company_id = c.id
    JOIN categories cat ON j.category_id = cat.id
    WHERE (j.is_fresher = 1 OR j.experience_level = 'Fresher') AND j.status = 'ACTIVE'
    ORDER BY j.created_at DESC
  `);
  res.render('fresher_jobs.html', { jobs, saved_job_ids: [] });
});

app.get('/remote', (req, res) => {
  const jobs = queryAll(`
    SELECT j.*, c.name as company_name, c.logo_url as company_logo, cat.name as category_name
    FROM jobs j
    JOIN companies c ON j.company_id = c.id
    JOIN categories cat ON j.category_id = cat.id
    WHERE (j.is_remote = 1 OR j.work_mode = 'Remote') AND j.status = 'ACTIVE'
    ORDER BY j.created_at DESC
  `);
  res.render('remote_jobs.html', { jobs, saved_job_ids: [] });
});

// Companies
app.get('/companies', (req, res) => {
  const companies = queryAll(`
    SELECT c.*, COUNT(j.id) as job_count
    FROM companies c
    LEFT JOIN jobs j ON j.company_id = c.id AND j.status = 'ACTIVE'
    GROUP BY c.id
    ORDER BY c.name
  `);
  res.render('companies.html', { companies });
});

app.get('/company/:slug', (req, res) => {
  const company = queryOne('SELECT * FROM companies WHERE slug = ?', [req.params.slug]);
  if (!company) {
    req.flash('danger', 'Company not found.');
    return res.redirect('/companies');
  }

  const jobs = queryAll(`
    SELECT j.*, cat.name as category_name
    FROM jobs j
    JOIN categories cat ON j.category_id = cat.id
    WHERE j.company_id = ? AND j.status = 'ACTIVE'
    ORDER BY j.created_at DESC
  `, [company.id]);

  res.render('company_detail.html', { company, jobs, saved_job_ids: [] });
});

app.get('/about', (req, res) => {
  res.render('about.html');
});

// Auth Routes
app.get('/login', (req, res) => {
  if (req.session.user_id) return res.redirect('/dashboard');
  res.render('auth.html', { mode: 'login' });
});

app.post('/login', (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) {
    req.flash('danger', 'Please enter email and password.');
    return res.render('auth.html', { mode: 'login' });
  }

  const user = queryOne('SELECT * FROM users WHERE email = ?', [email.trim().toLowerCase()]);
  if (!user || !user.password_hash || !checkPassword(password, user.password_hash)) {
    req.flash('danger', 'Invalid email or password.');
    return res.render('auth.html', { mode: 'login' });
  }

  if (user.status === 'SUSPENDED') {
    req.flash('danger', 'Your account has been suspended.');
    return res.render('auth.html', { mode: 'login' });
  }

  req.session.user_id = user.id;
  req.session.user_name = user.full_name;
  req.session.user_email = user.email;
  req.session.user_role = user.role;
  req.session.avatar_url = user.avatar_url;

  req.flash('success', `Welcome back, ${user.full_name}!`);
  const nextUrl = req.query.next || (user.role === 'ADMIN' ? '/admin' : '/dashboard');
  res.redirect(nextUrl);
});

app.get('/register', (req, res) => {
  if (req.session.user_id) return res.redirect('/dashboard');
  res.render('auth.html', { mode: 'register' });
});

app.post('/register', (req, res) => {
  const { full_name, email, password, confirm_password, role } = req.body;

  if (!full_name || !email || !password) {
    req.flash('danger', 'All required fields must be filled.');
    return res.render('auth.html', { mode: 'register' });
  }

  if (password !== confirm_password) {
    req.flash('danger', 'Passwords do not match.');
    return res.render('auth.html', { mode: 'register' });
  }

  const existing = queryOne('SELECT id FROM users WHERE email = ?', [email.trim().toLowerCase()]);
  if (existing) {
    req.flash('danger', 'An account with this email already exists.');
    return res.render('auth.html', { mode: 'register' });
  }

  const userRole = role === 'ADMIN' ? 'ADMIN' : 'USER';
  const hashed = hashPassword(password);
  const avatarUrl = `https://api.dicebear.com/7.x/initials/svg?seed=${encodeURIComponent(full_name)}`;

  const result = execute(`
    INSERT INTO users (full_name, email, password_hash, role, avatar_url, auth_provider)
    VALUES (?, ?, ?, ?, ?, 'LOCAL')
  `, [full_name.trim(), email.trim().toLowerCase(), hashed, userRole, avatarUrl]);

  req.session.user_id = Number(result.lastInsertRowid);
  req.session.user_name = full_name.trim();
  req.session.user_email = email.trim().toLowerCase();
  req.session.user_role = userRole;
  req.session.avatar_url = avatarUrl;

  req.flash('success', 'Registration successful! Welcome to JobPost Aggregator.');
  res.redirect('/dashboard');
});

app.get('/logout', (req, res) => {
  req.session = {};
  res.clearCookie('jp_session');
  res.redirect('/');
});

// Google Sign-In Endpoint
app.post('/api/auth/google/login', (req, res) => {
  const { email, name, avatar_url, google_id } = req.body;
  if (!email) {
    return res.status(400).json({ error: 'Email is required' });
  }

  let user = queryOne('SELECT * FROM users WHERE email = ?', [email.trim().toLowerCase()]);
  if (!user) {
    const avatar = avatar_url || `https://api.dicebear.com/7.x/initials/svg?seed=${encodeURIComponent(name || email)}`;
    const result = execute(`
      INSERT INTO users (full_name, email, google_id, avatar_url, auth_provider, role)
      VALUES (?, ?, ?, ?, 'GOOGLE', 'USER')
    `, [name || email.split('@')[0], email.trim().toLowerCase(), google_id || null, avatar]);
    user = queryOne('SELECT * FROM users WHERE id = ?', [Number(result.lastInsertRowid)]);
  }

  req.session.user_id = user.id;
  req.session.user_name = user.full_name;
  req.session.user_email = user.email;
  req.session.user_role = user.role;
  req.session.avatar_url = user.avatar_url;

  res.json({ success: true, redirect_url: user.role === 'ADMIN' ? '/admin' : '/dashboard' });
});

// User Dashboard
app.get('/dashboard', loginRequired, (req, res) => {
  const user = queryOne('SELECT * FROM users WHERE id = ?', [req.session.user_id]);

  const savedJobs = queryAll(`
    SELECT j.*, c.name as company_name, c.logo_url as company_logo, b.created_at as saved_at
    FROM saved_jobs b
    JOIN jobs j ON b.job_id = j.id
    JOIN companies c ON j.company_id = c.id
    WHERE b.user_id = ?
    ORDER BY b.created_at DESC
  `, [user.id]);

  const applications = queryAll(`
    SELECT a.*, j.title as job_title, j.location as job_location, c.name as company_name
    FROM job_applications a
    JOIN jobs j ON a.job_id = j.id
    JOIN companies c ON j.company_id = c.id
    WHERE a.user_id = ?
    ORDER BY a.applied_at DESC
  `, [user.id]);

  const alerts = queryAll(`
    SELECT a.*, cat.name as category_name
    FROM job_alerts a
    LEFT JOIN categories cat ON a.category_id = cat.id
    WHERE a.user_id = ?
    ORDER BY a.created_at DESC
  `, [user.id]);

  const notifications = queryAll(`
    SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 10
  `, [user.id]);

  const categories = queryAll('SELECT * FROM categories ORDER BY name');

  res.render('dashboard.html', {
    user,
    saved_jobs: savedJobs,
    applications,
    alerts,
    notifications,
    categories
  });
});

// Profile update
app.post('/dashboard/profile', loginRequired, upload.single('resume'), (req, res) => {
  const { full_name, headline, bio, skills, location, experience_level } = req.body;
  const userId = req.session.user_id;

  let resumeFilename = null;
  if (req.file) {
    resumeFilename = req.file.filename;
    execute('UPDATE users SET resume_filename = ? WHERE id = ?', [resumeFilename, userId]);
  }

  execute(`
    UPDATE users
    SET full_name = ?, headline = ?, bio = ?, skills = ?, location = ?, experience_level = ?
    WHERE id = ?
  `, [full_name, headline, bio, skills, location, experience_level, userId]);

  req.session.user_name = full_name;
  req.flash('success', 'Profile updated successfully.');
  res.redirect('/dashboard');
});

// Bookmark API
app.post('/api/jobs/:id/save', loginRequired, (req, res) => {
  const jobId = parseInt(req.params.id, 10);
  const userId = req.session.user_id;

  const existing = queryOne('SELECT id FROM saved_jobs WHERE user_id = ? AND job_id = ?', [userId, jobId]);
  if (existing) {
    execute('DELETE FROM saved_jobs WHERE id = ?', [existing.id]);
    return res.json({ saved: false, message: 'Job removed from bookmarks' });
  } else {
    execute('INSERT INTO saved_jobs (user_id, job_id) VALUES (?, ?)', [userId, jobId]);
    return res.json({ saved: true, message: 'Job saved to bookmarks' });
  }
});

// Track Application API
app.post('/api/jobs/:id/track', loginRequired, (req, res) => {
  const jobId = parseInt(req.params.id, 10);
  const userId = req.session.user_id;
  const { status, notes, interview_date } = req.body;

  const existing = queryOne('SELECT id FROM job_applications WHERE user_id = ? AND job_id = ?', [userId, jobId]);
  if (existing) {
    execute(`
      UPDATE job_applications
      SET status = ?, notes = ?, interview_date = ?, updated_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `, [status || 'Applied', notes || '', interview_date || null, existing.id]);
  } else {
    execute(`
      INSERT INTO job_applications (user_id, job_id, status, notes, interview_date)
      VALUES (?, ?, ?, ?, ?)
    `, [userId, jobId, status || 'Applied', notes || '', interview_date || null]);
  }

  res.json({ success: true, message: 'Application tracking updated' });
});

// Admin Panel
app.get('/admin', adminRequired, (req, res) => {
  const jobs = queryAll(`
    SELECT j.*, c.name as company_name, cat.name as category_name
    FROM jobs j
    JOIN companies c ON j.company_id = c.id
    JOIN categories cat ON j.category_id = cat.id
    ORDER BY j.created_at DESC
  `);
  const sources = queryAll('SELECT * FROM job_sources ORDER BY name');
  const syncLogs = queryAll('SELECT * FROM sync_logs ORDER BY created_at DESC LIMIT 10');
  const reports = queryAll(`
    SELECT r.*, j.title as job_title, u.email as user_email
    FROM job_reports r
    JOIN jobs j ON r.job_id = j.id
    LEFT JOIN users u ON r.user_id = u.id
    ORDER BY r.created_at DESC
  `);

  const stats = {
    total_jobs: queryOne('SELECT COUNT(*) as c FROM jobs')?.c || 0,
    active_jobs: queryOne("SELECT COUNT(*) as c FROM jobs WHERE status = 'ACTIVE'")?.c || 0,
    total_users: queryOne('SELECT COUNT(*) as c FROM users')?.c || 0,
    total_companies: queryOne('SELECT COUNT(*) as c FROM companies')?.c || 0
  };

  const categories = queryAll('SELECT * FROM categories ORDER BY name');
  const companies = queryAll('SELECT * FROM companies ORDER BY name');

  res.render('admin.html', {
    jobs,
    sources,
    sync_logs: syncLogs,
    reports,
    stats,
    categories,
    companies
  });
});

// Admin Job Actions
app.post('/admin/jobs/add', adminRequired, (req, res) => {
  const { title, company_id, category_id, job_type, work_mode, location, salary_min, salary_max, experience_level, description, skills_required, original_url } = req.body;
  const slug = slugify(title);

  execute(`
    INSERT INTO jobs (
      title, slug, company_id, category_id, job_type, work_mode, location,
      salary_min, salary_max, experience_level, description, skills_required, original_url, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
  `, [
    title, slug, parseInt(company_id, 10), parseInt(category_id, 10),
    job_type, work_mode, location,
    parseFloat(salary_min) || 0, parseFloat(salary_max) || 0,
    experience_level, description, skills_required, original_url
  ]);

  req.flash('success', 'Job posted successfully.');
  res.redirect('/admin');
});

app.post('/admin/jobs/delete', adminRequired, (req, res) => {
  const jobId = parseInt(req.body.job_id, 10);
  execute('DELETE FROM jobs WHERE id = ?', [jobId]);
  req.flash('success', 'Job deleted successfully.');
  res.redirect('/admin');
});

// Health check endpoint for Cloud Run
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Start Server on 0.0.0.0
app.listen(port, '0.0.0.0', () => {
  console.log('=========================================================');
  console.log(' JOBPOST AGGREGATOR - Production Node.js / Express Server');
  console.log(` Server actively listening on 0.0.0.0:${port}`);
  console.log(' Ready for Cloud Run & AI Studio deployment');
  console.log('=========================================================');
});
