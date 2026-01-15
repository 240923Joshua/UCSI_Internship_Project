from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.db import get_db
from app.hasher import hash_password, verify_password

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
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
        return redirect(url_for("intern.intern_dashboard"))

    if user["role"] == "supervisor":
        return redirect(url_for("supervisor.supervisor_dashboard"))

    return "Unknown role", 403

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    
    db = get_db()
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
            return redirect(url_for("auth.change_password"))

        if new != confirm:
            flash("Passwords do not match", "error")
            return redirect(url_for("auth.change_password"))

        hashed = hash_password(new)

        db.execute("""
            UPDATE users
            SET password = ?, password_updated_at = CURRENT_DATE
            WHERE user_id = ?
        """, (hashed, session["user_id"]))
        db.commit()

        flash("Password updated successfully", "success")
        return redirect(url_for('intern.profile') if session['role'] == "intern" else url_for('supervisor.supervisor_profile'))

    return render_template("changePassword.html", previous_page=previous_page)
