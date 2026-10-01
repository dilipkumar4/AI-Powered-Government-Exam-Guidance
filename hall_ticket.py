"""
Module 19: Smart Hall Ticket Alert
------------------------------------------------------------------
Flow (matches the workflow diagram):
  Candidate registers/selects a recruitment
    -> "Official Source Monitoring" checks whether the hall ticket
       has been released
    -> If released: database updated, email sent to every registered
       candidate
    -> If not released: nothing happens yet, checked again later
  Candidate logs in and downloads the hall ticket once released.

NOTE ON "Official Source Monitoring":
This project has no access to Puducherry's real recruitment site's
internal API/structure, so live scraping isn't implemented here.
Instead, `check_official_source()` is the single function that
represents that step. Right now it just reads the `is_released`
flag an admin sets via /admin/hall-ticket/<id>. In a real deployment,
you would replace the body of that one function with actual scraping
or an official API call -- nothing else in this module would need
to change.
"""

from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from flask_mail import Message
import mysql.connector

hall_ticket_bp = Blueprint("hall_ticket_bp", __name__)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "ai_powered_puducherry_government_exam_guidance"
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


# ---------------------------------------------------------------
# "Official Source Monitoring" step (see note above)
# ---------------------------------------------------------------
def check_official_source(recruitment_id):
    """
    Returns True if the hall ticket is released, False otherwise.
    Currently reads the DB flag set by an admin. Replace this
    function's body with real scraping/API logic later if needed.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM hall_tickets WHERE recruitment_id = %s", (recruitment_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return bool(row and row["is_released"])


def notify_registered_candidates(app, recruitment_id):
    """
    "Email Notification Sent" step. Sends one email to every
    candidate registered for this recruitment who hasn't already
    been notified (hall_ticket_notifications prevents duplicates).
    """
    from app import mail  # imported here to avoid circular import at module load

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM recruitments WHERE id = %s", (recruitment_id,))
    recruitment = cursor.fetchone()

    cursor.execute(
        """SELECT u.user_id, u.name, u.email
           FROM recruitment_registrations rr
           JOIN users u ON u.user_id = rr.user_id
           WHERE rr.recruitment_id = %s""",
        (recruitment_id,)
    )
    candidates = cursor.fetchall()

    sent_count = 0
    for candidate in candidates:
        cursor.execute(
            "SELECT * FROM hall_ticket_notifications WHERE user_id = %s AND recruitment_id = %s",
            (candidate["user_id"], recruitment_id)
        )
        already_sent = cursor.fetchone()
        if already_sent:
            continue

        try:
            msg = Message(
                subject=f"Hall Ticket Released: {recruitment['title']}",
                recipients=[candidate["email"]],
                body=(
                    f"Dear {candidate['name']},\n\n"
                    f"The hall ticket for \"{recruitment['title']}\" has been released.\n"
                    f"Log in to the Puducherry Recruitment Portal and visit "
                    f"the recruitment's Hall Ticket page to download it.\n\n"
                    f"Good luck!"
                ),
            )
            mail.send(msg)

            cursor.execute(
                "INSERT INTO hall_ticket_notifications (user_id, recruitment_id) VALUES (%s, %s)",
                (candidate["user_id"], recruitment_id)
            )
            conn.commit()
            sent_count += 1
        except Exception as e:
            # Don't let one failed email break the whole batch
            print(f"Failed to email {candidate['email']}: {e}")

    cursor.close()
    conn.close()
    return sent_count


# ---------------------------------------------------------------
# Candidate-facing routes
# ---------------------------------------------------------------
@hall_ticket_bp.route("/recruitments/<int:recruitment_id>/notify-me", methods=["POST"])
def register_for_alert(recruitment_id):
    """Candidate registers/selects a recruitment to be alerted for."""
    if "user_id" not in session:
        flash("Please log in to register for hall ticket alerts.", "warning")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO recruitment_registrations (user_id, recruitment_id) VALUES (%s, %s)",
            (user_id, recruitment_id)
        )
        conn.commit()
        flash("You're registered! We'll email you the moment the hall ticket is released.", "success")
    except mysql.connector.errors.IntegrityError:
        flash("You're already registered for alerts on this recruitment.", "info")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("recruitment.recruitment_detail", recruitment_id=recruitment_id))


@hall_ticket_bp.route("/recruitments/<int:recruitment_id>/hall-ticket")
def view_hall_ticket(recruitment_id):
    """Candidate logs in and checks/downloads their hall ticket."""
    if "user_id" not in session:
        flash("Please log in to view your hall ticket.", "warning")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM recruitments WHERE id = %s", (recruitment_id,))
    recruitment = cursor.fetchone()
    cursor.execute("SELECT * FROM hall_tickets WHERE recruitment_id = %s", (recruitment_id,))
    hall_ticket = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template(
        "hall_ticket.html",
        recruitment=recruitment,
        hall_ticket=hall_ticket,
    )


# ---------------------------------------------------------------
# Admin route: simulates the "Official Source Monitoring" detecting
# a release, and drives the Database Updated -> Email Sent steps.
# ---------------------------------------------------------------
@hall_ticket_bp.route("/admin/hall-ticket/<int:recruitment_id>", methods=["GET", "POST"])
def admin_hall_ticket(recruitment_id):
    if not session.get("is_admin"):
        flash("Admin access only.", "danger")
        return redirect(url_for("login"))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM recruitments WHERE id = %s", (recruitment_id,))
    recruitment = cursor.fetchone()

    if request.method == "POST":
        link = request.form.get("hall_ticket_link", "").strip()

        cursor.execute("SELECT * FROM hall_tickets WHERE recruitment_id = %s", (recruitment_id,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                """UPDATE hall_tickets
                   SET is_released = TRUE, released_at = NOW(),
                       hall_ticket_link = %s, last_checked_at = NOW()
                   WHERE recruitment_id = %s""",
                (link, recruitment_id)
            )
        else:
            cursor.execute(
                """INSERT INTO hall_tickets
                   (recruitment_id, is_released, released_at, hall_ticket_link)
                   VALUES (%s, TRUE, NOW(), %s)""",
                (recruitment_id, link)
            )
        conn.commit()
        cursor.close()
        conn.close()

        # "Hall Ticket Released?" -> Yes -> Database Updated -> Email Notification Sent
        from flask import current_app
        sent_count = notify_registered_candidates(current_app, recruitment_id)

        flash(f"Hall ticket marked released. Notified {sent_count} candidate(s).", "success")
        return redirect(url_for("hall_ticket_bp.admin_hall_ticket", recruitment_id=recruitment_id))

    cursor.execute("SELECT * FROM hall_tickets WHERE recruitment_id = %s", (recruitment_id,))
    hall_ticket = cursor.fetchone()
    cursor.execute(
        "SELECT COUNT(*) AS cnt FROM recruitment_registrations WHERE recruitment_id = %s",
        (recruitment_id,)
    )
    registration_count = cursor.fetchone()["cnt"]
    cursor.close()
    conn.close()

    return render_template(
        "admin_hall_ticket.html",
        recruitment=recruitment,
        hall_ticket=hall_ticket,
        registration_count=registration_count,
    )