import csv
import io
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, abort, make_response
from app.db import get_db, calculate_attendance_percentage
from app.utils import (
    get_skill_stats,
    myProgressPercentage,
    calculate_current_week,
    calculate_progress_percentage,
    build_domain_string,
    get_user_internships,
    get_user_details,
    get_active_internships,
    get_attendance_stats,
    get_report_status,
    get_report_due_status,
    get_skill_trend,
    get_outstanding_reports,
    SUBMITTED_STATUSES,
    REPORT_STATUS_DRAFT,
    REPORT_STATUS_SUBMITTED
)
from app.ml_prediction import set_predict

intern_bp = Blueprint('intern', __name__, url_prefix='/intern')

@intern_bp.route("/dashboard")
def intern_dashboard():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("auth.login"))
    
    user_id = session["user_id"]
    db = get_db()
    today = date.today().isoformat()

    # Mark attendance for active internships
    active_internships = get_active_internships(db, user_id, today)
    for internship in active_internships:
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

    # Get user data
    internships = get_user_internships(db, user_id)
    user_details = get_user_details(db, user_id)
    domain = build_domain_string(internships)
    progress_percentage = myProgressPercentage(db, user_id)

    # Get selected internship
    internship_id = request.args.get("internship_id", type=int)
    if internships:
        if not internship_id:
            internship_id = internships[-1]["internship_id"]

    internship = db.execute("""
        SELECT *
        FROM internship
        WHERE internship_id = ? AND user_id = ?
    """, (internship_id, user_id)).fetchone()

    if not internship:
        abort(403)

    today_date = date.today()
    start_date = datetime.strptime(internship["start_date"], "%Y-%m-%d").date()
    end_date = datetime.strptime(internship["end_date"], "%Y-%m-%d").date()

    progressPercentage = calculate_progress_percentage(start_date, end_date)
    total_weeks = internship["weeks"]
    current_week = calculate_current_week(start_date, total_weeks)

    # Get report status
    weekly_status = get_report_status(db, user_id, internship_id, current_week)
    next_due = f"Week {current_week + 1}" if weekly_status == "Submitted" else f"Week {current_week}"

    # Get latest internship for redirect
    latest_internship = db.execute(
        """
        SELECT * FROM internship
        WHERE user_id = ?
        ORDER BY start_date DESC
        LIMIT 1
        """,
        (user_id,)
    ).fetchone()

    latest_start_date = datetime.strptime(latest_internship["start_date"], "%Y-%m-%d").date()
    latest_current_week = calculate_current_week(latest_start_date, latest_internship["weeks"])

    weeklyReportRedirect = {
        "internship_id": latest_internship["internship_id"],
        "week": latest_current_week
    }

    return render_template(
        "intern/dashboard.html",
        internships=internships,
        user_details=user_details,
        domain=domain,
        weeklyReportRedirect=weeklyReportRedirect,
        progress_percentage=progress_percentage,
        active_internship_id=internship_id,
        total_weeks=total_weeks,
        currentWeek=current_week,
        progressPercentage=progressPercentage,
        next_due=next_due,
        weekly_status=weekly_status
    )

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
    current_week = calculate_current_week(start_date, internship["weeks"])

    if week > current_week or week < 1:
        abort(400)

    action = request.form.get("action") if request.method == "POST" else None

    existing = db.execute("""
        SELECT status
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ? AND week_number = ?
    """, (user_id, internship_id, week)).fetchone()

    if existing and existing["status"] in SUBMITTED_STATUSES and action == "submit":
        flash("Weekly report already submitted for this week.", "warning")
        return redirect(
            url_for("intern.internship_progress", internship_id=internship_id)
        )

    # Calculate week period
    week_start = start_date + timedelta(days=(week - 1) * 7)
    week_end = week_start + timedelta(days=6)
    reportPeriod = f"{week_start.strftime('%d %b %Y')} - {week_end.strftime('%d %b %Y')}"

    # Get attendance for this week
    row = db.execute("""
        SELECT
            COUNT(*) as total_days,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days
        FROM attendance
        WHERE user_id = ?
        AND internship_id = ?
        AND date BETWEEN ? AND ?
    """, (user_id, internship_id, week_start, week_end)).fetchone()

    attendance_percentage = (
        round((row["present_days"] / row["total_days"]) * 100)
        if row["total_days"] > 0 else 0
    )

    if request.method == "POST":
        status = REPORT_STATUS_DRAFT if action == "draft" else REPORT_STATUS_SUBMITTED
        
        if existing and existing["status"] in SUBMITTED_STATUSES:
            flash("Weekly report already submitted for this week.", "warning")
            return redirect(url_for("intern.internship_progress", internship_id=internship_id))

        report_data = {
            "attendance_percentage": attendance_percentage,
            "task_description": request.form["task_description"].strip(),
            "focus_skill": request.form["focus_skill"],
            "skill_rating": int(request.form["skill_rating"]),
            "stress_level": int(request.form["stress_level"]),
            "self_evaluation": request.form.get("self_evaluation", ""),
            "challenges": request.form.get("challenges", ""),
            "next_week_priorities": request.form.get("priorities", ""),
            "evidence_link": request.form.get("evidence_link"),
            "status": status,
        }

        if existing:
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
                report_data["attendance_percentage"],
                report_data["task_description"],
                report_data["focus_skill"],
                report_data["skill_rating"],
                report_data["stress_level"],
                report_data["self_evaluation"],
                report_data["challenges"],
                report_data["next_week_priorities"],
                report_data["evidence_link"],
                report_data["status"],
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
                report_data["attendance_percentage"],
                report_data["task_description"],
                report_data["focus_skill"],
                report_data["skill_rating"],
                report_data["stress_level"],
                report_data["self_evaluation"],
                report_data["challenges"],
                report_data["next_week_priorities"],
                report_data["evidence_link"],
                report_data["status"]
            ))
        db.commit()

        if status == REPORT_STATUS_DRAFT:
            flash("Draft saved successfully.", "info")
        else:
            flash("Weekly report submitted successfully!", "success")
            set_predict(user_id, internship_id, db)
            return redirect(url_for("intern.internship_progress", internship_id=internship_id))

    # GET request - prepare form data
    skills = db.execute("""
        SELECT s.name
        FROM skills s
        JOIN domain_skills ds ON ds.skill_id = s.skill_id
        WHERE ds.domain = ?
        ORDER BY s.name
    """, (internship["domain"],)).fetchall()

    internships = get_user_internships(db, user_id)
    domain = build_domain_string(internships)
    due_date = start_date + timedelta(days=current_week * 7)

    all_internships = db.execute(
        "SELECT internship_id, title, domain FROM internship WHERE user_id = ?",
        (user_id,)
    ).fetchall()

    existing_report = db.execute("""
        SELECT *
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ? AND week_number = ?
    """, (user_id, internship_id, week)).fetchone()

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

    current_week = calculate_current_week(start_date, internship["weeks"])

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

    user_details = get_user_details(db, user_id)
    internships = get_user_internships(db, user_id)

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

    latest_start_date = datetime.strptime(
        latest_internship["start_date"], "%Y-%m-%d"
    ).date()

    today = date.today()
    latest_current_week = calculate_current_week(latest_start_date, latest_internship["weeks"])

    weeklyReportRedirect = {
        "internship_id": latest_internship["internship_id"],
        "week": latest_current_week
    }

    # Get selected internship
    selected_id = request.args.get("internship_id", type=int)
    internship = next(
        (i for i in internships if i["internship_id"] == selected_id),
        None
    ) if selected_id else internships[-1]

    startDateConv = datetime.strptime(internship["start_date"], "%Y-%m-%d").date()
    endDateConv = datetime.strptime(internship["end_date"], "%Y-%m-%d").date()

    # Determine status
    if startDateConv <= today <= endDateConv:
        status = "ACTIVE"
    elif today < startDateConv:
        status = "UPCOMING"
    else:
        status = "COMPLETED"

    completion = calculate_progress_percentage(startDateConv, endDateConv)
    internship_id = internship["internship_id"]

    # Get statistics
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

    domain = build_domain_string(internships)

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

    user_details = get_user_details(db, user_id)

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

    internships = get_user_internships(db, user_id)
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

    # Get selected internship
    selected_internship_id = request.args.get("internship_id", type=int) if request.args.get("internship_id") else None
    selected_internship = next(
        (i for i in internships if i["internship_id"] == selected_internship_id),
        None
    ) if selected_internship_id else internships[-1]

    if not selected_internship:
        return redirect(url_for("intern.internship_progress"))

    selected_internship_id = selected_internship["internship_id"]
    user_details = get_user_details(db, user_id)

    # Get attendance statistics
    stats = get_attendance_stats(db, user_id, selected_internship_id)

    start_date = datetime.strptime(
        selected_internship["start_date"], "%Y-%m-%d"
    ).date()

    today = date.today()
    current_week = calculate_current_week(start_date, selected_internship["weeks"])
    total_weeks = selected_internship["weeks"]

    ml_results = db.execute(
        "SELECT * FROM ml_results WHERE user_id = ? AND internship_id = ? ORDER BY created_at DESC",
        (user_id, selected_internship_id)
    ).fetchone()

    # Get report due status
    report_info = get_report_due_status(db, user_id, selected_internship_id, current_week, total_weeks, start_date)

    # Get reports count
    reports_submitted = db.execute("""
        SELECT COUNT(*) AS count
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ?
    """, (user_id, selected_internship_id)).fetchone()["count"]

    outstanding_reports = get_outstanding_reports(db, user_id, selected_internship_id, current_week, start_date)

    domain = build_domain_string(internships)

    # Get skill trend
    trend_data = get_skill_trend(db, user_id, selected_internship_id, current_week)

    skill_stats = get_skill_stats(db, user_id, selected_internship_id)

    # Get outstanding tasks
    submitted_weeks = {row["week_number"] for row in db.execute("""
        SELECT week_number
        FROM weekly_reports
        WHERE user_id = ?
        AND internship_id = ?
    """, (user_id, selected_internship_id)).fetchall()}

    outstanding_tasks = []
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

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

    outstanding_tasks.sort(key=lambda t: (priority_order[t["priority"]], t["deadline"]))

    progress_stats = {
        "present_days": stats["present_days"],
        "absent_days": stats["absent_days"],
        "total_days": stats["total_days"],
        "attendance_percentage": stats["attendance_percentage"],
        "current_week": current_week,
        "reports_submitted": reports_submitted,
        "total_weeks": total_weeks,
        "report_status": report_info["status"],
        "days_until_due": report_info["days_until_due"],
        "outstanding_reports": outstanding_reports,
        "domain": domain,
        "performance_trend": trend_data["trend"],
        "trend_delta": trend_data["trend_delta"],
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
        skill_trend=trend_data["skill_trend"],
        skill_trend_weeks=trend_data["skill_trend_weeks"]
    )

@intern_bp.route("/skills")
def view_all_skills():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    internship_id = request.args.get("internship_id", type=int)

    if not internship_id:
        abort(400)

    db = get_db()
    skill_stats = get_skill_stats(db, user_id, internship_id)

    return render_template(
        "intern/internSkills.html",
        skill_stats=skill_stats,
        previous_page=request.referrer
    )

@intern_bp.route("/reports")
def intern_report_history():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    internship_id = request.args.get("internship_id")

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
        previous_page=request.referrer
    )
