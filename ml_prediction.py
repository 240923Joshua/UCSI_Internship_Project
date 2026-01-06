import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from db import get_db

MIN_WEEKLY_SCORES = 3


def predict(user_id, internship_id,conn):

    df = pd.read_sql("""
        SELECT week_number, attendance_percentage, skill_rating
        FROM weekly_reports
        WHERE user_id = ? AND internship_id = ?
        ORDER BY week_number
    """, conn, params=(user_id, internship_id))

    if len(df) < MIN_WEEKLY_SCORES:
        return None

    df = df.apply(pd.to_numeric, errors="coerce")
    df.dropna(inplace=True)

    if len(df) < MIN_WEEKLY_SCORES:
        return None

    # Scale skill rating to 0–100
    df["skill_scaled"] = df["skill_rating"] * 10

    # ------------------ TARGET: DELTA ------------------
    df["delta_skill"] = df["skill_scaled"].diff()
    df.dropna(inplace=True)

    if len(df) < 2:
        return None

    # ------------------ FEATURES ------------------
    X = df[["week_number", "attendance_percentage"]]
    y = df["delta_skill"]

    # ------------------ TRAIN MODEL ------------------
    model = Ridge(alpha=1.0)
    model.fit(X, y)

    # ------------------ PREDICT NEXT WEEK DELTA ------------------
    last = df.iloc[-1]

    X_next = np.array([[
        last["week_number"] + 1,
        df["attendance_percentage"].mean()
    ]])

    predicted_delta = model.predict(X_next)[0]

    # ------------------ FINAL SCORE ------------------
    last_score = df["skill_scaled"].iloc[-1]
    predicted_score = last_score + predicted_delta

    # Clamp strictly
    predicted_score = np.clip(predicted_score, 0, 100)

    return round(float(predicted_score), 2)


def set_predict(user_id, internship_id,conn):

    predicted_score = predict(user_id, internship_id,conn)
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
    exists = cursor.execute("""
        SELECT 1 FROM ml_results
        WHERE user_id = ? AND
        internship_id = ?
    """,(user_id,internship_id)).fetchone()
    if exists:
        cursor.execute("""
        UPDATE  ml_results
        SET 
        predicted_score = ?,
        risk_level = ?,
        recommendation = ?
        WHERE 
        user_id = ? AND
        internship_id = ?
        """, (predicted_score,risk,recommendation,user_id,internship_id))
    else:
        cursor.execute("""
            INSERT INTO ml_results
            (user_id, internship_id, predicted_score, risk_level, recommendation)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, internship_id, predicted_score, risk, recommendation))

    conn.commit()
    return predicted_score


# ------------------ TEST ------------------
# result = set_predict(100001, 3)
# print("Predicted Score:", result)

# conn.close()
