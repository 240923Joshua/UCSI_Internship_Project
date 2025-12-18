from flask import Flask
from db import get_db
from avatar import get_avatar_response


app = Flask(__name__)

@app.route("/")
def home():
    return "Backend is running"

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



if __name__ == "__main__":
    app.run(debug=True)
