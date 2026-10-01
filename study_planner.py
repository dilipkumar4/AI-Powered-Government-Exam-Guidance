"""
Module 11: AI Personalized Study Planner
------------------------------------------------------------------
Generates a study schedule from the student's target recruitment,
available study hours, weak topics (Module 10's KMeans output), and
current preparation level / performance (Module 9).

AI TECHNIQUE USED: Linear Programming (constrained optimization),
via scipy.optimize.linprog. Each subject is assigned a priority
score derived from its accuracy and weakness level. The optimizer
then solves for the time allocation (in minutes) that MAXIMIZES
total learning benefit (sum of priority * time), subject to:
    - total time <= the student's available study time
    - each subject gets at least a minimum floor of time
    - no single subject can consume more than a fair ceiling of time
This is a genuine optimization problem being solved algorithmically,
not a hardcoded percentage split.
"""

from flask import Blueprint, render_template, session, redirect, url_for, flash
import mysql.connector
from scipy.optimize import linprog

study_planner_bp = Blueprint("study_planner_bp", __name__)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "ai_powered_puducherry_government_exam_guidance"
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


LEVEL_MULTIPLIERS = {
    "Beginner":     {"Weak": 2.0, "Moderate": 1.0, "Strong": 0.3},
    "Intermediate": {"Weak": 1.5, "Moderate": 1.1, "Strong": 0.6},
    "Advanced":     {"Weak": 1.2, "Moderate": 1.1, "Strong": 0.9},
}


def compute_priority(accuracy, weakness_level, preparation_level):
    """Higher priority = needs more study time."""
    multipliers = LEVEL_MULTIPLIERS.get(preparation_level, LEVEL_MULTIPLIERS["Intermediate"])
    multiplier = multipliers.get(weakness_level, 1.0)
    return multiplier * (100 - accuracy + 1)


def optimize_schedule(subjects, available_hours, preparation_level):
    """
    Uses linear programming (scipy.optimize.linprog) to solve for the
    time (in minutes) allocated to each subject that maximizes total
    weighted priority, subject to a total time budget and per-subject
    min/max bounds.
    """
    total_minutes = max(int(round(available_hours * 60)), 30)
    revision_minutes = max(int(total_minutes * 0.10), 10)
    working_minutes = total_minutes - revision_minutes

    n = len(subjects)
    if n == 0:
        return [{"duration_minutes": total_minutes, "activity": "Revision"}]

    priorities = [
        compute_priority(s["accuracy"], s["level"], preparation_level)
        for s in subjects
    ]

    # linprog performs MINIMIZATION, so minimize the negative of the
    # priority-weighted time to effectively MAXIMIZE it.
    c = [-p for p in priorities]

    A_ub = [[1] * n]
    b_ub = [working_minutes]

    min_floor = max(int(working_minutes / (n * 3)), 5)
    max_ceiling = max(int(working_minutes * 0.5), min_floor + 5)
    if min_floor * n > working_minutes:
        min_floor = max(int(working_minutes / n / 2), 1)

    bounds = [(min_floor, max_ceiling) for _ in range(n)]

    result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")

    schedule = []
    if result.success:
        allocated = result.x
        for subject, minutes in zip(subjects, allocated):
            schedule.append({
                "duration_minutes": max(int(round(minutes)), 1),
                "activity": subject["subject"],
            })
    else:
        total_priority = sum(priorities) or 1
        for subject, priority in zip(subjects, priorities):
            minutes = max(int(round(working_minutes * (priority / total_priority))), 5)
            schedule.append({"duration_minutes": minutes, "activity": subject["subject"]})

    schedule.sort(key=lambda block: block["duration_minutes"], reverse=True)
    schedule.append({"duration_minutes": revision_minutes, "activity": "Revision"})
    return schedule


@study_planner_bp.route("/study-planner")
def study_planner():
    if "user_id" not in session:
        flash("Please log in to view your study planner.", "warning")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM student_profile WHERE user_id = %s", (user_id,))
    profile = cursor.fetchone()

    if not profile:
        cursor.close()
        conn.close()
        flash("Please complete your profile first so we know your target and available hours.", "info")
        return redirect(url_for("profile_bp.view_profile"))

    available_hours = float(profile["available_study_hours"] or 2)
    preparation_level = profile["preparation_level"] or "Beginner"
    target_recruitment = profile["target_recruitment"]

    cursor.execute(
        """SELECT * FROM diagnostic_results
           WHERE user_id = %s
           ORDER BY taken_at DESC LIMIT 1""",
        (user_id,)
    )
    latest_result = cursor.fetchone()

    subjects = []
    if latest_result:
        cursor.execute(
            "SELECT * FROM weakness_analysis WHERE user_id = %s AND result_id = %s",
            (user_id, latest_result["id"])
        )
        rows = cursor.fetchall()
        for row in rows:
            subjects.append({
                "subject": row["subject"],
                "accuracy": float(row["accuracy"]),
                "level": row["weakness_level"],
            })

    cursor.close()
    conn.close()

    if not subjects:
        flash("Take the diagnostic test and view your weakness analysis first, "
              "so the planner can prioritize your weak topics.", "info")
        return redirect(url_for("diagnostic_test"))

    schedule = optimize_schedule(subjects, available_hours, preparation_level)

    return render_template(
        "study_planner.html",
        schedule=schedule,
        available_hours=available_hours,
        preparation_level=preparation_level,
        target_recruitment=target_recruitment,
        latest_result=latest_result,
    )
