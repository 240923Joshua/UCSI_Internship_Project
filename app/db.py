import sqlite3

def get_db():
    conn = sqlite3.connect("internship.db")
    conn.row_factory = sqlite3.Row
    return conn
    
def calculate_attendance_percentage(db, user_id, internship_id):
    query = """
    SELECT 
        (SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) * 100.0)
        / COUNT(*) AS attendance_percentage
    FROM attendance
    WHERE user_id = ? AND internship_id = ?;
    """

    result = db.execute(query, (user_id, internship_id)).fetchone()

    if result is None or result["attendance_percentage"] is None:
        return None   # <-- VERY IMPORTANT for Step 3

    return round(result["attendance_percentage"], 2)
