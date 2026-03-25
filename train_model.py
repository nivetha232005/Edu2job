"""
train_model.py
--------------
Run this script whenever you update job_roles_dataset.csv.
It trains a Random Forest model and saves job_model.pkl in the same folder.

Usage:
    python train_model.py
"""

import pandas as pd
import numpy as np
import pickle
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

# ── Config ────────────────────────────────────────────────────
CSV_PATH   = os.path.join(os.path.dirname(__file__), 'job_roles_dataset.csv')
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'job_model.pkl')

# ── Load dataset ──────────────────────────────────────────────
print(f"Loading dataset from: {CSV_PATH}")
df = pd.read_csv(CSV_PATH).fillna('')
print(f"  Rows: {len(df)}")
print(f"  Job roles ({df['job_role'].nunique()}): {sorted(df['job_role'].unique())}\n")

# ── Feature engineering ───────────────────────────────────────
def combine_features(row):
    cgpa_bucket = int(float(row['cgpa'])) if row['cgpa'] else 0
    return (
        f"{row['degree']} "
        f"{row['specialization']} "
        f"{row['certifications']} "
        f"{row['skills']} "
        f"cgpa_{cgpa_bucket}"
    )

df['combined'] = df.apply(combine_features, axis=1)

# ── Encode labels ─────────────────────────────────────────────
le = LabelEncoder()
y  = le.fit_transform(df['job_role'])

# ── Vectorise text ────────────────────────────────────────────
vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
X = vectorizer.fit_transform(df['combined'])

# ── Train / test split ────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.15, random_state=42, stratify=None
)

# ── Train model ───────────────────────────────────────────────
print("Training Random Forest...")
model = RandomForestClassifier(
    n_estimators=300,
    max_depth=None,
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train)

# ── Evaluate ──────────────────────────────────────────────────
y_pred = model.predict(X_test)
acc = accuracy_score(y_test, y_pred)
print(f"  Accuracy: {acc*100:.1f}%\n")

if len(X_test.toarray()) > 5:
    labels_in_test = sorted(set(y_test) | set(y_pred))
    names_in_test  = le.inverse_transform(labels_in_test)
    print(classification_report(y_test, y_pred, labels=labels_in_test, target_names=names_in_test, zero_division=0))

# ── Save artifacts ────────────────────────────────────────────
bundle = {
    'model':         model,
    'vectorizer':    vectorizer,
    'label_encoder': le,
}
with open(MODEL_PATH, 'wb') as f:
    pickle.dump(bundle, f)

print(f"\nModel saved to: {MODEL_PATH}")
print("Done! Restart your Flask app to use the new model.")