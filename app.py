from flask import Flask,render_template, request, redirect, url_for, session, jsonify
from db import get_db, calculate_attendance_percentage
from avatar import get_avatar_response
from hasher import hash_password, verify_password
from llm import generate_response, build_avatar_prompt

app = Flask(__name__)
app.secret_key = "d2a0fc31b5ca9b05585d76fd607983601efe4bf8980e10c9a40f13e36a3cb2e3"
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
    cursor = db.execute("SELECT * FROM user_details WHERE user_id = ?", (user_id,))
    user_details = cursor.fetchone()
    cursor = db.execute("SELECT * FROM internship WHERE user_id = ?", (user_id,))
    internships = cursor.fetchall()
    domain=""
    for i in internships:
        domain+=i["domain"]+" • "
    domain = domain[:-3]  # Remove trailing separator
    return render_template("intern/finalprofile.html", user_details=user_details,internships=internships,domain=domain)

@app.route("/avatar/chat", methods=["POST"])
def avatar_chat():
    data = request.json

    user_id = data.get("user_id")
    internship_id = data.get("internship_id")
    user_message = data.get("message")

    db = get_db()

    # 1️⃣ Fetch internship domain
    internship = db.execute(
        "SELECT domain FROM internship WHERE internship_id = ?",
        (internship_id,)
    ).fetchone()

    if not internship:
        return jsonify({"reply": "Invalid internship."}), 400

    domain = internship["domain"]

    # 2️⃣ Fetch attendance
    attendance_percentage = calculate_attendance_percentage(
        db, user_id, internship_id
    )

    # 3️⃣ Fetch ML result
    ml_result = db.execute(
        "SELECT predicted_score, risk_level FROM ml_results WHERE user_id = ? AND internship_id = ?",
        (user_id, internship_id)
    ).fetchone()

    if attendance_percentage is None or not ml_result:
        return jsonify({
            "reply": "I need more performance data before I can guide you properly."
        })

    # 4️⃣ Build prompt
    prompt = build_avatar_prompt(
        attendance_percentage,
        ml_result["predicted_score"],
        ml_result["risk_level"],
        domain,
        user_message
    )

    # 5️⃣ Generate response
    reply = generate_response(prompt)

    return jsonify({"reply": reply})


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
