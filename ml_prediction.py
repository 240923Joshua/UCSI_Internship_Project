import sqlite3
import pandas as pd
import numpy as np

DB_PATH = r"C:\Users\PROBOOK\Downloads\internship (4).db"

MIN_WEEKLY_SCORES = 2

conn = sqlite3.connect(DB_PATH)


def predict(user_id, internship_id):

    weekly_df = pd.read_sql("""
        SELECT week_number, attendance_percentage, skill_rating
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ?
        ORDER BY week_number
    """, conn, params=(user_id, internship_id))

    if len(weekly_df) < MIN_WEEKLY_SCORES:
        return None

    # Ensure numeric
    weekly_df["attendance_percentage"] = pd.to_numeric(
        weekly_df["attendance_percentage"], errors="coerce"
    )
    weekly_df["skill_rating"] = pd.to_numeric(
        weekly_df["skill_rating"], errors="coerce"
    )

    weekly_df.dropna(inplace=True)

    if len(weekly_df) < MIN_WEEKLY_SCORES:
        return None

    # 🔹 SCALE skill rating from 1–10 → 0–100
    scores = weekly_df["skill_rating"].values * 10
    attendance = weekly_df["attendance_percentage"].values / 100

    # ---- TREND CALCULATION ----
    deltas = np.diff(scores)
    avg_delta = np.mean(deltas) * 0.6  # dampened trend

    last_score = scores[-1]
    avg_attendance = np.mean(attendance)

    # Predict next score
    predicted_score = last_score + avg_delta

    # Attendance impact
    predicted_score *= avg_attendance

    # 🔒 FINAL CLAMP (ABSOLUTE SAFETY)
    predicted_score = np.clip(predicted_score, 0, 100)

    return round(float(predicted_score), 2)


def set_predict(user_id, internship_id):

    predicted_score = predict(user_id, internship_id)
    if predicted_score is None:
        print("Not enough data to predict.")
        return None

    if predicted_score < 50:
        risk = "High"
        recommendation = "Immediate intervention required"
    elif predicted_score < 75:
        risk = "Medium"
        recommendation = "Needs improvement"
    else:
        risk = "Low"
        recommendation = "Good performance"

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ml_results
        (user_id, internship_id, predicted_score, risk_level, recommendation)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, internship_id, predicted_score, risk, recommendation))

    conn.commit()
    return predicted_score


# Example usage
result = set_predict(100001, 3)
print("Predicted Score:", result)

conn.close()
