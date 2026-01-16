import os
from flask import current_app
from datetime import datetime, timedelta, date

# ==================== CONSTANTS ====================
REPORT_STATUS_DRAFT = "draft"
REPORT_STATUS_SUBMITTED = "submitted"
REPORT_STATUS_REVIEWED = "reviewed"
SUBMITTED_STATUSES = (REPORT_STATUS_SUBMITTED, REPORT_STATUS_REVIEWED)

def allowed_file(filename):
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def get_skill_stats(db, user_id, internship_id):
    cursor = db.execute("""
        SELECT focus_skill, skill_rating
        FROM weekly_reports
        WHERE user_id = ?
          AND internship_id = ?
          AND skill_rating IS NOT NULL
    """, (user_id, internship_id))

    rows = cursor.fetchall()

    skills = {}

    for row in rows:
        skill = row["focus_skill"]
        rating = row["skill_rating"]

        skills.setdefault(skill, []).append(rating)

    skill_stats = []

    for skill, ratings in skills.items():
        avg = sum(ratings) / len(ratings)
        percentage = round((avg / 10) * 100)

        if avg >= 8:
            level = "Advanced"
        elif avg >= 6:
            level = "Intermediate"
        else:
            level = "Developing"

        skill_stats.append({
            "name": skill,
            "avg": round(avg, 1),
            "percentage": percentage,
            "level": level,
            "reports": len(ratings)
        })

    skill_stats.sort(key=lambda x: x["percentage"], reverse=True)
    return skill_stats

def myProgressPercentage(db, user_id):
    internships = db.execute("""
    SELECT COUNT(internship_id) AS total_internships
    FROM internship
    WHERE user_id = ?
    """, (user_id,)).fetchone()["total_internships"]
    
    ml_results = db.execute("""
    SELECT SUM(predicted_score) AS total_score
    FROM ml_results
    WHERE user_id = ?
    """, (user_id,)).fetchone()["total_score"]
    
    if internships == 0:
        return 0
    ml_results = ml_results if ml_results else 0
    return round(ml_results / internships, 2)


# ==================== DATE & TIME HELPERS ====================
def calculate_current_week(start_date, total_weeks):
    """Calculate the current week number based on start date."""
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    today = date.today()
    current_week = ((today - start_date).days // 7) + 1
    return min(current_week, total_weeks)


def calculate_progress_percentage(start_date, end_date):
    """Calculate internship progress percentage based on current date."""
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    today = date.today()
    if today < start_date:
        return 0
    elif today > end_date:
        return 100
    else:
        total_days = (end_date - start_date).days
        elapsed_days = (today - start_date).days
        return round((elapsed_days / total_days) * 100)


def build_domain_string(internships):
    """Build domain string from internships list."""
    domains = [i["domain"] for i in internships]
    return " • ".join(domains)


# ==================== DATABASE QUERY HELPERS ====================
def get_user_internships(db, user_id):
    """Fetch all internships for a user."""
    return db.execute(
        "SELECT * FROM internship WHERE user_id = ?",
        (user_id,)
    ).fetchall()


def get_user_details(db, user_id):
    """Fetch user details."""
    return db.execute(
        "SELECT * FROM user_details WHERE user_id = ?",
        (user_id,)
    ).fetchone()


def get_active_internships(db, user_id, today=None):
    """Fetch active internships for a user on a given date."""
    if today is None:
        today = date.today().isoformat()
    
    return db.execute("""
        SELECT internship_id
        FROM internship
        WHERE user_id = ?
        AND date(start_date) <= date(?)
        AND date(end_date) >= date(?)
    """, (user_id, today, today)).fetchall()


def get_attendance_stats(db, user_id, internship_id):
    """Get attendance statistics for an internship."""
    present_days = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM attendance
        WHERE user_id = ? AND internship_id = ? AND status = 'Present'
        """,
        (user_id, internship_id)
    ).fetchone()["count"]

    total_days = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM attendance
        WHERE user_id = ? AND internship_id = ?
        """,
        (user_id, internship_id)
    ).fetchone()["count"]

    absent_days = total_days - present_days
    attendance_percentage = round((present_days / total_days) * 100, 2) if total_days > 0 else 0

    return {
        "present_days": present_days,
        "absent_days": absent_days,
        "total_days": total_days,
        "attendance_percentage": attendance_percentage
    }


def get_report_status(db, user_id, internship_id, week):
    """Determine report status for a specific week."""
    report = db.execute("""
        SELECT status
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ? AND week_number = ?
    """, (user_id, internship_id, week)).fetchone()

    if report and report["status"] in SUBMITTED_STATUSES:
        return "Submitted"
    return "Pending"


def get_report_due_status(db, user_id, internship_id, current_week, total_weeks, start_date):
    """Calculate overall report submission status and days until due."""
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    
    today = date.today()
    report_due_date = start_date + timedelta(days=current_week * 7)
    days_until_due = (report_due_date - today).days

    current_week_report = db.execute("""
        SELECT 1
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ? AND week_number = ?
    """, (user_id, internship_id, current_week)).fetchone()

    if current_week > total_weeks:
        status = "completed"
        days_until_due = None
    elif current_week_report:
        status = "submitted"
        days_until_due = None
    elif days_until_due < 0:
        status = "overdue"
        days_until_due = abs(days_until_due)
    else:
        status = "pending"

    return {
        "status": status,
        "days_until_due": days_until_due,
        "due_date": report_due_date
    }


def get_skill_trend(db, user_id, internship_id, current_week):
    """Get recent skill trend data."""
    skill_rows = db.execute(
        """
        SELECT week_number, skill_rating
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ?
        ORDER BY week_number DESC
        LIMIT 6
        """,
        (user_id, internship_id)
    ).fetchall()

    trend = "stable"
    trend_delta = 0

    if len(skill_rows) >= 3:
        recent = [r["skill_rating"] for r in skill_rows[:3]]
        previous = [r["skill_rating"] for r in skill_rows[3:6]] if len(skill_rows) >= 6 else recent
        recent_avg = sum(recent) / len(recent)
        previous_avg = sum(previous) / len(previous)
        trend_delta = round(recent_avg - previous_avg, 2)
        
        if trend_delta >= 0.5:
            trend = "improving"
        elif trend_delta <= -0.5:
            trend = "declining"

    skill_trend = list(reversed([r["skill_rating"] for r in skill_rows]))
    skill_trend_weeks = list(range(current_week - len(skill_trend) + 1, current_week + 1))

    return {
        "trend": trend,
        "trend_delta": trend_delta,
        "skill_trend": skill_trend,
        "skill_trend_weeks": skill_trend_weeks
    }


def get_outstanding_reports(db, user_id, internship_id, current_week, start_date):
    """Get count of outstanding reports."""
    reports_submitted = db.execute("""
        SELECT COUNT(*) AS count
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ?
    """, (user_id, internship_id)).fetchone()["count"]

    expected_reports = max(current_week - 1, 0)
    outstanding_reports = max(expected_reports - reports_submitted, 0)

    return outstanding_reports
