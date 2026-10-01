"""
Puducherry Government Recruitment Guidance Portal
Module 1: User Registration
"""
 
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from datetime import datetime
from recruitment import recruitment_bp
from weakness import weakness_bp
from recruitment import (
    CANDIDATE_QUALIFICATION_RANK,
    qualification_rank_from_text,
    calculate_age,
)
from profile_module import profile_bp   # <-- ADDED: import the profile blueprint
from study_planner import study_planner_bp   # Module 11
from flask_mail import Mail
from hall_ticket import hall_ticket_bp   # Module 19
 
app = Flask(__name__)
app.secret_key = "change-this-to-a-random-secret-key"   # needed for session/flash
 
# ---------- Flask-Mail config (Module 19) ----------
# Secrets are read from environment variables (never type the password here).
# In the terminal, before running Flask:
#   set MAIL_USERNAME=your_gmail@gmail.com
#   set MAIL_PASSWORD=your_gmail_app_password
import os
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME")
 
# Emails allowed to use admin pages
ADMIN_EMAILS = {"314dilip@gmail.com"}
mail = Mail(app)
 
app.register_blueprint(recruitment_bp)
app.register_blueprint(profile_bp)   # <-- ADDED: register the profile blueprint
app.register_blueprint(weakness_bp)
app.register_blueprint(study_planner_bp)   # Module 11
app.register_blueprint(hall_ticket_bp)   # Module 19
# ---------- Database connection ----------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",          # change to your MySQL username
    "password": "",          # change to your MySQL password
    "database": "ai_powered_puducherry_government_exam_guidance"
}
 
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)
 
 
# ---------- Routes ----------
 
@app.route("/")
def home():
    return render_template("home.html")
 
 
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        mobile = request.form.get("mobile", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        dob = request.form.get("dob", "")
        qualification = request.form.get("qualification", "").strip()
        preferred_language = request.form.get("preferred_language", "English")
 
        # ---- Basic validation ----
        if not all([name, email, mobile, password, dob, qualification]):
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("register"))
 
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))
 
        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return redirect(url_for("register"))
 
        if not mobile.isdigit() or len(mobile) != 10:
            flash("Enter a valid 10-digit mobile number.", "danger")
            return redirect(url_for("register"))
 
        password_hash = generate_password_hash(password)
 
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO users
                   (name, email, mobile, password_hash, dob, qualification, preferred_language)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (name, email, mobile, password_hash, dob, qualification, preferred_language)
            )
            conn.commit()
 
            # ---- Module 6 (extended): show eligible recruitments right away ----
            dob_date = datetime.strptime(dob, "%Y-%m-%d").date()
            age = calculate_age(dob_date)
            candidate_rank = CANDIDATE_QUALIFICATION_RANK.get(qualification, 0)
 
            elig_conn = get_db_connection()
            elig_cursor = elig_conn.cursor(dictionary=True)
            elig_cursor.execute("SELECT * FROM recruitments")
            all_recruitments = elig_cursor.fetchall()
            elig_cursor.close()
            elig_conn.close()
 
            eligible_recruitments = [
                r for r in all_recruitments
                if candidate_rank >= qualification_rank_from_text(r["qualification"])
                and r["min_age"] <= age <= r["max_age"]
            ]
 
            flash("Registration successful! Here's what you may be eligible for.", "success")
            return render_template(
                "register_eligible.html",
                name=name,
                qualification=qualification,
                age=age,
                recruitments=eligible_recruitments,
            )
        except mysql.connector.errors.IntegrityError:
            flash("An account with this email already exists.", "danger")
            return redirect(url_for("register"))
        finally:
            cursor.close()
            conn.close()
 
    return render_template("register.html")
 
 
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
 
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
 
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["user_id"]
            session["name"] = user["name"]
            session["is_admin"] = user["email"] in ADMIN_EMAILS
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))
 
    return render_template("login.html")
 
 
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please log in to continue.", "warning")
        return redirect(url_for("login"))
    return render_template("dashboard.html", name=session.get("name"))
 
 
@app.route("/diagnostic-test", methods=["GET", "POST"])
def diagnostic_test():
    """Module 9: Diagnostic Assessment"""
    if "user_id" not in session:
        flash("Please log in to take the diagnostic test.", "warning")
        return redirect(url_for("login"))
 
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM diagnostic_questions")
    questions = cursor.fetchall()
 
    result = None
 
    if request.method == "POST":
        subject_stats = {}   # subject -> [correct, total]
        score = 0
 
        for q in questions:
            subject_stats.setdefault(q["subject"], [0, 0])
            subject_stats[q["subject"]][1] += 1
 
            submitted = request.form.get(f"question_{q['question_id']}")
            if submitted == q["correct_option"]:
                score += 1
                subject_stats[q["subject"]][0] += 1
 
        total = len(questions)
        percentage = round((score / total) * 100, 2) if total else 0
 
        if percentage < 40:
            preparation_level = "Beginner"
        elif percentage < 70:
            preparation_level = "Intermediate"
        else:
            preparation_level = "Advanced"
 
        breakdown_str = "; ".join(
            f"{subj}: {c}/{t}" for subj, (c, t) in subject_stats.items()
        )
 
        cursor.execute(
            """INSERT INTO diagnostic_results
               (user_id, score, total_questions, percentage, preparation_level, subject_breakdown)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (session["user_id"], score, total, percentage, preparation_level, breakdown_str)
        )
        conn.commit()
 
        result = {
            "score": score,
            "total": total,
            "percentage": percentage,
            "preparation_level": preparation_level,
            "subject_stats": subject_stats,
        }
 
    cursor.close()
    conn.close()
 
    return render_template("diagnostic_test.html", questions=questions, result=result)
 
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))
 
 
if __name__ == "__main__":
    app.run(debug=True)