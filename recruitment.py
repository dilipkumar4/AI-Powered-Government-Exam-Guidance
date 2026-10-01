"""
Puducherry Government Recruitment Guidance Portal
Module 2: Recruitment Search & Recommendation
"""

from flask import Blueprint, render_template, request
import mysql.connector

recruitment_bp = Blueprint('recruitment', __name__)

# ---------- Database connection ----------
# Matches the DB_CONFIG already used in app.py
DB_CONFIG = {
    "host": "localhost",
    "user": "root",          # change to your MySQL username
    "password": "",          # change to your MySQL password
    "database": "ai_powered_puducherry_government_exam_guidance"
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


# ---------- Module 6: Eligibility Checker helpers ----------

# Ranks the qualification dropdown from register.html
CANDIDATE_QUALIFICATION_RANK = {
    "10th Standard": 1,
    "12th Standard": 2,
    "Diploma": 3,
    "Bachelor's Degree": 4,
    "Master's Degree": 5,
    "Other": 0,
}


def qualification_rank_from_text(text):
    """
    Recruitment.qualification is free text (e.g. '12th Pass',
    'B.E/B.Tech Civil', 'B.Sc Nursing'). This maps it onto the same
    0-5 rank scale as CANDIDATE_QUALIFICATION_RANK so the two can be
    compared even though they're written differently.
    """
    if not text:
        return 0
    t = text.lower()
    if "master" in t or "post graduate" in t or t.strip() == "pg":
        return 5
    if "bachelor" in t or "degree" in t or "b.e" in t or "b.tech" in t or "b.sc" in t:
        return 4
    if "diploma" in t:
        return 3
    if "12th" in t:
        return 2
    if "10th" in t:
        return 1
    return 0


def calculate_age(dob):
    from datetime import date
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


# ---------- Routes ----------

@recruitment_bp.route('/recruitments')
def list_recruitments():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    search = request.args.get('search', '')
    department = request.args.get('department', '')

    query = "SELECT * FROM recruitments WHERE title LIKE %s"
    params = [f"%{search}%"]

    if department:
        query += " AND department = %s"
        params.append(department)

    query += " ORDER BY title ASC"
    cursor.execute(query, params)
    recruitments = cursor.fetchall()

    cursor.execute("SELECT DISTINCT department FROM recruitments ORDER BY department")
    departments = [row['department'] for row in cursor.fetchall()]

    cursor.close()
    conn.close()
    return render_template('recruitments.html', recruitments=recruitments, departments=departments)


@recruitment_bp.route('/recruitments/<int:recruitment_id>')
def recruitment_detail(recruitment_id):
    """Module 5: Recruitment Information - full detail page for one posting"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM recruitments WHERE id = %s",
        (recruitment_id,)
    )
    recruitment = cursor.fetchone()
    cursor.close()
    conn.close()

    if recruitment is None:
        return render_template('recruitment_detail.html', recruitment=None), 404

    return render_template('recruitment_detail.html', recruitment=recruitment)


@recruitment_bp.route('/recruitments/<int:recruitment_id>/eligibility', methods=['GET', 'POST'])
def check_eligibility(recruitment_id):
    """Module 6: Eligibility Checker"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM recruitments WHERE id = %s", (recruitment_id,))
    recruitment = cursor.fetchone()
    cursor.close()
    conn.close()

    if recruitment is None:
        return render_template('eligibility.html', recruitment=None), 404

    result = None
    form_values = {}

    if request.method == 'POST':
        qualification = request.form.get('qualification', '')
        dob_str = request.form.get('dob', '')
        form_values = request.form

        reasons = []
        is_eligible = True

        # --- Qualification check ---
        candidate_rank = CANDIDATE_QUALIFICATION_RANK.get(qualification, 0)
        required_rank = qualification_rank_from_text(recruitment['qualification'])

        if candidate_rank >= required_rank:
            reasons.append(('pass', f"Qualification requirement met ({recruitment['qualification']} required)"))
        else:
            is_eligible = False
            reasons.append(('fail', f"NOT ELIGIBLE — Required educational qualification is not satisfied "
                                     f"(needs {recruitment['qualification']})"))

        # --- Age check ---
        if dob_str:
            from datetime import datetime
            dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
            age = calculate_age(dob)

            if age < recruitment['min_age']:
                is_eligible = False
                reasons.append(('fail', f"NOT ELIGIBLE — You are below the minimum age of {recruitment['min_age']} years (your age: {age})"))
            elif age > recruitment['max_age']:
                is_eligible = False
                reasons.append(('fail', f"NOT ELIGIBLE — You exceed the maximum age of {recruitment['max_age']} years (your age: {age})"))
            else:
                reasons.append(('pass', f"Age requirement met ({recruitment['min_age']}–{recruitment['max_age']} years, your age: {age})"))

        result = {'eligible': is_eligible, 'reasons': reasons}

    return render_template(
        'eligibility.html',
        recruitment=recruitment,
        qualifications=list(CANDIDATE_QUALIFICATION_RANK.keys()),
        result=result,
        form_values=form_values,
    )


@recruitment_bp.route('/recruitments/<int:recruitment_id>/syllabus')
def view_syllabus(recruitment_id):
    """Module 7: Syllabus and Selection Process"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM recruitments WHERE id = %s", (recruitment_id,))
    recruitment = cursor.fetchone()

    subjects = []
    stages = []
    if recruitment:
        cursor.execute(
            "SELECT * FROM syllabus_subjects WHERE recruitment_id = %s",
            (recruitment_id,)
        )
        subjects = cursor.fetchall()

        cursor.execute(
            "SELECT * FROM selection_stages WHERE recruitment_id = %s ORDER BY stage_order ASC",
            (recruitment_id,)
        )
        stages = cursor.fetchall()

    cursor.close()
    conn.close()

    if recruitment is None:
        return render_template('syllabus.html', recruitment=None), 404

    return render_template(
        'syllabus.html',
        recruitment=recruitment,
        subjects=subjects,
        stages=stages,
    )


@recruitment_bp.route('/recruitments/<int:recruitment_id>/study-material')
def view_study_material(recruitment_id):
    """Module 8: Study Material"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM recruitments WHERE id = %s", (recruitment_id,))
    recruitment = cursor.fetchone()

    materials = []
    if recruitment:
        cursor.execute(
            "SELECT * FROM study_materials WHERE recruitment_id = %s ORDER BY material_type, title",
            (recruitment_id,)
        )
        materials = cursor.fetchall()

    cursor.close()
    conn.close()

    if recruitment is None:
        return render_template('study_material.html', recruitment=None), 404

    return render_template(
        'study_material.html',
        recruitment=recruitment,
        materials=materials,
    )


@recruitment_bp.route('/recommendations')
def recommendations():
    user_qualification = request.args.get('qualification', '')
    user_age = request.args.get('age', '0')
    user_age = int(user_age) if user_age.isdigit() else 0

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT * FROM recruitments
           WHERE qualification LIKE %s
           AND %s BETWEEN min_age AND max_age
           ORDER BY application_end ASC""",
        (f"%{user_qualification}%", user_age)
    )
    matches = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('recommendations.html', matches=matches)