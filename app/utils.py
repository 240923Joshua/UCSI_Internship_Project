import os
from flask import current_app

def allowed_file(filename):
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def get_skill_stats(db, user_id, internship_id):
    cursor = db.execute("""
        SELECT focus_skill, skill_rating
        FROM weekly_reports
        WHERE user_id = ?
          AND internship_id = ?
          AND skill_rating IS NOT NULL
    """, (user_id, internship_id))

    rows = cursor.fetchall()

    skills = {}

    for row in rows:
        skill = row["focus_skill"]
        rating = row["skill_rating"]

        skills.setdefault(skill, []).append(rating)

    skill_stats = []

    for skill, ratings in skills.items():
        avg = sum(ratings) / len(ratings)
        percentage = round((avg / 10) * 100)

        if avg >= 8:
            level = "Advanced"
        elif avg >= 6:
            level = "Intermediate"
        else:
            level = "Developing"

        skill_stats.append({
            "name": skill,
            "avg": round(avg, 1),
            "percentage": percentage,
            "level": level,
            "reports": len(ratings)
        })

    skill_stats.sort(key=lambda x: x["percentage"], reverse=True)
    return skill_stats

def myProgressPercentage(db, user_id):
    internships = db.execute("""
    SELECT COUNT(internship_id) AS total_internships
    FROM internship
    WHERE user_id = ?
    """, (user_id,)).fetchone()["total_internships"]
    
    ml_results = db.execute("""
    SELECT SUM(predicted_score) AS total_score
    FROM ml_results
    WHERE user_id = ?
    """, (user_id,)).fetchone()["total_score"]
    
    if internships == 0:
        return 0
    ml_results = ml_results if ml_results else 0
    return round(ml_results / internships, 2)
