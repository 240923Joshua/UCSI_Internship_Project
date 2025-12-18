import sqlite3
import pandas as pd
from sklearn.linear_model import LinearRegression
conn = sqlite3.connect(r"C:\Users\PROBOOK\Downloads\internship.db")
cursor = conn.cursor()
def fetch_marks(user_id, internship_id):
    query = """
    SELECT score
    FROM weekly_report
    WHERE user_id = ? AND score IS NOT NULL AND internship_id = ? ORDER BY week_number ASC"""

    cursor.execute(query, (user_id, internship_id))

    # Fetch all scores as list
    scores = [row[0] for row in cursor.fetchall()]

    # Close connection
    conn.close()
    return scores


def mark_prediction(marks):
   data = {
    'Previous_Marks': marks[:-1],
    'Final_Marks': marks[1:]
    }

   dataf = pd.DataFrame(data, columns=['Previous_Marks', 'Final_Marks'])

   x = dataf[['Previous_Marks']]   # Independent variable
   y = dataf['Final_Marks']        # Dependent variable
   model = LinearRegression()
   model.fit(x, y)
   current_mark = pd.DataFrame(
    [[marks[-1]]],
    columns=['Previous_Marks']
    )
   predicted_mark = model.predict(current_mark)

   return int(predicted_mark[0])

def set_predict(user_id, internship_id):
    marks = fetch_marks(user_id, internship_id)
    if len(marks) < 2:
        print("Not enough data to make a prediction.")
    else:
        predicted_mark = mark_prediction(marks)
        if predicted_mark < 50:
            risk_level = "High"
        elif 50 <= predicted_mark < 70:
            risk_level = "Medium"
        elif predicted_mark >= 70:
            risk_level = "Low"

        insert_query = """
        INSERT INTO weekly_report (user_id, internship_id, predicted_mark, risk_level)
        VALUES (?, ?, ?, ?)"""
        cursor.execute(insert_query, (user_id, internship_id, predicted_mark, risk_level ))
        conn.commit()