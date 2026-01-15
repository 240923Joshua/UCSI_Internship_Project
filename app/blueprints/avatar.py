import os
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from app.db import get_db, calculate_attendance_percentage
from app.utils import allowed_file, myProgressPercentage
from app.llm import generate_response, build_avatar_prompt, synthesize_speech
from app.memory import get_last_message, set_last_message

avatar_bp = Blueprint('avatar', __name__)

@avatar_bp.route("/update-avatar", methods=["POST"])
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

@avatar_bp.route("/upload-avatar", methods=["POST"])
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
    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)

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

@avatar_bp.route("/avatar/chat", methods=["POST"])
def avatar_chat():
    if "user_id" not in session:
        return jsonify({"reply": "Unauthorized"}), 401
    data = request.json
    user_id = session["user_id"]
    internship_id = data.get("internship_id")
    user_message = data.get("message")

    db = get_db()

    internship = db.execute(
        "SELECT domain FROM internship WHERE internship_id = ?",
        (internship_id,)
    ).fetchone()

    # Use absolute path for static folder
    static_audio_dir = os.path.join(current_app.static_folder, "audio")
    os.makedirs(static_audio_dir, exist_ok=True)

    if not internship:
        error_file = os.path.join(static_audio_dir, "response.wav")
        synthesize_speech("Invalid internship.", output_file=error_file)
        return jsonify({"reply": "Invalid internship."}), 400

    domain = internship["domain"]

    attendance_percentage = calculate_attendance_percentage(
        db, user_id, internship_id
    )

    ml_result = db.execute(
        "SELECT predicted_score, risk_level FROM ml_results WHERE user_id = ? AND internship_id = ?",
        (user_id, internship_id)
    ).fetchone()

    if attendance_percentage is None or not ml_result:
        error_file = os.path.join(static_audio_dir, "response.wav")
        synthesize_speech("I need more performance data before I can guide you properly.", output_file=error_file)
        return jsonify({
            "reply": "I need more performance data before I can guide you properly."
        })

    prompt = build_avatar_prompt(
        attendance_percentage,
        ml_result["predicted_score"],
        ml_result["risk_level"],
        domain,
        user_message,
        memory=get_last_message(user_id, internship_id)
    )

    reply = generate_response(prompt)

    user_audio_dir = os.path.join(static_audio_dir, f"user_{user_id}")
    os.makedirs(user_audio_dir, exist_ok=True)

    filename = "response.wav"
    output_file = os.path.join(user_audio_dir, filename)

    synthesize_speech(reply, output_file=output_file)
    set_last_message(user_id, internship_id, reply, user_message)

    return jsonify({
        "reply": reply,
        "audio_url": f"/static/audio/user_{user_id}/{filename}"
    })

@avatar_bp.route("/intern/avatar", methods=["GET", "POST"])
def avatar_page():
    if "user_id" not in session or session.get("role") != "intern":
        return redirect(url_for("auth.login"))

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
    domain = domain[:-3]

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
