from flask import Flask,render_template
from db import get_db
from avatar import get_avatar_response


app = Flask(__name__)

@app.route("/")
def home():
    # return "Backend is running"
    return render_template("home.html")

@app.route("/test-db")
def test_db():
    db = get_db()
    return "Database connection successful" if db else "Database connection failed"

@app.route("/users")
def select_all_users():
    db = get_db()
    cursor = db.execute("SELECT * FROM users")
    users = cursor.fetchall()
    return {"users": [dict(user) for user in users]}

@app.route("/attendance/<int:user_id>/<int:internship_id>")
def attendance_percentage(user_id, internship_id):
    db = get_db()

    query = """
    SELECT 
        ROUND(
            (SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) * 100.0)
            / COUNT(*),
            2
        ) AS attendance_percentage
    FROM attendance
    WHERE user_id = ? AND internship_id = ?;
    """

    result = db.execute(query, (user_id, internship_id)).fetchone()

    return {
        "user_id": user_id,
        "internship_id": internship_id,
        "attendance_percentage": result["attendance_percentage"] if result else 0
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
        return {"message": "No ML results found"}

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

    attendance_percentage = attendance_result["attendance_percentage"] or 0

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
        return {"message": "No ML results available"}

    # 3️⃣ Avatar decision
    avatar_response = get_avatar_response(
        attendance_percentage,
        ml_result["risk_level"],
        ml_result["predicted_score"]
    )

    return {
        "user_id": user_id,
        "internship_id": internship_id,
        "attendance_percentage": round(attendance_percentage, 2),
        "predicted_score": ml_result["predicted_score"],
        "risk_level": ml_result["risk_level"],
        "avatar_state": avatar_response["state"],
        "avatar_message": avatar_response["message"]
    }

@app.route("/intern/<int:user_id>")
def intern_dashboard(user_id):
    db = get_db()
    cursor = db.execute("SELECT * FROM internship WHERE user_id = ?", (user_id,))
    internships = cursor.fetchall()
    return render_template("intern_dashboard.html", internships=internships)

@app.route("/supervisor/<int:supervisor_id>/dashboard")
def supervisor_dashboard(supervisor_id):
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

if __name__ == "__main__":
    app.run(debug=True)
