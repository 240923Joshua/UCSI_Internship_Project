import csv,io
from flask import Flask,render_template, request, redirect, url_for, session, jsonify, flash,make_response,abort
from db import get_db, calculate_attendance_percentage
from avatar import get_avatar_response
from hasher import hash_password, verify_password
# from llm import generate_response, build_avatar_prompt, synthesize_speech
from memory import get_last_message, set_last_message
from datetime import date, datetime, timedelta

from sqlite3 import IntegrityError

app = Flask(__name__)
app.secret_key = "d2a0fc31b5ca9b05585d76fd607983601efe4bf8980e10c9a40f13e36a3cb2e3"
@app.route("/")
def home():
    # return "Backend is running"
    return render_template("home.html")

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
    return round(ml_results / internships,2)

@app.route("/attendance/<int:user_id>/<int:internship_id>")
def attendance_percentage(user_id, internship_id):
    db = get_db()

    attendance_percentage = calculate_attendance_percentage(db, user_id, internship_id)

    if attendance_percentage is None:
        return {
            "message": "Attendance data not available yet",
            "user_id": user_id,
            "internship_id": internship_id
        }

    return {
        "user_id": user_id,
        "internship_id": internship_id,
        "attendance_percentage": attendance_percentage
    }

@app.route("/ml-results/<int:user_id>/<int:internship_id>")
def ml_results(user_id, internship_id):
    db = get_db()

    query = """
    SELECT predicted_score, risk_level, recommendation
    FROM ml_results
    WHERE user_id = ? AND internship_id = ?
    ORDER BY created_at DESC
    LIMIT 1;
    """

    result = db.execute(query, (user_id, internship_id)).fetchone()

    if not result:
        return {
            "status": "error",
            "message": "No ML results found"}

    return {
        "user_id": user_id,
        "internship_id": internship_id,
        "predicted_score": result["predicted_score"],
        "risk_level": result["risk_level"],
        "recommendation": result["recommendation"]
    }

@app.route("/avatar/<int:user_id>/<int:internship_id>")
def avatar(user_id, internship_id):
    db = get_db()

    # 1️⃣ Attendance %
    attendance_query = """
    SELECT 
        (SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) * 100.0)
        / COUNT(*) AS attendance_percentage
    FROM attendance
    WHERE user_id = ? AND internship_id = ?;
    """

    attendance_result = db.execute(
        attendance_query, (user_id, internship_id)
    ).fetchone()

    attendance_percentage = calculate_attendance_percentage(db, user_id, internship_id)

    # if attendance_percentage is None:
    #     return {
    #         "avatar_state": "neutral",
    #         "avatar_message": "Attendance data is still being collected.",
    #         "user_id": user_id,
    #         "internship_id": internship_id
    #     }



    # 2️⃣ ML Results
    ml_query = """
    SELECT predicted_score, risk_level
    FROM ml_results
    WHERE user_id = ? AND internship_id = ?
    ORDER BY created_at DESC
    LIMIT 1;
    """

    ml_result = db.execute(
        ml_query, (user_id, internship_id)
    ).fetchone()

    if not ml_result:
        return {
            "avatar_state": "neutral",
            "avatar_message": "Performance prediction not available yet."
        }

    # 3️⃣ Avatar decision
    avatar_response = get_avatar_response(
        attendance_percentage,
        ml_result["risk_level"],
        ml_result["predicted_score"]
    )

    return {
        "user_id": user_id,
        "internship_id": internship_id,
        "attendance_percentage": round(attendance_percentage, 2) if attendance_percentage is not None else None,
        "predicted_score": ml_result["predicted_score"],
        "risk_level": ml_result["risk_level"],
        "avatar_state": avatar_response["state"],
        "avatar_message": avatar_response["message"]
    }

@app.route("/intern/<int:user_id>")
def intern_dashboard(user_id):
    domain=""
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("login"))
    db = get_db()
    cursor = db.execute("SELECT * FROM internship WHERE user_id = ?", (user_id,))
    internships = cursor.fetchall()
    for i in internships:
        domain+=i["domain"]+" • "
    domain = domain[:-3]  # Remove trailing separator
    cursor = db.execute("SELECT * FROM user_details WHERE user_id = ?", (user_id,))
    user_details = cursor.fetchone()
    cursor = db.execute("SELECT * FROM ml_results WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    ml_results = cursor.fetchall()
    return render_template("intern/finalinterndashboard.html", internships=internships[0], user_details=user_details,domain=domain,ml_results=ml_results)

@app.route(
    "/intern/weekly-report/<int:internship_id>/<int:week>",
    methods=["GET", "POST"]
)
def weekly_report(internship_id, week):
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("login"))

    user_id = session["user_id"]
    db = get_db()

    # Ownership check
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

    if existing and existing["status"] == "submitted" and action == "submit":
        flash("Weekly report already submitted for this week.", "warning")
        return redirect(
            url_for("internship_progress", internship_id=internship_id)
        )
    start_date = internship["start_date"]

    # Convert string → date (only once)
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
            if existing["status"] == "submitted":
                flash("Weekly report already submitted for this week.", "warning")
                return redirect(url_for("internship_progress", internship_id=internship_id))

            # UPDATE existing (draft → draft OR draft → submit)
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
            # INSERT brand new
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
            return redirect(url_for("internship_progress", internship_id=internship_id))
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

   

    return render_template(
    "intern/weeklyReport.html",
    internships=all_internships,
    selected_internship_id=internship_id,
    current_week=current_week,
    userdetails=db.execute(
        "SELECT first_name, last_name FROM user_details WHERE user_id = ?",
        (user_id,)
    ).fetchone(),
    domain=domain,
    progress_percentage=myProgressPercentage(db, user_id),
    user_id=user_id,
    due_date=due_date.strftime("%d %b %Y"),
    existing_report=existing_report,
    reportPeriod=reportPeriod,
    attendance_percentage=attendance_percentage,
    skills=skills
)

@app.route("/intern/weekly-report/redirect/<int:internship_id>")
def weekly_report_redirect(internship_id):
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("login"))

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
        "weekly_report",
        internship_id=internship_id,
        week=current_week
    ))

@app.route("/supervisor/<int:supervisor_id>/dashboard")
def supervisor_dashboard(supervisor_id):
    if "user_id" not in session or session.get("role") != "supervisor":
        return redirect(url_for("login"))
    db = get_db()

    query = """
    SELECT
        u.user_id AS intern_id,
        ud.first_name,
        ud.last_name,
        i.internship_id,
        i.title,
        i.domain
    FROM internship i
    JOIN users u ON i.user_id = u.user_id
    JOIN user_details ud ON u.user_id = ud.user_id
    WHERE i.supervisor_id = ?
      AND u.role = 'intern';
    """

    rows = db.execute(query, (supervisor_id,)).fetchall()

    internships = [dict(row) for row in rows]

    return render_template(
        "supervisor_dashboard.html",
        supervisor_id=supervisor_id,
        internships=internships
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    # POST logic starts here
    email = request.form.get("email")
    password = request.form.get("password")

    db = get_db()

    query = """
    SELECT u.user_id, u.password, u.role
    FROM users u
    JOIN user_details ud ON u.user_id = ud.user_id
    WHERE ud.email = ?;
    """

    user = db.execute(query, (email,)).fetchone()

    if not user or not verify_password(user["password"], password):
        return render_template(
            "login.html",
            error="Invalid email or password"
        )

    # Store session
    session["user_id"] = user["user_id"]
    session["role"] = user["role"]

    # Redirect based on role
    if user["role"] == "intern":
        return redirect(url_for("intern_dashboard", user_id=user["user_id"]))

    if user["role"] == "supervisor":
        return redirect(url_for("supervisor_dashboard", supervisor_id=user["user_id"]))

    return "Unknown role", 403

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/<int:user_id>/profile")
def profile(user_id):
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("login"))
    db = get_db()
    month = {'01': 'January', '02': 'February', '03': 'March', '04': 'April',
             '05': 'May', '06': 'June', '07': 'July', '08': 'August',
             '09': 'September', '10': 'October', '11': 'November', '12': 'December'}
    cursor = db.execute("SELECT * FROM user_details WHERE user_id = ?", (user_id,))
    user_details = cursor.fetchone()
    cursor = db.execute("SELECT * FROM internship WHERE user_id = ?", (user_id,))
    internships = cursor.fetchall()
    domain=""
    dates=[]
    internship = db.execute(
        """
        SELECT * FROM internship
        WHERE user_id = ?
        ORDER BY start_date DESC
        LIMIT 1
        """,
        (user_id,)
    ).fetchone()

    if not internship:
        abort(404)

    internship_id = internship["internship_id"]
    start_date = datetime.strptime(
        internship["start_date"], "%Y-%m-%d"
    ).date()

    today = date.today()
    current_week = ((today - start_date).days // 7) + 1
    current_week = max(1, current_week)

    weeklyReportRedirect = {
        "internship_id": internship_id,
        "week": current_week
    }
    print(weeklyReportRedirect)
    for i in internships:
        domain+=i["domain"]+" • "
        start_split = i["start_date"].split("-")
        end_split = i["end_date"].split("-")
        start_formatted = f"{month[start_split[1]]} {int(start_split[2])}, {start_split[0]}"
        end_formatted = f"{month[end_split[1]]} {int(end_split[2])}, {end_split[0]}"
        dates.append(f"{start_formatted} — {end_formatted}")
    domain = domain[:-3]  # Remove trailing separator
    return render_template("intern/final2profile.html", 
    user_details=user_details,
    internships=internships,
    domain=domain,
    dates=dates,
    today=date.today().strftime("%d %b %Y"),
    progress_percentage=myProgressPercentage(db, user_id),
    weeklyReportRedirect=weeklyReportRedirect
    )

@app.route("/intern/export-report/<int:internship_id>")
def export_report(internship_id):
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
        "Week",
        "Attendance %",
        "Focus Skill",
        "Skill Rating",
        "Stress Level",
        "Self Evaluation",
        "Challenges",
        "Next Week Priorities",
        "Submitted At"
    ])

    for r in reports:
        writer.writerow(r)

    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = "attachment; filename=weekly_reports.csv"
    return response


@app.route("/intern/progress")
def internship_progress():
    # Auth check
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("login"))

    user_id = session["user_id"]
    db = get_db()

    # 1. Fetch all internships for this intern
    internships = db.execute(
        "SELECT * FROM internship WHERE user_id = ?",
        (user_id,)
    ).fetchall()
    progress_percentage = myProgressPercentage(db, user_id)
    if not internships:
        # No internships yet
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
        selected_internship = internships[0]
        selected_internship_id = selected_internship["internship_id"]

    # Safety check (ownership)
    if not selected_internship:
        return redirect(url_for("internship_progress"))

    # 3. Fetch user details
    user_details = db.execute(
        "SELECT * FROM user_details WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    # 4. Attendance calculation (SCOPED TO INTERNSHIP)
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

    # 5. Week number calculation
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

    start_date_raw = selected_internship["start_date"]
    start_date = datetime.strptime(
        start_date_raw, "%Y-%m-%d"
    ).date()
    total_weeks = selected_internship["weeks"]
    today = date.today()

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

    # Expected reports up to last completed week
    expected_reports = max(current_week - 1, 0)

    # Outstanding reports (cannot be negative)
    outstanding_reports = max(
        expected_reports - reports_submitted,
        0
    )

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
            previous = recent  # fallback

        recent_avg = sum(recent) / len(recent)
        previous_avg = sum(previous) / len(previous)

        trend_delta = round(recent_avg - previous_avg, 2)

        if trend_delta >= 0.5:
            trend = "improving"
        elif trend_delta <= -0.5:
            trend = "declining"

    skill_trend = list(reversed([
    r["skill_rating"] for r in skill_rows
    ]))

    if skill_trend:
        max_val = max(skill_trend)
        min_val = min(skill_trend)

        if max_val == min_val:
            normalized = [50 for _ in skill_trend]
        else:
            normalized = [
                int((v - min_val) / (max_val - min_val) * 90 + 5)
                for v in skill_trend
            ]
    else:
        normalized = []
    
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
                "action_url": url_for(
                    "weekly_report",
                    internship_id=selected_internship_id,
                    week=week
                )
            })
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

    outstanding_tasks.sort(
        key=lambda t: (priority_order[t["priority"]], t["deadline"])
    )


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
    "skill_trend": skill_trend,
    "skill_trend_normalized": normalized
    }
    if len(skill_trend) < 2:
        progress_stats["skill_trend_normalized"] = []
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
        weeklyReportRedirect=weeklyReportRedirect
    )

@app.route("/intern/skills")
def view_all_skills():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("login"))

    user_id = session["user_id"]
    internship_id = request.args.get("internship_id", type=int)

    if not internship_id:
        abort(400)

    db = get_db()
    skill_stats = get_skill_stats(db, user_id, internship_id)

    return render_template(
        "intern/intern_skills.html",
        skill_stats=skill_stats
    )

@app.route("/intern/reports")
def intern_report_history():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("login"))

    user_id = session["user_id"]
    internship_id = request.args.get("internship_id")

    if not internship_id:
        return redirect(url_for("internship_progress"))

    internship_id = int(internship_id)
    db = get_db()

    # Ownership check
    internship = db.execute(
        "SELECT * FROM internship WHERE internship_id = ? AND user_id = ?",
        (internship_id, user_id)
    ).fetchone()

    if not internship:
        return redirect(url_for("internship_progress"))

    # Fetch reports
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
        "intern/finalreporthistory.html",
        reports=reports,
        internship=internship
    )


@app.route("/avatar/chat", methods=["POST"])
def avatar_chat():
    data = request.json

    user_id = data.get("user_id")
    internship_id = data.get("internship_id")
    user_message = data.get("message")
    db = get_db()

    # Fetch internship domain
    internship = db.execute(
        "SELECT domain FROM internship WHERE internship_id = ?",
        (internship_id,)
    ).fetchone()

    if not internship:
        synthesize_speech("Invalid internship.", output_file="response.wav")
        return jsonify({"reply": "Invalid internship."}), 400

    domain = internship["domain"]

    # Fetch attendance
    attendance_percentage = calculate_attendance_percentage(
        db, user_id, internship_id
    )

    # Fetch ML result
    ml_result = db.execute(
        "SELECT predicted_score, risk_level FROM ml_results WHERE user_id = ? AND internship_id = ?",
        (user_id, internship_id)
    ).fetchone()

    if attendance_percentage is None or not ml_result:
        synthesize_speech("I need more performance data before I can guide you properly.", output_file="response.wav")
        return jsonify({
            "reply": "I need more performance data before I can guide you properly."
        })

    # Build prompt
    prompt = build_avatar_prompt(
        attendance_percentage,
        ml_result["predicted_score"],
        ml_result["risk_level"],
        domain,
        user_message,
        memory=get_last_message(user_id, internship_id)
    )

    # Generate response
    reply = generate_response(prompt)
    # Store last message in memory
    synthesize_speech(reply, output_file="response.wav")
    set_last_message(user_id, internship_id, reply, user_message)

    return jsonify({"reply": reply})


if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
