from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_dance.contrib.google import make_google_blueprint, google
import sqlite3, jwt, json, datetime, os, secrets, re, csv, io
from collections import Counter
from functools import wraps
from dotenv import load_dotenv

load_dotenv()
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
JWT_SECRET = os.getenv("JWT_SECRET_KEY") or secrets.token_hex(32)
app.config["SERVER_NAME"] = "127.0.0.1:5050"
app.config["PREFERRED_URL_SCHEME"] = "http"
DATABASE = 'jobrole.db'

google_bp = make_google_blueprint(
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    scope=["openid","https://www.googleapis.com/auth/userinfo.email","https://www.googleapis.com/auth/userinfo.profile"],
)
app.register_blueprint(google_bp, url_prefix="/login")

# ── DB helpers ────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL, password_hash TEXT, role TEXT DEFAULT 'user',
            google_id TEXT, avatar_url TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS education_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            degree TEXT, specialization TEXT, institution TEXT, year_of_passing INTEGER,
            cgpa REAL, certifications TEXT, skills TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS prediction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            input_summary TEXT, predicted_roles TEXT, confidence_scores TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS prediction_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            prediction_id INTEGER, predicted_role TEXT,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            relevance TEXT, comment TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS uploaded_datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT NOT NULL,
            row_count INTEGER, uploaded_by INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        if not db.execute("SELECT id FROM users WHERE email='admin@jobrole.ai'").fetchone():
            db.execute("INSERT INTO users (full_name,email,password_hash,role) VALUES (?,?,?,?)",
                ('Admin User','admin@jobrole.ai',generate_password_hash('admin123'),'admin'))
        db.commit()

init_db()

# ── Auth decorators ───────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def d(*a,**kw):
        if 'user_id' not in session:
            flash('Please login to continue.','warning')
            return redirect(url_for('login'))
        return f(*a,**kw)
    return d

def admin_required(f):
    @wraps(f)
    def d(*a,**kw):
        if 'user_id' not in session or session.get('role')!='admin':
            flash('Admin access required.','danger')
            return redirect(url_for('dashboard'))
        return f(*a,**kw)
    return d

# ── JWT helpers ───────────────────────────────────────────────
def generate_jwt(uid, role):
    return jwt.encode({'user_id':uid,'role':role,
        'exp':datetime.datetime.utcnow()+datetime.timedelta(days=7),
        'iat':datetime.datetime.utcnow()}, JWT_SECRET, algorithm='HS256')

def decode_jwt(token):
    try: return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except: return None

# ── Public routes ─────────────────────────────────────────────
@app.route("/google-login")
def google_login():
    if not google.authorized: return redirect(url_for("google.login"))
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        flash("Google login failed.","danger"); return redirect(url_for("login"))
    info = resp.json()
    email,name,gid,avatar = info["email"],info.get("name","Google User"),info["id"],info.get("picture","")
    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        if not user:
            db.execute("INSERT INTO users (full_name,email,google_id,avatar_url) VALUES (?,?,?,?)",(name,email,gid,avatar))
            db.commit()
            user = db.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
    session.update(user_id=user["id"],user_name=user["full_name"],email=user["email"],
        role=user["role"],avatar=user["avatar_url"] or "",jwt_token=generate_jwt(user["id"],user["role"]))
    flash(f"Welcome, {user['full_name']}!","success")
    return redirect(url_for("dashboard"))

@app.route('/')
def index():
    return redirect(url_for('dashboard')) if 'user_id' in session else render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method=='POST':
        fn=request.form.get('full_name','').strip(); em=request.form.get('email','').strip().lower()
        pw=request.form.get('password',''); cf=request.form.get('confirm_password','')
        errors=[]
        if not fn: errors.append('Full name is required.')
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$',em): errors.append('Invalid email address.')
        if len(pw)<8: errors.append('Password must be at least 8 characters.')
        if pw!=cf: errors.append('Passwords do not match.')
        if errors:
            [flash(e,'danger') for e in errors]
            return render_template('register.html',full_name=fn,email=em)
        with get_db() as db:
            if db.execute("SELECT id FROM users WHERE email=?",(em,)).fetchone():
                flash('Email already registered.','warning'); return redirect(url_for('login'))
            db.execute("INSERT INTO users (full_name,email,password_hash) VALUES (?,?,?)",(fn,em,generate_password_hash(pw)))
            db.commit()
        flash('Registration successful! Please login.','success'); return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method=='POST':
        em=request.form.get('email','').strip().lower(); pw=request.form.get('password','')
        with get_db() as db:
            user=db.execute("SELECT * FROM users WHERE email=?",(em,)).fetchone()
        if user and user['password_hash'] and check_password_hash(user['password_hash'],pw):
            session.update(user_id=user['id'],user_name=user['full_name'],role=user['role'],
                email=user['email'],avatar=user['avatar_url'] or '',
                jwt_token=generate_jwt(user['id'],user['role']))
            flash(f"Welcome back, {user['full_name'].split()[0]}!",'success')
            return redirect(url_for('admin_dashboard') if user['role']=='admin' else url_for('dashboard'))
        flash('Invalid email or password.','danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); flash('You have been logged out.','info'); return redirect(url_for('index'))

# ── User routes ───────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    with get_db() as db:
        user=db.execute("SELECT * FROM users WHERE id=?",(session['user_id'],)).fetchone()
        edu=db.execute("SELECT * FROM education_profiles WHERE user_id=?",(session['user_id'],)).fetchone()
        rows=db.execute("SELECT * FROM prediction_history WHERE user_id=? ORDER BY created_at DESC LIMIT 5",(session['user_id'],)).fetchall()
    hist=[{**dict(h),'predicted_roles':json.loads(h['predicted_roles']) if h['predicted_roles'] else [],
           'confidence_scores':json.loads(h['confidence_scores']) if h['confidence_scores'] else []} for h in rows]
    return render_template('dashboard.html',user=user,edu=edu,history=hist)

@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    with get_db() as db:
        user=db.execute("SELECT * FROM users WHERE id=?",(session['user_id'],)).fetchone()
        edu=db.execute("SELECT * FROM education_profiles WHERE user_id=?",(session['user_id'],)).fetchone()
    if request.method=='POST':
        action=request.form.get('action')
        if action=='update_personal':
            fn=request.form.get('full_name','').strip()
            if fn:
                with get_db() as db:
                    db.execute("UPDATE users SET full_name=? WHERE id=?",(fn,session['user_id'])); db.commit()
                session['user_name']=fn; flash('Personal info updated.','success')
        elif action=='update_password':
            cur=request.form.get('current_password',''); npw=request.form.get('new_password',''); cf=request.form.get('confirm_new_password','')
            with get_db() as db: u=db.execute("SELECT * FROM users WHERE id=?",(session['user_id'],)).fetchone()
            if u['password_hash'] and not check_password_hash(u['password_hash'],cur): flash('Current password is incorrect.','danger')
            elif len(npw)<8: flash('New password must be at least 8 characters.','danger')
            elif npw!=cf: flash('New passwords do not match.','danger')
            else:
                with get_db() as db:
                    db.execute("UPDATE users SET password_hash=? WHERE id=?",(generate_password_hash(npw),session['user_id'])); db.commit()
                flash('Password updated successfully.','success')
        elif action=='update_education':
            degree=request.form.get('degree','').strip(); spec=request.form.get('specialization','').strip()
            inst=request.form.get('institution','').strip(); yr=request.form.get('year_of_passing','')
            cg=request.form.get('cgpa',''); certs=request.form.get('certifications','').strip(); skills=request.form.get('skills','').strip()
            try: yr=int(yr) if yr else None; cg=float(cg) if cg else None
            except: yr=None; cg=None
            with get_db() as db:
                if db.execute("SELECT id FROM education_profiles WHERE user_id=?",(session['user_id'],)).fetchone():
                    db.execute("UPDATE education_profiles SET degree=?,specialization=?,institution=?,year_of_passing=?,cgpa=?,certifications=?,skills=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                        (degree,spec,inst,yr,cg,certs,skills,session['user_id']))
                else:
                    db.execute("INSERT INTO education_profiles (user_id,degree,specialization,institution,year_of_passing,cgpa,certifications,skills) VALUES (?,?,?,?,?,?,?,?)",
                        (session['user_id'],degree,spec,inst,yr,cg,certs,skills))
                db.commit()
            flash('Education profile updated.','success')
        return redirect(url_for('profile'))
    return render_template('profile.html',user=user,edu=edu)

@app.route('/history')
@login_required
def history():
    with get_db() as db:
        records=db.execute("SELECT * FROM prediction_history WHERE user_id=? ORDER BY created_at DESC",(session['user_id'],)).fetchall()
    return render_template('history.html',records=records)

# ── Admin routes (Module 4) ───────────────────────────────────
@app.route('/admin')
@admin_required
def admin_dashboard():
    with get_db() as db:
        users=db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        total_users=db.execute("SELECT COUNT(*) as c FROM users WHERE role='user'").fetchone()['c']
        total_preds=db.execute("SELECT COUNT(*) as c FROM prediction_history").fetchone()['c']
        total_feedback=db.execute("SELECT COUNT(*) as c FROM prediction_feedback").fetchone()['c']
        avg_row=db.execute("SELECT AVG(rating) as a FROM prediction_feedback").fetchone()
        avg_feedback_score=round(avg_row['a'],1) if avg_row['a'] else 0
        recent_queries=db.execute("""SELECT ph.*, u.full_name, u.email FROM prediction_history ph
            JOIN users u ON ph.user_id=u.id ORDER BY ph.created_at DESC LIMIT 20""").fetchall()
        feedbacks=db.execute("""SELECT pf.*, u.full_name as user_name FROM prediction_feedback pf
            JOIN users u ON pf.user_id=u.id ORDER BY pf.created_at DESC""").fetchall()
        last_ds=db.execute("SELECT * FROM uploaded_datasets ORDER BY uploaded_at DESC LIMIT 1").fetchone()
    upload_success=session.pop('upload_success',False)
    upload_filename=session.pop('upload_filename','')
    upload_rows=session.pop('upload_rows',0)
    return render_template('admin_dashboard.html',
        users=users, total_users=total_users, total_preds=total_preds,
        total_feedback=total_feedback, avg_feedback_score=avg_feedback_score,
        recent_queries=recent_queries, feedbacks=feedbacks,
        last_dataset=last_ds['filename'] if last_ds else None,
        upload_success=upload_success, upload_filename=upload_filename, upload_rows=upload_rows,
        model_accuracy=87, model_algorithm='Random Forest', model_trained_at='—')

@app.route('/admin/upload-dataset', methods=['POST'])
@admin_required
def admin_upload_dataset():
    f=request.files.get('dataset')
    if not f or not f.filename.endswith('.csv'):
        flash('Please upload a valid CSV file.','danger'); return redirect(url_for('admin_dashboard'))
    content=f.read().decode('utf-8',errors='ignore')
    row_count=max(0,len(list(csv.reader(io.StringIO(content))))-1)
    with get_db() as db:
        db.execute("INSERT INTO uploaded_datasets (filename,row_count,uploaded_by) VALUES (?,?,?)",(f.filename,row_count,session['user_id'])); db.commit()
    session.update(upload_success=True,upload_filename=f.filename,upload_rows=row_count)
    flash(f'Dataset "{f.filename}" uploaded ({row_count} rows).','success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle-role/<int:user_id>', methods=['POST'])
@admin_required
def admin_toggle_role(user_id):
    with get_db() as db:
        user=db.execute("SELECT * FROM users WHERE id=?",(user_id,)).fetchone()
        if user and user['id']!=session['user_id']:
            new_role='admin' if user['role']=='user' else 'user'
            db.execute("UPDATE users SET role=? WHERE id=?",(new_role,user_id)); db.commit()
            flash(f'{user["full_name"]} is now {new_role}.','success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    if user_id==session['user_id']:
        flash('You cannot delete your own account.','danger'); return redirect(url_for('admin_dashboard'))
    with get_db() as db:
        user=db.execute("SELECT full_name FROM users WHERE id=?",(user_id,)).fetchone()
        if user:
            for tbl in ['prediction_feedback','prediction_history','education_profiles','users']:
                db.execute(f"DELETE FROM {tbl} WHERE {'id' if tbl=='users' else 'user_id'}=?",(user_id,))
            db.commit(); flash(f'User "{user["full_name"]}" deleted.','success')
    return redirect(url_for('admin_dashboard'))

# ── Visualizations (Module 4) ─────────────────────────────────
@app.route('/insights')
@login_required
def visualizations():
    with get_db() as db:
        all_preds=db.execute("SELECT * FROM prediction_history").fetchall()
        total_predictions=len(all_preds)
        total_users_count=db.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
        all_edu=db.execute("SELECT * FROM education_profiles").fetchall()
        daily=db.execute("""SELECT DATE(created_at) as day, COUNT(*) as cnt FROM prediction_history
            WHERE created_at>=DATE('now','-30 days') GROUP BY day ORDER BY day""").fetchall()
        skill_rows=db.execute("SELECT skills FROM education_profiles WHERE skills IS NOT NULL").fetchall()

    role_counter=Counter()
    conf_list=[]
    for p in all_preds:
        roles=json.loads(p['predicted_roles']) if p['predicted_roles'] else []
        scores=json.loads(p['confidence_scores']) if p['confidence_scores'] else []
        for r in roles: role_counter[r]+=1
        if scores: conf_list.append(scores[0])

    top_roles=role_counter.most_common(8)
    role_chart_data=(
        {'labels':[r for r,_ in top_roles],'values':[c for _,c in top_roles]}
        if top_roles else
        {'labels':['Data Scientist','ML Engineer','Full Stack Dev','Data Analyst','DevOps Engineer','Cloud Architect','Embedded Eng','Product Manager'],
         'values':[42,35,28,24,18,15,11,9]}
    )

    deg_counter=Counter(e['degree'] for e in all_edu if e['degree'])
    degree_chart_data=(
        {'labels':list(deg_counter.keys()),'values':list(deg_counter.values())}
        if deg_counter else
        {'labels':['B.Tech','B.E','M.Tech','MCA','BCA','MBA'],'values':[38,24,16,10,7,5]}
    )

    if daily:
        activity_chart_data={'labels':[r['day'][5:] for r in daily],'values':[r['cnt'] for r in daily]}
    else:
        import random; random.seed(42)
        days=[(datetime.date.today()-datetime.timedelta(days=29-i)).strftime('%m-%d') for i in range(30)]
        activity_chart_data={'labels':days,'values':[random.randint(0,8) for _ in days]}

    skill_counter=Counter()
    for row in skill_rows:
        for s in row['skills'].split(','):
            s=s.strip()
            if s: skill_counter[s.title()]+=1
    top_skills=skill_counter.most_common(8)
    skills_chart_data=(
        {'labels':[s for s,_ in top_skills],'values':[c for _,c in top_skills]}
        if top_skills else
        {'labels':['Python','Machine Learning','SQL','Java','Data Analysis','Flask','React','Cloud'],
         'values':[85,72,68,55,60,40,38,45]}
    )

    return render_template('visualizations.html',
        total_predictions=total_predictions, total_users=total_users_count,
        avg_confidence=round(sum(conf_list)/len(conf_list),1) if conf_list else 88,
        top_role=role_chart_data['labels'][0],
        top_degree=degree_chart_data['labels'][0],
        role_chart_data=role_chart_data, degree_chart_data=degree_chart_data,
        activity_chart_data=activity_chart_data, skills_chart_data=skills_chart_data)

# ── Feedback (Module 4) ───────────────────────────────────────
@app.route('/feedback')
@login_required
def feedback():
    pid=request.args.get('prediction_id',type=int)
    with get_db() as db:
        prediction=None
        row=db.execute(
            "SELECT * FROM prediction_history WHERE id=? AND user_id=?" if pid else
            "SELECT * FROM prediction_history WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
            (pid,session['user_id']) if pid else (session['user_id'],)
        ).fetchone()
        if row:
            prediction={**dict(row),
                'predicted_roles':json.loads(row['predicted_roles']) if row['predicted_roles'] else [],
                'confidence_scores':json.loads(row['confidence_scores']) if row['confidence_scores'] else []}
        past=db.execute("SELECT * FROM prediction_feedback WHERE user_id=? ORDER BY created_at DESC LIMIT 10",(session['user_id'],)).fetchall()
    return render_template('feedback.html',prediction=prediction,past_feedback=past)

@app.route('/feedback/submit', methods=['POST'])
@login_required
def submit_feedback():
    pid=request.form.get('prediction_id',type=int)
    role=request.form.get('predicted_role','').strip()
    rating=request.form.get('rating',type=int)
    if not rating or not 1<=rating<=5:
        flash('Please select a star rating.','danger'); return redirect(url_for('feedback'))
    with get_db() as db:
        db.execute("INSERT INTO prediction_feedback (user_id,prediction_id,predicted_role,rating,relevance,comment) VALUES (?,?,?,?,?,?)",
            (session['user_id'],pid,role,rating,request.form.get('relevance',''),request.form.get('comment','').strip()))
        db.commit()
    flash('Thank you for your feedback! It helps us improve.','success')
    return redirect(url_for('dashboard'))

# ── ML Model loader (Module 3) ────────────────────────────────
import pickle, numpy as np

_ML_BUNDLE = None   # cached after first load

def _get_ml_bundle():
    """Load model from job_model.pkl once and cache it."""
    global _ML_BUNDLE
    if _ML_BUNDLE is None:
        model_path = os.path.join(os.path.dirname(__file__), 'job_model.pkl')
        if os.path.exists(model_path):
            with open(model_path, 'rb') as f:
                _ML_BUNDLE = pickle.load(f)
    return _ML_BUNDLE

def _justification(role, degree, specialization, skills, certifications):
    """Generate a human-readable justification sentence for a predicted role."""
    skill_list = [s.strip() for s in (skills or '').split(',') if s.strip()]
    cert_list  = [c.strip() for c in (certifications or '').split(',') if c.strip()]
    highlights = (skill_list[:3] + cert_list[:1])[:3]
    highlight_str = ', '.join(highlights) if highlights else (specialization or degree or 'your background')

    templates = {
        'Data Scientist':           f"Your {specialization} background with {highlight_str} strongly aligns with data science.",
        'Machine Learning Engineer':f"ML-focused skills ({highlight_str}) from {specialization} match ML engineering well.",
        'Data Analyst':             f"Your analytical background in {specialization} with {highlight_str} fits data analyst roles.",
        'Software Developer':       f"{highlight_str} skills from {specialization} are a solid fit for software development.",
        'Full Stack Developer':     f"Your {specialization} background with {highlight_str} matches full-stack development.",
        'DevOps Engineer':          f"Infrastructure skills ({highlight_str}) from {specialization} align with DevOps.",
        'Cloud Architect':          f"Cloud certifications and {highlight_str} skills match cloud architecture roles.",
        'Cybersecurity Analyst':    f"Security-focused skills ({highlight_str}) from {specialization} suit cybersecurity.",
        'Embedded Systems Engineer':f"Hardware/embedded skills ({highlight_str}) from {specialization} fit embedded roles.",
        'Network Engineer':         f"Your networking skills ({highlight_str}) from {specialization} match network engineering.",
        'AI/ML Researcher':         f"Research-oriented {specialization} background with {highlight_str} suits AI research.",
        'Business Analyst':         f"Business skills ({highlight_str}) from {specialization} align with business analysis.",
        'Financial Analyst':        f"Finance knowledge ({highlight_str}) from {specialization} suits financial analysis.",
        'Product Manager':          f"Management and strategy skills ({highlight_str}) match product management roles.",
        'Database Administrator':   f"Database skills ({highlight_str}) from {specialization} are ideal for DBA roles.",
        'Mobile App Developer':     f"Mobile development skills ({highlight_str}) from {specialization} match app dev roles.",
        'Data Engineer':            f"Big data and pipeline skills ({highlight_str}) from {specialization} fit data engineering.",
        'HR Analyst':               f"Your {specialization} background with {highlight_str} aligns with HR analytics.",
        'Research Analyst':         f"Research and analytical skills ({highlight_str}) from {specialization} suit this role.",
        'Mechanical Design Engineer':f"Engineering skills ({highlight_str}) from {specialization} match mechanical design.",
        'Civil Engineer':           f"Your {specialization} background with {highlight_str} aligns with civil engineering.",
    }
    return templates.get(role, f"Your {specialization} background with {highlight_str} aligns with {role}.")


# ── Job Role Prediction (Module 3) ───────────────────────────
def predict_job_roles(degree, specialization, cgpa, certifications, skills):
    """
    CSV-trained Random Forest model predicts top 10 job roles.
    Falls back to rule-based scoring if model file is missing.
    Returns list of (role, confidence, justification) tuples.
    """
    bundle = _get_ml_bundle()

    if bundle:
        # ── ML path: use trained Random Forest ──────────────────
        model      = bundle['model']
        vectorizer = bundle['vectorizer']
        le         = bundle['label_encoder']

        cgpa_val = int(float(cgpa)) if cgpa else 0
        combined = f"{degree} {specialization} {certifications} {skills} cgpa_{cgpa_val}"
        X = vectorizer.transform([combined])

        proba     = model.predict_proba(X)[0]
        top10_idx = np.argsort(proba)[::-1][:10]

        results = []
        for idx in top10_idx:
            conf = int(round(proba[idx] * 100))
            if conf < 3:
                continue
            role = le.classes_[idx]
            just = _justification(role, degree, specialization, skills, certifications)
            results.append((role, conf, just))
        return results

    else:
        # ── Fallback: rule-based (runs if job_model.pkl is missing) ──
        degree_l = (degree or '').lower()
        spec     = (specialization or '').lower()
        certs    = (certifications or '').lower()
        skills_l = [s.strip().lower() for s in (skills or '').split(',') if s.strip()]
        cgpa_f   = float(cgpa) if cgpa else 0.0
        all_text = f"{spec} {certs} {' '.join(skills_l)}"

        role_defs = [
            ("Data Scientist",60,['python','ml','machine learning','tensorflow','data science','statistics','pandas']),
            ("Machine Learning Engineer",58,['machine learning','tensorflow','pytorch','deep learning','nlp','ai']),
            ("Data Analyst",55,['sql','excel','tableau','power bi','statistics','data analysis','python']),
            ("Software Developer",56,['java','python','javascript','spring','git','rest','oop','programming']),
            ("Full Stack Developer",52,['react','node','javascript','html','css','mongodb','rest api']),
            ("DevOps Engineer",50,['docker','kubernetes','jenkins','ci/cd','linux','terraform','aws']),
            ("Cloud Architect",48,['aws','azure','gcp','cloud','terraform','microservices','serverless']),
            ("Cybersecurity Analyst",46,['security','cybersecurity','ethical hacking','linux','soc','penetration']),
            ("Embedded Systems Engineer",44,['embedded','c','c++','iot','arduino','rtos','microcontroller']),
            ("Network Engineer",42,['networking','cisco','ccna','tcp/ip','routing','switching','firewall']),
        ]
        results = []
        for role, base, kws in role_defs:
            score = base + sum(6 for kw in kws if kw in all_text)
            if 'b.tech' in degree_l or 'b.e' in degree_l: score += 4
            if 'm.tech' in degree_l: score += 6
            if 'mba' in degree_l and role in ('Business Analyst','Product Manager'): score += 15
            if cgpa_f >= 8.5: score += 5
            conf = min(95, score)
            just = _justification(role, degree, specialization, skills, certifications)
            results.append((role, conf, just))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:10]


@app.route('/predict', methods=['GET', 'POST'])
@login_required
def predict():
    with get_db() as db:
        edu = db.execute("SELECT * FROM education_profiles WHERE user_id=?", (session['user_id'],)).fetchone()

    prediction_results = None
    form_data = {}

    if request.method == 'POST':
        degree        = request.form.get('degree', '').strip()
        specialization= request.form.get('specialization', '').strip()
        institution   = request.form.get('institution', '').strip()
        year          = request.form.get('year_of_passing', '').strip()
        cgpa_raw      = request.form.get('cgpa', '').strip()
        certifications= request.form.get('certifications', '').strip()
        skills        = request.form.get('skills', '').strip()

        form_data = dict(degree=degree, specialization=specialization, institution=institution,
                         year_of_passing=year, cgpa=cgpa_raw, certifications=certifications, skills=skills)

        errors = []
        if not degree:            errors.append('Degree is required.')
        if not specialization:    errors.append('Specialization is required.')
        cgpa = None
        if cgpa_raw:
            try:
                cgpa = float(cgpa_raw)
                if not 0 <= cgpa <= 10: errors.append('CGPA must be between 0 and 10.')
            except ValueError:
                errors.append('CGPA must be a number.')

        if errors:
            [flash(e, 'danger') for e in errors]
        else:
            roles = predict_job_roles(degree, specialization, cgpa, certifications, skills)
            if roles:
                prediction_results = [{'role': r, 'confidence': c, 'justification': j} for r, c, j in roles]
                input_summary = f"{degree} in {specialization}" + (f", CGPA {cgpa}" if cgpa else "")
                if skills: input_summary += f", Skills: {skills[:60]}"
                with get_db() as db:
                    db.execute(
                        "INSERT INTO prediction_history (user_id, input_summary, predicted_roles, confidence_scores) VALUES (?,?,?,?)",
                        (session['user_id'], input_summary,
                         json.dumps([r['role'] for r in prediction_results]),
                         json.dumps([r['confidence'] for r in prediction_results]))
                    )
                    db.commit()
                flash(f'Prediction complete! Found {len(prediction_results)} matching roles. Results saved to your history.', 'success')
            else:
                flash('Could not generate predictions. Please provide more details.', 'warning')

    return render_template('predict.html', edu=edu, prediction_results=prediction_results, form_data=form_data)


# ── API ───────────────────────────────────────────────────────
@app.route('/api/verify-token', methods=['POST'])
def verify_token():
    payload=decode_jwt(request.json.get('token',''))
    if payload: return jsonify({'valid':True,'user_id':payload['user_id'],'role':payload['role']})
    return jsonify({'valid':False}),401

@app.route('/seed-demo')
@login_required
def seed_demo():
    with get_db() as db:
        if not db.execute("SELECT id FROM education_profiles WHERE user_id=?",(session['user_id'],)).fetchone():
            db.execute("INSERT INTO education_profiles (user_id,degree,specialization,institution,year_of_passing,cgpa,certifications,skills) VALUES (?,?,?,?,?,?,?,?)",
                (session['user_id'],"B.Tech","Computer Science","Anna University",2024,8.5,
                 "AWS Cloud Practitioner, Python for Data Science","Python, Machine Learning, SQL, Data Analysis, Flask"))
        db.execute("INSERT INTO prediction_history (user_id,input_summary,predicted_roles,confidence_scores) VALUES (?,?,?,?)",
            (session['user_id'],"B.Tech CSE, CGPA 8.5, Skills: Python, ML, SQL",
             '["Data Scientist","ML Engineer","Data Analyst","Backend Developer","AI Researcher"]','[92,87,81,74,68]'))
        db.commit()
    flash('Demo data seeded successfully!','success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    with app.app_context():
        print("Google authorized endpoint:", url_for("google.authorized",_external=True))
    app.run(host='0.0.0.0', port=port, debug=False)
