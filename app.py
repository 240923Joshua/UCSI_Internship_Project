import csv,io,os
from flask import Flask,render_template, request, redirect, url_for, session, jsonify, flash,make_response,abort
from db import get_db, calculate_attendance_percentage
from hasher import hash_password, verify_password
from llm import generate_response, build_avatar_prompt, synthesize_speech
from memory import get_last_message, set_last_message
from datetime import date, datetime, timedelta
from werkzeug.utils import secure_filename
from collections import defaultdict
from sqlite3 import IntegrityError

app = Flask(__name__)
app.secret_key = "d2a0fc31b5ca9b05585d76fd607983601efe4bf8980e10c9a40f13e36a3cb2e3"
UPLOAD_FOLDER = 'static/uploads/avatars'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def home():
    return redirect(url_for('login'))

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


@app.route("/intern/dashboard")
def intern_dashboard():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("login"))
    user_id = session["user_id"]
    domain=""
    db = get_db()

    today = date.today().isoformat()

    # 1️⃣ Get ALL active internships for this intern
    internships = db.execute("""
        SELECT internship_id
        FROM internship
        WHERE user_id = ?
        AND date(start_date) <= date('now')
        AND date(end_date) >= date('now')
    """, (user_id,)).fetchall()

    # 2️⃣ Loop through each active internship
    for internship in internships:
        internship_id = internship["internship_id"]

        # Check if attendance already marked today
        already_marked = db.execute("""
            SELECT 1
            FROM attendance
            WHERE user_id = ?
            AND internship_id = ?
            AND date = ?
        """, (user_id, internship_id, today)).fetchone()

        # 3️⃣ Auto-mark Present if not exists
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
    domain = domain[:-3]  # Remove trailing separator
    cursor = db.execute("SELECT * FROM user_details WHERE user_id = ?", (user_id,))
    user_details = cursor.fetchone()
    progress_percentage = myProgressPercentage(db, user_id)

    internship_id = request.args.get("internship_id", type=int)
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

    if report and report["status"] == "submitted":
        weekly_status = "Submitted"
        next_due = f"Week {currentWeek + 1}"
    else:
        weekly_status = "Pending"
        next_due = f"Week {currentWeek}"
    # --------------------------------------------------
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
    # --------------------------------------------------
    return render_template("intern/dashboard.html", internships=internships, 
    user_details=user_details,domain=domain,weeklyReportRedirect=weeklyReportRedirect,
    progress_percentage=progress_percentage, active_internship_id=internship_id,
    total_weeks=total_weeks, currentWeek=currentWeek,progressPercentage=progressPercentage,
    next_due=next_due,weekly_status=weekly_status)
   

# @app.route("/flash-test")
# def flash_test():
#     flash("This is a test flash message!", "success")
#     return redirect(url_for("avatar_page"))

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
    if existing and (existing["status"] == "submitted" or existing['status'] == 'reviewed') and action == "submit":
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
            if existing["status"] == "submitted" or existing["status"] == 'reviewed':
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
    week_end=week_end
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

@app.route("/supervisor/dashboard")
def supervisor_dashboard():
    if "user_id" not in session or session.get("role") != "supervisor":
        return redirect(url_for("login"))
    supervisor_id = session["user_id"]
    db = get_db()
    interns = db.execute("""
    SELECT
        u.user_id,
        ud.first_name || ' ' || ud.last_name AS name,
        i.domain
    FROM internship i
    JOIN users u ON u.user_id = i.user_id
    JOIN user_details ud ON ud.user_id = u.user_id
    WHERE i.supervisor_id = ?
    """, (supervisor_id,)).fetchall()
    total_interns = len(interns)

    submitted_reports = db.execute("""
        SELECT COUNT(*)
        FROM weekly_reports wr
        JOIN internship i ON i.internship_id = wr.internship_id
        WHERE i.supervisor_id = ?
          AND wr.status = 'submitted'
    """, (supervisor_id,)).fetchone()[0]

    pending_reviews = submitted_reports
    
    recent_reports = db.execute("""
    SELECT
        wr.report_id,
        ud.first_name || ' ' || ud.last_name AS intern_name,
        wr.week_number,
        i.domain,
        wr.submitted_at
    FROM weekly_reports wr
    JOIN internship i ON i.internship_id = wr.internship_id
    JOIN user_details ud ON ud.user_id = i.user_id
    WHERE i.supervisor_id = ?
      AND wr.status = 'submitted'
    ORDER BY wr.submitted_at DESC
    LIMIT 5
    """, (supervisor_id,)).fetchall() 

    active_internships = db.execute("""
    SELECT COUNT(*) AS active_internships
    FROM internship
    WHERE supervisor_id = ?
      AND start_date <= DATE('now')
      AND end_date >= DATE('now')
    """, (supervisor_id,)).fetchone()["active_internships"]

    top_intern = db.execute("""
    SELECT
        ud.user_id,
        ud.first_name || ' ' || ud.last_name AS intern_name,
        i.domain, ud.avatar_url,
        COUNT(wr.report_id) AS report_count
    FROM weekly_reports wr
    JOIN internship i ON i.internship_id = wr.internship_id
    JOIN user_details ud ON ud.user_id = i.user_id
    WHERE i.supervisor_id = ?
      AND wr.status = 'submitted'
    GROUP BY i.user_id
    ORDER BY report_count DESC
    LIMIT 1
    """, (supervisor_id,)).fetchone()

    supervisor_weeklyReportRedirect = db.execute("""
        SELECT internship_id 
        FROM internship
        WHERE supervisor_id = ?
        ORDER BY internship_id DESC
        LIMIT 1
    """, (supervisor_id,)).fetchone()[0]

    supervisor_details = db.execute("""
    SELECT * from user_details
    WHERE user_id = ?
    """, (supervisor_id,)).fetchone()
    return render_template("supervisor/supervisorDashboard.html", interns=interns, total_interns=total_interns,
    supervisor_details=supervisor_details,submitted_reports=submitted_reports,pending_reviews=pending_reviews,
    recent_reports=recent_reports,active_internships=active_internships,top_intern=top_intern,
    supervisor_weeklyReportRedirect=supervisor_weeklyReportRedirect)

@app.route("/supervisor/report/<int:report_id>")
def supervisor_view_report(report_id):
    if "user_id" not in session or session.get("role") != "supervisor":
        return redirect(url_for("login"))

    supervisor_id = session["user_id"]
    db = get_db()

    cursor = db.execute("""
        SELECT
            wr.report_id,
            wr.week_number,
            wr.task_description,
            wr.focus_skill,
            wr.skill_rating,
            wr.stress_level,
            wr.self_evaluation,
            wr.challenges,
            wr.next_week_priorities,
            wr.evidence_link,
            wr.submitted_at,
            ud.first_name || ' ' || ud.last_name AS intern_name,
            i.domain
        FROM weekly_reports wr
        JOIN internship i ON i.internship_id = wr.internship_id
        JOIN user_details ud ON ud.user_id = i.user_id
        WHERE wr.report_id = ?
          AND i.supervisor_id = ?
          AND wr.status = 'submitted'
    """, (report_id, supervisor_id))

    report = cursor.fetchone()

    if report is None:
        return redirect(url_for("supervisor_dashboard"))

    return render_template(
        "supervisor/viewWeeklyReport.html",
        report=report
    )

@app.route("/supervisor/interns")
def supervisor_interns():
    if "user_id" not in session or session.get('role') != "supervisor":
        return redirect(url_for('login'))
    supervisor_id = session['user_id']
    db = get_db()

    search = request.args.get("q", "").strip()
    domain = request.args.get("domain", "").strip()

    query = """
        SELECT
            i.user_id AS user_id,
            ud.first_name || ' ' || ud.last_name AS intern_name,
            ud.email,
            ud.avatar_url,
            i.domain,
            i.start_date,
            i.end_date,
            i.internship_id,

            -- Attendance %
            MIN(
            ROUND(
                (
                SELECT COUNT(*)
                FROM attendance a
                WHERE a.user_id = i.user_id
                    AND a.status = 'Present'
                ) * 100.0 /
                NULLIF(
                (SELECT COUNT(*) FROM attendance a2 WHERE a2.user_id = i.user_id),
                0
                ),
                0
            ),
            100
            ) AS attendance_percent,

            -- Reports submitted %
            MIN(
            ROUND(
                (
                SELECT COUNT(*)
                FROM weekly_reports wr
                WHERE wr.internship_id = i.internship_id
                    AND wr.status = 'submitted'
                ) * 100.0 /
                NULLIF(
                (JULIANDAY('now') - JULIANDAY(i.start_date)) / 7,
                0
                ),
                0
            ),
            100
            ) AS reports_percent,

            -- Skill rating avg %
            MIN(
            ROUND(
                (
                SELECT AVG(
                    CASE
                    WHEN wr2.skill_rating > 5 THEN 5
                    ELSE wr2.skill_rating
                    END
                )
                FROM weekly_reports wr2
                WHERE wr2.internship_id = i.internship_id
                    AND wr2.skill_rating IS NOT NULL
                ) * 20,
                0
            ),
            100
            ) AS skill_percent,

            CASE
                WHEN i.start_date <= DATE('now') AND i.end_date >= DATE('now')
                THEN 'Active'
                ELSE 'Completed'
            END AS status

        FROM internship i
        JOIN user_details ud ON ud.user_id = i.user_id
        WHERE i.supervisor_id = ?
        """

    params = [supervisor_id]
    if search:
        query += """
            AND (
                ud.first_name LIKE ?
                OR ud.last_name LIKE ?
                OR (ud.first_name || ' ' || ud.last_name) LIKE ?
                OR (ud.last_name || ' ' || ud.first_name) LIKE ?
                OR ud.email LIKE ?
                OR i.domain LIKE ?
            )
        """
        like = f"%{search}%"
        params.extend([like, like, like, like, like, like])

    if domain:
        query += " AND i.domain = ?"
        params.append(domain)

    query += " ORDER BY ud.first_name"

    interns = db.execute(query, params).fetchall()

    supervisor_details = db.execute("""
    SELECT * FROM user_details
    WHERE user_id = ?
    """, (supervisor_id,)).fetchone()

    domains = db.execute("""
        SELECT DISTINCT domain
        FROM internship
        WHERE supervisor_id = ?
    """, (supervisor_id,)).fetchall()

    domains = [d["domain"] for d in domains]

    supervisor_weeklyReportRedirect = db.execute("""
        SELECT internship_id 
        FROM internship
        WHERE supervisor_id = ?
        ORDER BY internship_id DESC
        LIMIT 1
    """, (supervisor_id,)).fetchone()[0]
    return render_template('supervisor/supervisorInterns.html',supervisor_details=supervisor_details,interns=interns,domains=domains,
    supervisor_weeklyReportRedirect=supervisor_weeklyReportRedirect)

@app.route("/supervisor/intern/<int:intern_id>")
def supervisor_view_intern(intern_id):
    if "user_id" not in session or session.get("role") != "supervisor":
        return redirect(url_for("login"))

    supervisor_id = session["user_id"]
    db = get_db()
    previous_page = request.referrer
    cursor = db.execute("""
        SELECT
            ud.first_name || ' ' || ud.last_name AS intern_name,
            ud.email,
            i.domain,
            i.start_date,
            i.end_date,
            ud.avatar_url as avatar_url,

            -- Attendance %
            ROUND(
              (
                SELECT COUNT(*)
                FROM attendance a
                WHERE a.user_id = i.user_id
                  AND a.status = 'Present'
              ) * 100.0 /
              NULLIF(
                (SELECT COUNT(*) FROM attendance a2 WHERE a2.user_id = i.user_id),
                0
              ),
              0
            ) AS attendance_percent,

            -- Reports %
            MIN(
              ROUND(
                (
                  SELECT COUNT(*)
                  FROM weekly_reports wr
                  WHERE wr.internship_id = i.internship_id
                    AND wr.status = 'submitted'
                ) * 100.0 /
                NULLIF(
                  (JULIANDAY('now') - JULIANDAY(i.start_date)) / 7,
                  0
                ),
                0
              ),
              100
            ) AS reports_percent,

            -- Skill %
            MIN(
              ROUND(
                (
                  SELECT AVG(
                    CASE
                      WHEN wr2.skill_rating > 5 THEN 5
                      ELSE wr2.skill_rating
                    END
                  )
                  FROM weekly_reports wr2
                  WHERE wr2.internship_id = i.internship_id
                ) * 20,
                0
              ),
              100
            ) AS skill_percent

        FROM internship i
        JOIN user_details ud ON ud.user_id = i.user_id
        WHERE i.user_id = ?
          AND i.supervisor_id = ?
    """, (intern_id, supervisor_id))

    intern = cursor.fetchone()

    if intern is None:
        return redirect(url_for("supervisor_interns"))

    return render_template(
        "supervisor/viewInternProfile.html",
        intern=intern,
        previous_page=previous_page
    )

@app.route("/supervisor/weekly-reports/<int:internship_id>", methods=['GET','POST'])
def supervisor_weeklyreports(internship_id):
    if "user_id" not in session or session.get('role') != 'supervisor':
        return redirect(url_for('login'))
    supervisor_id = session['user_id']
    db = get_db()
    prev_week = None
    next_week = None
    if request.method == "POST":
        report_id = request.form.get("report_id")
        feedback = request.form.get("feedback")

        if not report_id:
            flash("Invalid report action", "error")
            return redirect(url_for(
                "supervisor_weeklyreports",
                internship_id=internship_id
            ))

        db.execute("""
            UPDATE weekly_reports
            SET
                status = 'reviewed',
                supervisor_feedback = ?,
                reviewed_at = DATETIME('now')
            WHERE report_id = ?
            AND internship_id = ?
        """, (feedback, report_id, internship_id))

        db.commit()

        flash("Report reviewed and feedback saved", "success")

        return redirect(url_for(
            "supervisor_weeklyreports",
            internship_id=internship_id
        ))


    week = request.args.get("week", type=int)

    stats = db.execute("""
    WITH internship_expected AS (
        SELECT
            i.internship_id,
            MAX(
                CAST((JULIANDAY('now') - JULIANDAY(i.start_date)) / 7 AS INTEGER),
                0
            ) AS expected_reports
        FROM internship i
        WHERE i.supervisor_id = ?
    ),
    submitted AS (
        SELECT
            wr.internship_id,
            COUNT(*) AS submitted_reports
        FROM weekly_reports wr
        WHERE wr.status = 'submitted'
        GROUP BY wr.internship_id
    )
    SELECT
        SUM(
            CASE
                WHEN ie.expected_reports - COALESCE(s.submitted_reports, 0) > 0
                THEN ie.expected_reports - COALESCE(s.submitted_reports, 0)
                ELSE 0
            END
        ) AS reports_not_submitted,
        SUM(ie.expected_reports) AS total_expected_reports,
        SUM(COALESCE(s.submitted_reports, 0)) AS total_submitted_reports
    FROM internship_expected ie
    LEFT JOIN submitted s ON s.internship_id = ie.internship_id;
    """, (supervisor_id,)).fetchone()

    total_expected = stats["total_expected_reports"] or 0
    total_submitted = stats["total_submitted_reports"] or 0
    reports_not_submitted = stats["reports_not_submitted"] or 0

    if total_expected > 0:
        submitted_percent = round((total_submitted / total_expected) * 100)
    else:
        submitted_percent = 0
    if week is None:
        reports = db.execute("""
        SELECT
                wr.report_id,
                wr.week_number,
                wr.task_description,
                wr.attendance_percentage,
                wr.focus_skill,
                wr.skill_rating,
                wr.stress_level,
                wr.self_evaluation,
                wr.challenges,
                wr.next_week_priorities,
                wr.evidence_link,
                wr.submitted_at,
                wr.status,
                wr.supervisor_feedback,
                wr.reviewed_at,

            ud.first_name || ' ' || ud.last_name AS intern_name,
            ud.email,
            ud.avatar_url,
            i.domain
        FROM weekly_reports wr
        JOIN internship i ON i.internship_id = wr.internship_id
        JOIN user_details ud ON ud.user_id = wr.user_id
        WHERE i.supervisor_id = ?
        AND i.internship_id = ?
            AND (wr.status = 'submitted' or wr.status = 'reviewed')
        ORDER BY wr.week_number DESC
        LIMIT 1
        """,(supervisor_id, internship_id)).fetchone()
    else:
        reports = db.execute("""
        SELECT
                wr.report_id,
                wr.week_number,
                wr.task_description,
                wr.attendance_percentage,
                wr.focus_skill,
                wr.skill_rating,
                wr.stress_level,
                wr.self_evaluation,
                wr.challenges,
                wr.next_week_priorities,
                wr.evidence_link,
                wr.submitted_at,
                wr.status,
                wr.supervisor_feedback,
                wr.reviewed_at,

            ud.first_name || ' ' || ud.last_name AS intern_name,
            ud.email,
            ud.avatar_url,
            i.domain
        FROM weekly_reports wr
        JOIN internship i ON i.internship_id = wr.internship_id
        JOIN user_details ud ON ud.user_id = wr.user_id
        WHERE i.supervisor_id = ?
        AND i.internship_id = ?
            AND (wr.status = 'submitted' or wr.status = 'reviewed')
        AND wr.week_number = ?
        ORDER BY wr.submitted_at DESC
        """, (supervisor_id, internship_id, week)).fetchone()

    if reports:
            print('hello')
            current_week = reports["week_number"]

            if current_week > 1:
                prev_week = current_week - 1

            candidate_next = current_week + 1

            exists = db.execute("""
                SELECT 1
                FROM weekly_reports wr
                JOIN internship i ON i.internship_id = wr.internship_id
                WHERE i.internship_id = ?
                AND i.supervisor_id = ?
                AND wr.week_number = ?
                AND (wr.status = 'submitted' OR wr.status = 'reviewed')
            """, (internship_id, supervisor_id, candidate_next)).fetchone()
            if exists:
                next_week = candidate_next

    supervisor_details = db.execute("""
    SELECT * FROM user_details
    WHERE user_id = ?
    """,(supervisor_id,)).fetchone()  
    return render_template("supervisor/supervisorWeeklyReports.html",supervisor_details=supervisor_details,report=reports, submitted_percent=submitted_percent,
    reports_not_submitted=reports_not_submitted,prev_week=prev_week,next_week=next_week,internship_id=internship_id)

@app.route("/supervisor/profile")
def supervisor_profile():
    if "user_id" not in session or session.get('role') != 'supervisor':
        return redirect(url_for('login'))
    supervisor_id = session['user_id']
    db = get_db()

    today = date.today()

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
    """, (supervisor_id,)).fetchone()

    overview = {}

    overview["interns_assigned"] = db.execute("""
        SELECT COUNT(DISTINCT user_id)
        FROM internship
        WHERE supervisor_id = ?
    """, (supervisor_id,)).fetchone()[0]

    overview["reports_reviewed"] = db.execute("""
        SELECT COUNT(*)
        FROM weekly_reports wr
        JOIN internship i ON i.internship_id = wr.internship_id
        WHERE i.supervisor_id = ?
        AND wr.status = 'reviewed'
    """, (supervisor_id,)).fetchone()[0]

    overview["avg_completion"] = round(
        db.execute("""
            SELECT AVG(
            CASE
                WHEN DATE('now') >= end_date THEN 100
                WHEN DATE('now') <= start_date THEN 0
                ELSE
                ROUND(
                    (JULIANDAY('now') - JULIANDAY(start_date)) * 100.0 /
                    NULLIF(JULIANDAY(end_date) - JULIANDAY(start_date), 0),
                    0
                )
            END
            )
            FROM internship
            WHERE supervisor_id = ?
        """, (supervisor_id,)).fetchone()[0] or 0
    )

    overview["experience_years"] = supervisor_details["experience_years"] or 0

    return render_template("supervisor/supervisorProfile.html",supervisor_details=supervisor_details,today=today.strftime("%d %b %Y"),
    overview=overview)

@app.route("/supervisor/profile/edit", methods=["GET", "POST"])
def edit_supervisor_profile():
    if "user_id" not in session or session.get("role") != "supervisor":
        return redirect(url_for("login"))

    supervisor_id = session["user_id"]
    db = get_db()

    db.execute("""
INSERT OR IGNORE INTO supervisor_details (user_id)
VALUES (?)
""", (supervisor_id,))

    if request.method == "POST":
        # 1️⃣ Update user_details
        db.execute("""
            UPDATE user_details
            SET
                first_name = ?,
                last_name = ?,
                email = ?,
                phone_number = ?
            WHERE user_id = ?
        """, (
            request.form["first_name"].strip(),
            request.form["last_name"].strip(),
            request.form["email"].strip(),
            request.form["phone_number"].strip(),
            supervisor_id
        ))

        # 2️⃣ Update supervisor_details
        db.execute("""
            UPDATE supervisor_details
            SET
                employee_id = ?,
                designation = ?,
                department = ?,
                organization = ?
            WHERE user_id = ?
        """, (
            request.form["employee_id"].strip(),
            request.form["designation"].strip(),
            request.form["department"].strip(),
            request.form.get("organization", "").strip(),
            supervisor_id
        ))

        db.commit()
        flash("Profile updated successfully", "success")
        return redirect(url_for("supervisor_profile"))

    # GET → load existing data
    supervisor = db.execute("""
        SELECT
            ud.user_id,
            ud.first_name,
            ud.last_name,
            ud.email,
            ud.phone_number,
            sd.employee_id,
            sd.designation,
            sd.department,
            sd.organization
        FROM user_details ud
        LEFT JOIN supervisor_details sd
            ON ud.user_id = sd.user_id
        WHERE ud.user_id = ?
    """, (supervisor_id,)).fetchone()

    return render_template(
        "supervisor/editSupervisorProfile.html",
        supervisor=supervisor
    )

@app.route("/supervisor/performance")
def supervisor_performance():
    if "user_id" not in session and session['role'] != 'supervisor':
        return redirect(url_for('login'))
    supervisor_id = session['user_id']
    db=get_db()
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
    """, (supervisor_id,)).fetchone()
    return render_template("supervisor/supervisorPerformance.html",supervisor_details=supervisor_details)

@app.route("/supervisor/performance/data")
def supervisor_performance_data():
    if "user_id" not in session or session.get("role") != "supervisor":
        return jsonify({}), 401

    supervisor_id = session["user_id"]
    db = get_db()

    # -----------------------------
    # 1️⃣ DOMAIN-LEVEL METRICS
    # -----------------------------
    domain_rows = db.execute("""
        SELECT
            i.domain,

            ROUND(AVG(wr.attendance_percentage), 1) AS avg_attendance,
            ROUND(AVG(wr.skill_rating), 1) AS avg_rating,
            ROUND(AVG(wr.stress_level), 1) AS avg_stress

        FROM weekly_reports wr
        JOIN internship i
            ON i.internship_id = wr.internship_id

        WHERE i.supervisor_id = ?
          AND wr.status IN ('submitted', 'reviewed')

        GROUP BY i.domain
    """, (supervisor_id,)).fetchall()

    domains = {}

    for row in domain_rows:
        domains[row["domain"]] = {
            "scores": {
                "attendance": row["avg_attendance"] or 0,
                "rating": row["avg_rating"] or 0,
                "stress": row["avg_stress"] or 0
            },
            "weekly": []
        }

    # -----------------------------
    # 2️⃣ WEEKLY ATTENDANCE TREND
    # -----------------------------
    weekly_rows = db.execute("""
        SELECT
            i.domain,
            wr.week_number,
            ROUND(AVG(wr.attendance_percentage), 0) AS attendance
        FROM weekly_reports wr
        JOIN internship i
            ON i.internship_id = wr.internship_id
        WHERE i.supervisor_id = ?
          AND wr.status IN ('submitted', 'reviewed')
        GROUP BY i.domain, wr.week_number
        ORDER BY wr.week_number
    """, (supervisor_id,)).fetchall()

    for row in weekly_rows:
        domains[row["domain"]]["weekly"].append(
            row["attendance"]
        )

    return jsonify(domains)



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
        flash("Invalid email or password", "error")
        return render_template(
            "login.html",
        )

    # Store session
    session["user_id"] = user["user_id"]
    session["role"] = user["role"]

    # Redirect based on role
    if user["role"] == "intern":
        return redirect(url_for("intern_dashboard"))

    if user["role"] == "supervisor":
        return redirect(url_for("supervisor_dashboard"))

    return "Unknown role", 403

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/update-avatar", methods=["POST"])
def update_avatar():
    if "user_id" not in session:
        return "", 401

    avatar_url = request.json.get("avatar_url")

    db = get_db()
    db.execute(
        "UPDATE user_details SET avatar_url = ? WHERE user_id = ?",
        (avatar_url, session["user_id"])
    )
    db.commit()
    return "", 204

@app.route("/upload-avatar", methods=["POST"])
def upload_avatar():
    if "user_id" not in session:
        return "", 401

    if "avatar" not in request.files:
        return "", 400

    file = request.files["avatar"]

    if file.filename == "":
        return "", 400

    if not allowed_file(file.filename):
        return "", 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"user_{session['user_id']}.{ext}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    if len(file.read()) > 2 * 1024 * 1024:
        return "", 413
    file.seek(0)
    file.save(filepath)

    avatar_url = f"/static/uploads/avatars/{filename}"

    db = get_db()
    db.execute(
        "UPDATE user_details SET avatar_url = ? WHERE user_id = ?",
        (avatar_url, session["user_id"])
    )
    db.commit()

    return "", 204


@app.route("/intern/profile")
def profile():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("login"))

    user_id = session["user_id"]   # 🔒 source of truth
    db = get_db()

    month = {
        '01': 'January', '02': 'February', '03': 'March', '04': 'April',
        '05': 'May', '06': 'June', '07': 'July', '08': 'August',
        '09': 'September', '10': 'October', '11': 'November', '12': 'December'
    }

    # --------------------
    # User details
    # --------------------
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

    # --------------------------------------------------
    # Latest internship → weekly report redirect logic
    # --------------------------------------------------
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

    # --------------------
    # Internship selector
    # --------------------
    selected_id = request.args.get("internship_id", type=int)

    if selected_id:
        internship = next(
            (i for i in internships if i["internship_id"] == selected_id),
            None
        )
    else:
        internship = internships[-1]

    # --------------------
    # Internship status
    # --------------------
    startDateConv = datetime.strptime(internship["start_date"], "%Y-%m-%d").date()
    endDateConv = datetime.strptime(internship["end_date"], "%Y-%m-%d").date()

    if startDateConv <= today <= endDateConv:
        status = "ACTIVE"
    elif today < startDateConv:
        status = "UPCOMING"
    else:
        status = "COMPLETED"

    # --------------------
    # Completion %
    # --------------------
    if today <= startDateConv:
        completion = 0
    elif today >= endDateConv:
        completion = 100
    else:
        total_days = (endDateConv - startDateConv).days
        days_passed = (today - startDateConv).days
        completion = round((days_passed / total_days) * 100, 2)

    # --------------------
    # Supervisor (display)
    # --------------------
    supervisor = db.execute(
        "SELECT * FROM user_details WHERE user_id = ?",
        (internship["supervisor_id"],)
    ).fetchone()

    # --------------------
    # Attendance + reports
    # --------------------
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
        WHERE user_id = ? AND internship_id = ? AND status = 'submitted'
        """,
        (user_id, internship_id)
    ).fetchone()["submitted_reports"]

    skill_count = db.execute(
        """
        SELECT COUNT(DISTINCT focus_skill) AS skill_variety
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ? AND status = 'submitted'
        """,
        (user_id, internship_id)
    ).fetchone()["skill_variety"]

    # --------------------
    # Password last updated
    # --------------------
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

    # --------------------
    # Domain display string
    # --------------------
    domain = " • ".join(i["domain"] for i in internships)

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
        supervisor=supervisor,
        status=status,
        counts=counts
    )

@app.route("/intern/profile/edit", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("login"))

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
            return redirect(url_for("edit_profile"))

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
        return redirect(url_for("profile"))

    return render_template(
        "intern/editProfile.html",
        user_details=user_details
    )


@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    db=get_db()
    previous_page = request.referrer

    if request.method == "POST":
        current = request.form["current_password"]
        new = request.form["new_password"]
        confirm = request.form["confirm_password"]

        user = db.execute(
            "SELECT password FROM users WHERE user_id = ?",
            (session["user_id"],)
        ).fetchone()

        if not verify_password(user["password"], current):
            flash("Current password is incorrect", "error")
            return redirect(url_for("change_password"))

        if new != confirm:
            flash("Passwords do not match", "error")
            return redirect(url_for("change_password"))

        hashed = hash_password(new)

        db.execute("""
            UPDATE users
            SET password = ?, password_updated_at = CURRENT_DATE
            WHERE user_id = ?
        """, (hashed, session["user_id"]))
        db.commit()

        flash("Password updated successfully", "success")
        return redirect(url_for('profile') if session['role'] == "intern" else url_for('supervisor_profile'))

    return render_template("changePassword.html",previous_page=previous_page)

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
        selected_internship = internships[-1]
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
        "intern/internSkills.html",
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
        "intern/reportHistory.html",
        reports=reports,
        internship=internship
    )

@app.route("/avatar/chat", methods=["POST"])
def avatar_chat():
    if "user_id" not in session:
        return jsonify({"reply": "Unauthorized"}), 401
    data = request.json
    user_id = session["user_id"]   # 🔒 SOURCE OF TRUTH
    internship_id = data.get("internship_id")
    user_message = data.get("message")

    db = get_db()

    # Fetch internship domain
    internship = db.execute(
        "SELECT domain FROM internship WHERE internship_id = ?",
        (internship_id,)
    ).fetchone()

    if not internship:
        synthesize_speech("Invalid internship.", output_file="static/audio/response.wav")
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
        synthesize_speech("I need more performance data before I can guide you properly.", output_file="static/audio/response.wav")
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
    synthesize_speech(reply, output_file="static/audio/response.wav")
    set_last_message(user_id, internship_id, reply, user_message)
    return jsonify({"reply": reply})

@app.route("/intern/avatar", methods=["GET", "POST"])
def avatar_page():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("login"))

    user_id = session["user_id"]
    db = get_db()

    internships = db.execute(
        "SELECT * FROM internship WHERE user_id = ?",
        (user_id,)
    ).fetchall()
    user_details = db.execute(
        "SELECT * FROM user_details WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    domain=""
    for i in internships:
        domain+=i["domain"]+" • "
    domain = domain[:-3]  # Remove trailing separator
     # --------------------------------------------------
    # Latest internship → weekly report redirect logic
    # --------------------------------------------------
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
    return render_template(
        "intern/avatarChat.html",
        internships=internships,
        user_details=user_details,
        domain=domain,
        progress_percentage=myProgressPercentage(db, user_id),
        weeklyReportRedirect=weeklyReportRedirect
    )

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
