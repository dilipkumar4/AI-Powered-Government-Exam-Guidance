"""
Module 10: AI Weakness Analysis
Uses Scikit-learn's KMeans clustering to group a student's subject-wise
diagnostic accuracy into Weak / Moderate / Strong bands (relative to their
own performance), instead of fixed thresholds.
"""

from flask import Blueprint, render_template, session, redirect, url_for, flash
import mysql.connector
import numpy as np
from sklearn.cluster import KMeans

weakness_bp = Blueprint("weakness_bp", __name__)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "ai_powered_puducherry_government_exam_guidance"
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def classify_weakness(accuracy):
    """Fallback rule-based classification, used when there are too few
    subjects (<3) to form meaningful clusters."""
    if accuracy < 50:
        return "Weak"
    elif accuracy < 75:
        return "Moderate"
    else:
        return "Strong"


def classify_with_kmeans(accuracies):
    """
    Clusters subject accuracies into 3 bands using KMeans.
    Falls back to classify_weakness() if fewer than 3 subjects exist.
    """
    n = len(accuracies)
    if n < 3:
        return [classify_weakness(a) for a in accuracies]

    X = np.array(accuracies).reshape(-1, 1)
    kmeans = KMeans(n_clusters=3, n_init=10, random_state=42)
    cluster_ids = kmeans.fit_predict(X)

    centroids = kmeans.cluster_centers_.flatten()
    order = np.argsort(centroids)
    band_names = ["Weak", "Moderate", "Strong"]
    label_map = {cluster_index: band_names[rank] for rank, cluster_index in enumerate(order)}

    return [label_map[c] for c in cluster_ids]


def parse_subject_breakdown(breakdown_str):
    """
    Parses strings like:
    'General Knowledge: 3/5; Mathematics: 2/5; Reasoning: 4/5'
    into a list of dicts with subject, correct, total, accuracy.
    """
    parsed = []
    if not breakdown_str:
        return parsed

    parts = [p.strip() for p in breakdown_str.split(";") if p.strip()]
    for part in parts:
        try:
            subject, fraction = part.split(":")
            subject = subject.strip()
            correct_str, total_str = fraction.strip().split("/")
            correct, total = int(correct_str), int(total_str)
            accuracy = round((correct / total) * 100, 2) if total else 0
            parsed.append({
                "subject": subject,
                "correct": correct,
                "total": total,
                "accuracy": accuracy,
            })
        except (ValueError, ZeroDivisionError):
            continue
    return parsed


@weakness_bp.route("/weakness-analysis")
def weakness_analysis():
    if "user_id" not in session:
        flash("Please log in to view your weakness analysis.", "warning")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """SELECT * FROM diagnostic_results
           WHERE user_id = %s
           ORDER BY taken_at DESC LIMIT 1""",
        (user_id,)
    )
    latest_result = cursor.fetchone()

    if not latest_result:
        cursor.close()
        conn.close()
        flash("Take the diagnostic test first to see your weakness analysis.", "info")
        return redirect(url_for("diagnostic_test"))

    parsed_subjects = parse_subject_breakdown(latest_result["subject_breakdown"])

    cursor.execute("DELETE FROM weakness_analysis WHERE result_id = %s", (latest_result["id"],))

    accuracies = [item["accuracy"] for item in parsed_subjects]
    levels = classify_with_kmeans(accuracies)

    analysis_rows = []
    for item, level in zip(parsed_subjects, levels):
        cursor.execute(
            """INSERT INTO weakness_analysis
               (user_id, result_id, subject, correct_count, total_count, accuracy, weakness_level)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (user_id, latest_result["id"], item["subject"],
             item["correct"], item["total"], item["accuracy"], level)
        )
        analysis_rows.append({**item, "weakness_level": level})

    conn.commit()
    cursor.close()
    conn.close()

    analysis_rows.sort(key=lambda r: r["accuracy"])

    weak_subjects = [r for r in analysis_rows if r["weakness_level"] == "Weak"]

    return render_template(
        "weakness_analysis.html",
        analysis_rows=analysis_rows,
        weak_subjects=weak_subjects,
        result=latest_result,
    )