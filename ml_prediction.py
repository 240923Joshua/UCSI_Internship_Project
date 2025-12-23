import sqlite3
import pandas as pd
import numpy as np

DB_PATH = r"C:\Users\PROBOOK\Downloads\internship (1).db"

MIN_WEEKLY_SCORES = 2
MIN_ATTENDANCE_DAYS = 2

conn = sqlite3.connect(DB_PATH)

def predict(user_id, internship_id):

    weekly_df = pd.read_sql("""
        SELECT week_number, score
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ?
        ORDER BY week_number
    """, conn, params=(user_id, internship_id))

    attendance_df = pd.read_sql("""
        SELECT status
        FROM attendance
        WHERE user_id = ? AND internship_id = ?
    """, conn, params=(user_id, internship_id))

    total_days = len(attendance_df)
    present_days = len(attendance_df[attendance_df["status"].str.lower() == "present"])

    if len(weekly_df) < MIN_WEEKLY_SCORES or total_days < MIN_ATTENDANCE_DAYS:
        print("Prediction not possible: insufficient data.")
        return None

    attendance_percentage = present_days / total_days

    # Ensure numeric scores
    weekly_df["score"] = pd.to_numeric(weekly_df["score"], errors="coerce")
    weekly_df = weekly_df.dropna(subset=["score"])

    scores = weekly_df["score"].values

    # ---- SAFE TREND CALCULATION ----
    # Use average improvement instead of extrapolation
    deltas = np.diff(scores)
    avg_delta = np.mean(deltas)

    # Damp the trend (prevents runaway growth)
    avg_delta *= 0.6

    predicted_score = scores[-1] + avg_delta

    # Attendance penalty (strong effect)
    predicted_score *= attendance_percentage

    # Absolute bounds
    predicted_score = max(0, min(100, predicted_score))

    return round(predicted_score, 2)


def set_predict(user_id, internship_id):

    predicted_score = predict(user_id, internship_id)
    if predicted_score is None:
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
result = set_predict(3, 1)
print("Predicted Score:", result)

conn.close()
