from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, abort
from app.db import get_db

supervisor_bp = Blueprint('supervisor', __name__, url_prefix='/supervisor')

@supervisor_bp.route("/dashboard")
def supervisor_dashboard():
    if "user_id" not in session or session.get("role") != "supervisor":
        return redirect(url_for("auth.login"))
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
          AND wr.status IN ('submitted', 'reviewed')
    """, (supervisor_id,)).fetchone()[0]

    pending_reviews = db.execute("""
        SELECT COUNT(*)
        FROM weekly_reports wr
        JOIN internship i ON i.internship_id = wr.internship_id
        WHERE i.supervisor_id = ?
        AND wr.status = 'submitted'
    """,(supervisor_id,)).fetchone()[0]

    recent_reports = db.execute("""
    SELECT
        wr.report_id,
        ud.first_name || ' ' || ud.last_name AS intern_name,
        wr.week_number,
        i.domain,
        i.internship_id,
        wr.submitted_at
    FROM weekly_reports wr
    JOIN internship i ON i.internship_id = wr.internship_id
    JOIN user_details ud ON ud.user_id = i.user_id
    WHERE i.supervisor_id = ?
      AND wr.status IN ('submitted','reviewed')
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
        i.domain, ud.avatar_url, i.internship_id,
        COUNT(wr.report_id) AS report_count
    FROM weekly_reports wr
    JOIN internship i ON i.internship_id = wr.internship_id
    JOIN user_details ud ON ud.user_id = i.user_id
    WHERE i.supervisor_id = ?
      AND wr.status IN ('submitted','reviewed')
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
    """, (supervisor_id,)).fetchone()

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

    return render_template("supervisor/supervisorDashboard.html", interns=interns, total_interns=total_interns,
    supervisor_details=supervisor_details,submitted_reports=submitted_reports,pending_reviews=pending_reviews,
    recent_reports=recent_reports,active_internships=active_internships,top_intern=top_intern,
    supervisor_weeklyReportRedirect=supervisor_weeklyReportRedirect)

@supervisor_bp.route("/interns")
def supervisor_interns():
    if "user_id" not in session or session.get('role') != "supervisor":
        return redirect(url_for('auth.login'))
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
                    AND wr.status IN ('submitted','reviewed')
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
    """, (supervisor_id,)).fetchone()
    return render_template('supervisor/supervisorInterns.html',supervisor_details=supervisor_details,interns=interns,domains=domains,
    supervisor_weeklyReportRedirect=supervisor_weeklyReportRedirect)

@supervisor_bp.route("/intern/<int:intern_id>/<int:internship_id>")
def supervisor_view_intern(intern_id,internship_id):
    if "user_id" not in session or session.get("role") != "supervisor":
        return redirect(url_for("auth.login"))

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
                    AND wr.status IN ('submitted', 'reviewed')
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
          AND i.internship_id = ?
    """, (intern_id, supervisor_id,internship_id))

    intern = cursor.fetchone()

    if intern is None:
        return redirect(url_for("supervisor.supervisor_interns"))

    return render_template(
        "supervisor/viewInternProfile.html",
        intern=intern,
        previous_page=previous_page
    )

@supervisor_bp.route("/weekly-reports/<int:internship_id>", methods=['GET','POST'])
def supervisor_weeklyreports(internship_id):
    if "user_id" not in session or session.get('role') != 'supervisor':
        return redirect(url_for('auth.login'))
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
                "supervisor.supervisor_weeklyreports",
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
            "supervisor.supervisor_weeklyreports",
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
        WHERE wr.status IN ('submitted', 'reviewed')
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
    return render_template("supervisor/supervisorWeeklyReports.html",supervisor_details=supervisor_details,report=reports, submitted_percent=submitted_percent,
    reports_not_submitted=reports_not_submitted,prev_week=prev_week,next_week=next_week,internship_id=internship_id)

@supervisor_bp.route("/profile")
def supervisor_profile():
    if "user_id" not in session or session.get('role') != 'supervisor':
        return redirect(url_for('auth.login'))
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

    password_updated = db.execute(
        """
        SELECT password_updated_at
        FROM users
        WHERE user_id = ?
        """,
        (supervisor_id,)
    ).fetchone()["password_updated_at"]

    password_updated = (
        datetime.strptime(password_updated, "%Y-%m-%d").date()
        if password_updated else None
    )
    today = date.today()
    days_ago = (today - password_updated).days if password_updated else None

    if days_ago is None:
        label = "Not available"
    elif days_ago < 30:
        label = "Less than a month ago"
    elif days_ago < 365:
        label = f"{days_ago // 30} month(s) ago"
    else:
        label = f"{days_ago // 365} year(s) ago"

    return render_template("supervisor/supervisorProfile.html",supervisor_details=supervisor_details,today=today.strftime("%d %b %Y"),
    overview=overview,label=label)

@supervisor_bp.route("/profile/edit", methods=["GET", "POST"])
def edit_supervisor_profile():
    if "user_id" not in session or session.get("role") != "supervisor":
        return redirect(url_for("auth.login"))

    supervisor_id = session["user_id"]
    db = get_db()

    db.execute("""
    INSERT OR IGNORE INTO supervisor_details (user_id)
    VALUES (?)
    """, (supervisor_id,))

    if request.method == "POST":
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
        return redirect(url_for("supervisor.supervisor_profile"))

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

@supervisor_bp.route("/performance")
def supervisor_performance():
    if "user_id" not in session or session.get('role') != 'supervisor':
        return redirect(url_for('auth.login'))
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

@supervisor_bp.route("/performance/data")
def supervisor_performance_data():
    if "user_id" not in session or session.get("role") != "supervisor":
        return jsonify({}), 401

    supervisor_id = session["user_id"]
    db = get_db()

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
