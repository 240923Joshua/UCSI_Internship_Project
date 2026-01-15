import csv
import io
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, abort, make_response
from app.db import get_db, calculate_attendance_percentage
from app.utils import get_skill_stats, myProgressPercentage
from app.ml_prediction import set_predict

intern_bp = Blueprint('intern', __name__, url_prefix='/intern')

@intern_bp.route("/dashboard")
def intern_dashboard():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("auth.login"))
    user_id = session["user_id"]
    domain=""
    db = get_db()

    today = date.today().isoformat()

    # 1 Get ALL active internships for this intern
    internships = db.execute("""
        SELECT internship_id
        FROM internship
        WHERE user_id = ?
        AND date(start_date) <= date('now')
        AND date(end_date) >= date('now')
    """, (user_id,)).fetchall()

    # 2 Loop through each active internship
    for internship in internships:
        internship_id = internship["internship_id"]
        already_marked = db.execute("""
            SELECT 1
            FROM attendance
            WHERE user_id = ?
            AND internship_id = ?
            AND date = ?
        """, (user_id, internship_id, today)).fetchone()
        if not already_marked:
            db.execute("""
                INSERT INTO attendance (user_id, internship_id, date, status)
                VALUES (?, ?, ?, 'Present')
            """, (user_id, internship_id, today))
    db.commit()

    cursor = db.execute("SELECT * FROM internship WHERE user_id = ?", (user_id,))
    internships = cursor.fetchall()
    for i in internships:
        domain+=i["domain"]+" • "
    domain = domain[:-3]
    cursor = db.execute("SELECT * FROM user_details WHERE user_id = ?", (user_id,))
    user_details = cursor.fetchone()
    progress_percentage = myProgressPercentage(db, user_id)

    internship_id = request.args.get("internship_id", type=int)
    if internships:
        if not internship_id:
            internship_id = internships[-1]["internship_id"]

    cursor = db.execute("""
    SELECT *
    FROM internship
    WHERE internship_id = ? AND user_id = ?
    """, (internship_id, user_id))

    internship = cursor.fetchone()

    if not internship:
        abort(403)
    today = date.today()
    start = datetime.strptime(internship["start_date"], "%Y-%m-%d").date()
    end = datetime.strptime(internship["end_date"], "%Y-%m-%d").date()

    if today < start:
        progressPercentage = 0
    elif today > end:
        progressPercentage = 100
    else:
        total_days = (end - start).days
        elapsed_days = (today - start).days
        progressPercentage = round((elapsed_days / total_days) * 100)
    total_weeks = internship["weeks"]

    currentWeek = min(
        total_weeks,
        max(1, ((today - start).days // 7) + 1)
    )
    cursor = db.execute("""
        SELECT status
        FROM weekly_reports
        WHERE user_id = ?
        AND internship_id = ?
        AND week_number = ?
    """, (user_id, internship_id, currentWeek))
    report = cursor.fetchone()
    if report is not None and report["status"] in ("submitted", "reviewed"):
        weekly_status = "Submitted"
        next_due = f"Week {currentWeek + 1}"
    else:
        weekly_status = "Pending"
        next_due = f"Week {currentWeek}"

    latest_internship = db.execute(
        """
        SELECT * FROM internship
        WHERE user_id = ?
        ORDER BY start_date DESC
        LIMIT 1
        """,
        (user_id,)
    ).fetchone()

    start_date_latest = datetime.strptime(
        latest_internship["start_date"], "%Y-%m-%d"
    ).date()

    current_week = max(1, ((today - start_date_latest).days // 7) + 1)

    weeklyReportRedirect = {
        "internship_id": latest_internship["internship_id"],
        "week": current_week
    }
    return render_template("intern/dashboard.html", internships=internships, 
    user_details=user_details,domain=domain,weeklyReportRedirect=weeklyReportRedirect,
    progress_percentage=progress_percentage, active_internship_id=internship_id,
    total_weeks=total_weeks, currentWeek=currentWeek,progressPercentage=progressPercentage,
    next_due=next_due,weekly_status=weekly_status)

@intern_bp.route("/weekly-report/<int:internship_id>/<int:week>", methods=["GET", "POST"])
def weekly_report(internship_id, week):
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    db = get_db()

    internship = db.execute(
        "SELECT * FROM internship WHERE internship_id = ? AND user_id = ?",
        (internship_id, user_id)
    ).fetchone()

    if not internship:
        abort(403)
    
    start_date = datetime.strptime(internship["start_date"], "%Y-%m-%d").date()
    today = date.today()
    current_week = ((today - start_date).days // 7) + 1
    current_week = min(current_week, internship["weeks"])

    if week > current_week or week < 1:
        abort(400)

    action = request.form.get("action") if request.method == "POST" else None

    existing = db.execute("""
        SELECT status
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ? AND week_number = ?
    """, (user_id, internship_id, week)).fetchone()
    if existing and (existing["status"] == "submitted" or existing['status'] == 'reviewed') and action == "submit":
        flash("Weekly report already submitted for this week.", "warning")
        return redirect(
            url_for("intern.internship_progress", internship_id=internship_id)
        )
    start_date = internship["start_date"]

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

    week_start = start_date + timedelta(days=(week - 1) * 7)
    week_end = week_start + timedelta(days=6)
    reportPeriod = f"{week_start.strftime('%d %b %Y')} - {week_end.strftime('%d %b %Y')}"
    cursor = db.execute("""
        SELECT
            COUNT(*) as total_days,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days
        FROM attendance
        WHERE user_id = ?
        AND internship_id = ?
        AND date BETWEEN ? AND ?
    """, (user_id, internship_id, week_start, week_end))

    row = cursor.fetchone()

    attendance_percentage = (
        round((row["present_days"] / row["total_days"]) * 100)
        if row["total_days"] > 0 else 0
    )
    if request.method == "POST":
        status = "draft" if action == "draft" else "submitted"
        
        if existing:
            if existing["status"] == "submitted" or existing["status"] == 'reviewed':
                flash("Weekly report already submitted for this week.", "warning")
                return redirect(url_for("intern.internship_progress", internship_id=internship_id))

            db.execute("""
                UPDATE weekly_reports
                SET
                    attendance_percentage = ?,
                    task_description = ?,
                    focus_skill = ?,
                    skill_rating = ?,
                    stress_level = ?,
                    self_evaluation = ?,
                    challenges = ?,
                    next_week_priorities = ?,
                    evidence_link = ?,
                    status = ?
                WHERE user_id = ? AND internship_id = ? AND week_number = ?
            """, (
                attendance_percentage,
                request.form["task_description"].strip(),
                request.form["focus_skill"],
                int(request.form["skill_rating"]),
                int(request.form["stress_level"]),
                request.form.get("self_evaluation", ""),
                request.form.get("challenges", ""),
                request.form.get("priorities", ""),
                request.form.get("evidence_link"),
                status,
                user_id,
                internship_id,
                week
            ))
        else:
            db.execute("""
                INSERT INTO weekly_reports (
                    user_id, internship_id, week_number,
                    attendance_percentage, task_description,
                    focus_skill, skill_rating, stress_level,
                    self_evaluation, challenges,
                    next_week_priorities, evidence_link, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, internship_id, week,
                attendance_percentage,
                request.form["task_description"].strip(),
                request.form["focus_skill"],
                int(request.form["skill_rating"]),
                int(request.form["stress_level"]),
                request.form.get("self_evaluation", ""),
                request.form.get("challenges", ""),
                request.form.get("priorities", ""),
                request.form.get("evidence_link"),
                status
            ))
        db.commit()

        if status == "draft":
            flash("Draft saved successfully.", "info")
        else:
            flash("Weekly report submitted successfully!", "success")
            set_predict(user_id, internship_id, db)
            return redirect(url_for("intern.internship_progress", internship_id=internship_id))
    skills = db.execute("""
    SELECT s.name
    FROM skills s
    JOIN domain_skills ds ON ds.skill_id = s.skill_id
    WHERE ds.domain = ?
    ORDER BY s.name
    """, (internship["domain"],)).fetchall()
    domain=""
    internships = db.execute("""
        SELECT domain
        FROM internship
        WHERE user_id = ?
    """, (user_id,)).fetchall()
    for i in internships:
        domain+=i["domain"]+" • "
    domain = domain[:-3]
    due_date = start_date + timedelta(days=current_week * 7)

    all_internships = db.execute(
    "SELECT internship_id, title, domain FROM internship WHERE user_id = ?",
    (user_id,)).fetchall()

    existing_report = db.execute(
    """
    SELECT *
    FROM weekly_reports
    WHERE user_id = ? AND internship_id = ? AND week_number = ?
    """,(user_id, internship_id, week)).fetchone()

    week_start = start_date + timedelta(days=(week - 1) * 7)
    week_end = week_start + timedelta(days=6)

    can_submit = today >= week_end

    return render_template(
    "intern/weeklyReport.html",
    internships=all_internships,
    selected_internship_id=internship_id,
    current_week=current_week,
    userdetails=db.execute(
        "SELECT first_name, last_name, avatar_url FROM user_details WHERE user_id = ?",
        (user_id,)
    ).fetchone(),
    domain=domain,
    progress_percentage=myProgressPercentage(db, user_id),
    user_id=user_id,
    due_date=due_date.strftime("%d %b %Y"),
    existing_report=existing_report,
    reportPeriod=reportPeriod,
    attendance_percentage=attendance_percentage,
    skills=skills,
    can_submit=can_submit,
    week_end=week_end,
    week=week
)

@intern_bp.route("/weekly-report/redirect/<int:internship_id>")
def weekly_report_redirect(internship_id):
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    db = get_db()

    internship = db.execute(
        "SELECT * FROM internship WHERE internship_id = ? AND user_id = ?",
        (internship_id, user_id)
    ).fetchone()

    if not internship:
        abort(403)

    start_date = datetime.strptime(
        internship["start_date"], "%Y-%m-%d"
    ).date()

    today = date.today()
    current_week = ((today - start_date).days // 7) + 1
    current_week = min(current_week, internship["weeks"])

    return redirect(url_for(
        "intern.weekly_report",
        internship_id=internship_id,
        week=current_week
    ))

@intern_bp.route("/profile")
def profile():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    db = get_db()

    user_details = db.execute(
        "SELECT * FROM user_details WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    internships = db.execute(
        "SELECT * FROM internship WHERE user_id = ?",
        (user_id,)
    ).fetchall()

    if not internships:
        abort(404)

    latest_internship = db.execute(
        """
        SELECT * FROM internship
        WHERE user_id = ?
        ORDER BY start_date DESC
        LIMIT 1
        """,
        (user_id,)
    ).fetchone()

    start_date_latest = datetime.strptime(
        latest_internship["start_date"], "%Y-%m-%d"
    ).date()

    today = date.today()
    current_week = max(1, ((today - start_date_latest).days // 7) + 1)

    weeklyReportRedirect = {
        "internship_id": latest_internship["internship_id"],
        "week": current_week
    }

    selected_id = request.args.get("internship_id", type=int)

    if selected_id:
        internship = next(
            (i for i in internships if i["internship_id"] == selected_id),
            None
        )
    else:
        internship = internships[-1]

    startDateConv = datetime.strptime(internship["start_date"], "%Y-%m-%d").date()
    endDateConv = datetime.strptime(internship["end_date"], "%Y-%m-%d").date()

    if startDateConv <= today <= endDateConv:
        status = "ACTIVE"
    elif today < startDateConv:
        status = "UPCOMING"
    else:
        status = "COMPLETED"

    if today <= startDateConv:
        completion = 0
    elif today >= endDateConv:
        completion = 100
    else:
        total_days = (endDateConv - startDateConv).days
        days_passed = (today - startDateConv).days
        completion = round((days_passed / total_days) * 100, 2)

    internship_id = internship["internship_id"]

    attendance_count = db.execute(
        """
        SELECT COUNT(*) AS total_days
        FROM attendance
        WHERE user_id = ? AND internship_id = ?
        """,
        (user_id, internship_id)
    ).fetchone()["total_days"]

    weekly_report_counts = db.execute(
        """
        SELECT COUNT(*) AS submitted_reports
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ? AND status IN ('submitted','reviewed')
        """,
        (user_id, internship_id)
    ).fetchone()["submitted_reports"]

    skill_count = db.execute(
        """
        SELECT COUNT(DISTINCT focus_skill) AS skill_variety
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ? AND status IN ('submitted','reviewed')
        """,
        (user_id, internship_id)
    ).fetchone()["skill_variety"]

    password_updated = db.execute(
        """
        SELECT password_updated_at
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()["password_updated_at"]

    password_updated = (
        datetime.strptime(password_updated, "%Y-%m-%d").date()
        if password_updated else None
    )

    days_ago = (today - password_updated).days if password_updated else None

    if days_ago is None:
        label = "Not available"
    elif days_ago < 30:
        label = "Less than a month ago"
    elif days_ago < 365:
        label = f"{days_ago // 30} month(s) ago"
    else:
        label = f"{days_ago // 365} year(s) ago"

    counts = {
        "attendance_count": attendance_count,
        "weekly_report_counts": weekly_report_counts,
        "skill_count": skill_count,
        "completion_percentage": completion,
        "password_last_updated": label
    }

    domain = " • ".join(i["domain"] for i in internships)

    supervisor_details = db.execute("""
        SELECT
            ud.user_id,
            ud.first_name,
            ud.last_name,
            ud.email,
            ud.phone_number,
            ud.avatar_url,

            sd.employee_id,
            sd.designation,
            sd.department,
            sd.organization,
            sd.experience_years
        FROM user_details ud
        LEFT JOIN supervisor_details sd
            ON ud.user_id = sd.user_id
        WHERE ud.user_id = ?
    """, (internship['supervisor_id'],)).fetchone()

    return render_template(
        "intern/profile.html",
        user_details=user_details,
        internships=internships,
        selected_internship=internship,
        selected_internship_id=internship["internship_id"],
        domain=domain,
        start_date=startDateConv.strftime("%d %b %Y"),
        end_date=endDateConv.strftime("%d %b %Y"),
        today=today.strftime("%d %b %Y"),
        progress_percentage=myProgressPercentage(db, user_id),
        weeklyReportRedirect=weeklyReportRedirect,
        status=status,
        counts=counts,
        supervisor_details=supervisor_details
    )

@intern_bp.route("/profile/edit", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    db = get_db()

    user_details = db.execute(
        "SELECT * FROM user_details WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    if not user_details:
        abort(404)

    if request.method == "POST":
        first_name = request.form.get("first_name").strip()
        last_name = request.form.get("last_name").strip()
        phone = request.form.get("phone_number").strip()

        if not first_name or not last_name:
            flash("First name and last name are required", "error")
            return redirect(url_for("intern.edit_profile"))

        db.execute(
            """
            UPDATE user_details
            SET first_name = ?, last_name = ?, phone_number = ?
            WHERE user_id = ?
            """,
            (first_name, last_name, phone, user_id)
        )
        db.commit()

        flash("Profile updated successfully", "success")
        return redirect(url_for("intern.profile"))

    return render_template(
        "intern/editProfile.html",
        user_details=user_details
    )

@intern_bp.route("/export-report/<int:internship_id>")
def export_report(internship_id):
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("auth.login"))
        
    user_id = session["user_id"]
    db = get_db()

    reports = db.execute("""
        SELECT
            week_number,
            attendance_percentage,
            focus_skill,
            skill_rating,
            stress_level,
            self_evaluation,
            challenges,
            next_week_priorities,
            submitted_at
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ?
        ORDER BY week_number
    """, (user_id, internship_id)).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Week", "Attendance %", "Focus Skill", "Skill Rating", "Stress Level",
        "Self Evaluation", "Challenges", "Next Week Priorities", "Submitted At"
    ])

    for r in reports:
        writer.writerow(r)

    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = f"attachment; filename=weekly_reports_{internship_id}.csv"
    return response

@intern_bp.route("/progress")
def internship_progress():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    db = get_db()

    internships = db.execute(
        "SELECT * FROM internship WHERE user_id = ?",
        (user_id,)
    ).fetchall()
    progress_percentage = myProgressPercentage(db, user_id)
    if not internships:
        return render_template(
            "intern/internshipProgress.html",
            internships=[],
            selected_internship_id=None,
            user_details=None,
            attendance=None,
            current_week=None,
            progress_percentage=progress_percentage
        )

    selected_internship_id = request.args.get("internship_id")

    if selected_internship_id:
        selected_internship_id = int(selected_internship_id)
        selected_internship = next(
            (i for i in internships if i["internship_id"] == selected_internship_id),
            None
        )
    else:
        selected_internship = internships[-1]
        selected_internship_id = selected_internship["internship_id"]

    if not selected_internship:
        return redirect(url_for("intern.internship_progress"))

    user_details = db.execute(
        "SELECT * FROM user_details WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    present_days = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM attendance
        WHERE user_id = ? AND internship_id = ? AND status = 'Present'
        """,
        (user_id, selected_internship_id)
    ).fetchone()["count"]

    total_days = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM attendance
        WHERE user_id = ? AND internship_id = ?
        """,
        (user_id, selected_internship_id)
    ).fetchone()["count"]

    absent_days = total_days - present_days

    start_date = datetime.strptime(
        selected_internship["start_date"], "%Y-%m-%d"
    ).date()

    ml_results = db.execute(
        "SELECT * FROM ml_results WHERE user_id = ? AND internship_id = ? ORDER BY created_at DESC",
        (user_id, selected_internship_id)
    ).fetchone()

    today = date.today()
    current_week = ((today - start_date).days // 7) + 1
    current_week = min(current_week, selected_internship["weeks"])

    total_weeks = selected_internship["weeks"]

    current_week_report = db.execute(
    """
    SELECT 1
    FROM weekly_reports
    WHERE user_id = ? AND internship_id = ? AND week_number = ?
    """,
        (user_id, selected_internship_id, current_week)
    ).fetchone()

    report_due_date = start_date + timedelta(days=current_week * 7)
    days_until_due = (report_due_date - today).days

    if current_week > total_weeks:
        report_status = "completed"
        days_until_due = None
    elif current_week_report:
        report_status = "submitted"
        days_until_due = None
    elif days_until_due < 0:
        report_status = "overdue"
        days_until_due = abs(days_until_due)
    else:
        report_status = "pending"

    reports_submitted = db.execute(
    """
    SELECT COUNT(*) AS count
    FROM weekly_reports
    WHERE user_id = ? AND internship_id = ?
    """,
    (user_id, selected_internship_id)
    ).fetchone()["count"]

    domain=""
    for i in internships:
        domain+=i["domain"]+" • "
    domain = domain[:-3]

    expected_reports = max(current_week - 1, 0)
    outstanding_reports = max(expected_reports - reports_submitted, 0)

    skill_rows = db.execute(
        """
        SELECT week_number, skill_rating
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ?
        ORDER BY week_number DESC
        LIMIT 6
        """,
        (user_id, selected_internship_id)
    ).fetchall()
   
    trend = "stable"
    trend_delta = 0

    if len(skill_rows) >= 3:
        recent = [r["skill_rating"] for r in skill_rows[:3]]
        if len(skill_rows) >= 6:
            previous = [r["skill_rating"] for r in skill_rows[3:6]]
        else:
            previous = recent
        recent_avg = sum(recent) / len(recent)
        previous_avg = sum(previous) / len(previous)
        trend_delta = round(recent_avg - previous_avg, 2)
        if trend_delta >= 0.5:
            trend = "improving"
        elif trend_delta <= -0.5:
            trend = "declining"

    skill_trend = list(reversed([r["skill_rating"] for r in skill_rows]))
    skill_trend_weeks = list(range(current_week - len(skill_trend) + 1, current_week + 1))

    skill_stats = get_skill_stats(db, user_id, selected_internship_id)

    cursor = db.execute("""
        SELECT week_number
        FROM weekly_reports
        WHERE user_id = ?
        AND internship_id = ?
    """, (user_id, selected_internship_id))

    submitted_weeks = {row["week_number"] for row in cursor.fetchall()}

    outstanding_tasks = []

    for week in range(1, current_week + 1):
        if week not in submitted_weeks:
            due_date = start_date + timedelta(days=week * 7)
            if due_date < today:
                priority = "HIGH"
            elif (due_date - today).days <= 3:
                priority = "MEDIUM"
            else:
                priority = "LOW"
            outstanding_tasks.append({
                "task_name": f"Weekly Report: Week {week}",
                "deadline": due_date,
                "priority": priority,
                "status": "Not Started",
                "action_url": url_for("intern.weekly_report", internship_id=selected_internship_id, week=week)
            })
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    outstanding_tasks.sort(key=lambda t: (priority_order[t["priority"]], t["deadline"]))

    progress_stats = {
        "present_days": present_days,
        "absent_days": absent_days,
        "total_days": total_days,
        "attendance_percentage": round((present_days / total_days) * 100, 2) if total_days > 0 else 0,
        "current_week": current_week,
        "reports_submitted": reports_submitted,
        "total_weeks": selected_internship["weeks"],
        "report_status": report_status,
        "days_until_due": days_until_due,
        "outstanding_reports": outstanding_reports,
        "domain": domain,
        "performance_trend": trend,
        "trend_delta": trend_delta,
    }
    weeklyReportRedirect = {
        "internship_id": selected_internship_id,
        "week": current_week
    }
    return render_template(
        "intern/internshipProgress.html",
        internships=internships,
        selected_internship_id=selected_internship_id,
        selected_internship=selected_internship,
        progress_stats=progress_stats,
        user_details=user_details,
        user_id=user_id,
        ml_results=ml_results,
        skill_stats=skill_stats,
        outstanding_tasks=outstanding_tasks,
        progress_percentage=progress_percentage,
        weeklyReportRedirect=weeklyReportRedirect,
        skill_trend=skill_trend,
        skill_trend_weeks=skill_trend_weeks
    )

@intern_bp.route("/skills")
def view_all_skills():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    previous_page = request.referrer
    internship_id = request.args.get("internship_id", type=int)

    if not internship_id:
        abort(400)

    db = get_db()
    skill_stats = get_skill_stats(db, user_id, internship_id)

    return render_template(
        "intern/internSkills.html",
        skill_stats=skill_stats,
        previous_page=previous_page
    )

@intern_bp.route("/reports")
def intern_report_history():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    internship_id = request.args.get("internship_id")
    previous_page = request.referrer
    if not internship_id:
        return redirect(url_for("intern.internship_progress"))

    internship_id = int(internship_id)
    db = get_db()

    internship = db.execute(
        "SELECT * FROM internship WHERE internship_id = ? AND user_id = ?",
        (internship_id, user_id)
    ).fetchone()

    if not internship:
        return redirect(url_for("intern.internship_progress"))

    reports = db.execute(
        """
        SELECT *
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ?
        ORDER BY week_number ASC
        """,
        (user_id, internship_id)
    ).fetchall()

    return render_template(
        "intern/reportHistory.html",
        reports=reports,
        internship=internship,
        previous_page=previous_page
    )
