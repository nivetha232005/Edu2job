# Edu2job

A full-stack ML-powered web application that predicts suitable job roles based on a user's education details.

---

## 🏗️ Tech Stack

| Layer      | Technology                          |
|------------|-------------------------------------|
| Backend    | Python 3.10+ / Flask                |
| Database   | MongoDB                             |
| Frontend   | Plain HTML + CSS + Vanilla JS       |
| ML Model   | XGBoost + scikit-learn              |
| Auth       | JWT + Google OAuth 2.0              |
| Charts     | Chart.js (CDN)                      |

---

## 📁 Project Structure

```
job_predictor/
├── app.py                  # Flask app factory & entry point
├── db_init.py              # DB indexes + admin seed
├── requirements.txt
├── .env                    # Environment variables (do NOT commit)
│
├── routes/
│   ├── auth.py             # Register, login, profile, Google OAuth
│   ├── prediction.py       # ML prediction + history + feedback
│   ├── admin.py            # Admin stats, logs, retrain, promote
│   ├── visualization.py    # Chart data APIs
│   └── pages.py            # HTML page routes
│
├── ml/
│   ├── train_model.py      # Train & save XGBoost model
│   └── sample_data.csv     # Sample training dataset
│
├── models/                 # Saved .pkl files (auto-generated)
│
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── predict.html
│   ├── visualize.html
│   └── admin.html
│
└── static/
    ├── css/style.css
    └── js/auth.js
```

---

## 🚀 Setup & Run

### 1. Prerequisites
- Python 3.10+
- MongoDB running locally on port 27017
- (Optional) Google OAuth credentials

### 2. Clone & install
```bash
git clone <repo-url>
cd job_predictor
pip install -r requirements.txt
```

### 3. Configure environment
Edit `.env`:
```
MONGO_URI=mongodb://localhost:27017/job_predictor
JWT_SECRET_KEY=change-this-to-a-long-random-string
SECRET_KEY=another-random-flask-secret
GOOGLE_CLIENT_ID=your-google-client-id        # optional
GOOGLE_CLIENT_SECRET=your-google-client-secret # optional
```

### 4. Train the ML model
```bash
python ml/train_model.py
```
This saves model files to `models/`.

### 5. Initialize database
```bash
python db_init.py
```
Creates indexes and a default admin user:
- **Email:** `admin@careerpredict.com`
- **Password:** `admin123`

### 6. Run the app
```bash
python app.py
```
Visit **http://localhost:5000**

---

## 🧩 Modules

### Module 1 — User Auth & Profile
- `POST /api/auth/register` — create account
- `POST /api/auth/login` — get JWT token
- `GET  /api/auth/profile` — fetch profile
- `PUT  /api/auth/profile` — update name/education
- `GET  /api/auth/google/login` — Google OAuth

### Module 2 — Education Input
- Profile dashboard supports adding degree, specialization, CGPA, year
- Data validated client-side and stored in MongoDB

### Module 3 — Job Role Prediction
- `POST /api/predict/` — run ML prediction, returns top 5 roles with confidence scores
- `GET  /api/predict/history` — user's past predictions
- `POST /api/predict/feedback` — rate a prediction (1–5 stars)

### Module 4 — Visualization & Admin
- `GET /api/viz/role-frequency` — pie chart data
- `GET /api/viz/education-to-jobs` — stacked bar chart data
- `GET /api/viz/cgpa-confidence` — scatter plot data
- `GET /api/viz/spec-to-domain` — table data
- `GET /api/admin/stats` — dashboard stats
- `GET /api/admin/logs` — all prediction logs
- `POST /api/admin/retrain` — retrain model
- `POST /api/admin/upload-data` — upload new CSV
- `POST /api/admin/flag/<id>` — flag a prediction
- `POST /api/admin/promote/<user_id>` — promote to admin

---

## 🤖 ML Model

- **Algorithm:** XGBoost Classifier
- **Features:** Degree (encoded), Specialization (encoded), CGPA, Years of Experience, Number of Certifications
- **Output:** Top 5 job roles with confidence percentages
- **Retraining:** Admin can upload a new CSV and trigger retraining via the dashboard

To use a real dataset, replace `ml/sample_data.csv` with your data (keep the same column names) and retrain.

---

## 🔐 Security Notes
- JWT tokens expire after 7 days
- Passwords hashed with bcrypt
- Admin routes protected by role check
- Set `JWT_COOKIE_SECURE=True` and use HTTPS in production

---

## 📊 Evaluation Checklist

| Milestone | Feature | Status |
|-----------|---------|--------|
| M1 | User registration & login | ✅ |
| M1 | JWT auth | ✅ |
| M1 | Google OAuth | ✅ |
| M1 | Profile & education history | ✅ |
| M2 | Education input form | ✅ |
| M2 | Data validation | ✅ |
| M2 | Preprocessing pipeline | ✅ |
| M3 | ML model (XGBoost) | ✅ |
| M3 | Top 5 predictions + confidence | ✅ |
| M3 | Skill gap hints | ✅ |
| M3 | Prediction history | ✅ |
| M4 | Pie / Bar / Scatter charts | ✅ |
| M4 | Admin dashboard | ✅ |
| M4 | Model retraining | ✅ |
| M4 | Feedback system | ✅ |
| M4 | Flag/review predictions | ✅ |
