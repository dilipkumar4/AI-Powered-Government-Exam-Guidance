"""
Module 2: Student Profile (Flask Blueprint)
--------------------------------------------
Integrates into the main app.py (Module 1) the same way
recruitment_bp does. Do NOT create a separate Flask() app here.

In Module 1's app.py, add:
    from profile_module import profile_bp
    app.register_blueprint(profile_bp)
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import mysql.connector

profile_bp = Blueprint("profile_bp", __name__)

# ---------------------------------------------------------
# Database connection - MUST match Module 1's DB_CONFIG
# ---------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "ai_powered_puducherry_government_exam_guidance"
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def get_current_user_id():
    return session.get("user_id")


# ---------------------------------------------------------
# Route: Show profile form (create or edit)
# ---------------------------------------------------------
@profile_bp.route("/profile", methods=["GET"])
def view_profile():
    user_id = get_current_user_id()
    if not user_id:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))   # Module 1's login route

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM student_profile WHERE user_id = %s", (user_id,))
    profile = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template("profile.html", profile=profile)


# ---------------------------------------------------------
# Route: Save profile (insert if new, update if exists)
# ---------------------------------------------------------
@profile_bp.route("/profile/save", methods=["POST"])
def save_profile():
    user_id = get_current_user_id()
    if not user_id:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    age = request.form.get("age", type=int)
    qualification = request.form.get("qualification", "").strip()
    skills = request.form.get("skills", "").strip()
    preferred_department = request.form.get("preferred_department", "").strip()
    preferred_job_type = request.form.get("preferred_job_type", "").strip()
    available_study_hours = request.form.get("available_study_hours", type=float)
    target_recruitment = request.form.get("target_recruitment", "").strip()
    preparation_level = request.form.get("preparation_level", "Beginner")
    preferred_language = request.form.get("preferred_language", "English")

    errors = []
    if age is None or not (15 <= age <= 65):
        errors.append("Please enter a valid age (15-65).")
    if not qualification:
        errors.append("Qualification is required.")
    if available_study_hours is None or available_study_hours < 0:
        errors.append("Available study hours must be a positive number.")
    if preparation_level not in ("Beginner", "Intermediate", "Advanced"):
        errors.append("Invalid preparation level.")

    if errors:
        for e in errors:
            flash(e, "danger")
        return redirect(url_for("profile_bp.view_profile"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT profile_id FROM student_profile WHERE user_id = %s", (user_id,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE student_profile
            SET age = %s, qualification = %s, skills = %s,
                preferred_department = %s, preferred_job_type = %s,
                available_study_hours = %s, target_recruitment = %s,
                preparation_level = %s, preferred_language = %s
            WHERE user_id = %s
        """, (age, qualification, skills, preferred_department, preferred_job_type,
              available_study_hours, target_recruitment, preparation_level,
              preferred_language, user_id))
    else:
        cursor.execute("""
            INSERT INTO student_profile
                (user_id, age, qualification, skills, preferred_department,
                 preferred_job_type, available_study_hours, target_recruitment,
                 preparation_level, preferred_language)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, age, qualification, skills, preferred_department,
              preferred_job_type, available_study_hours, target_recruitment,
              preparation_level, preferred_language))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Profile saved successfully.", "success")
    return redirect(url_for("profile_bp.view_profile"))