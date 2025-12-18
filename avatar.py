def get_avatar_response(attendance_percentage, risk_level, predicted_score):
    # Priority 1: High risk
    if risk_level == "High":
        return {
            "state": "risk",
            "message": "You are at high risk. Improve attendance and task consistency immediately."
        }

    # Priority 2: Attendance issues
    if attendance_percentage < 75:
        return {
            "state": "warning",
            "message": "Your attendance is low. Try to be more consistent."
        }

    # Priority 3: Good performance
    if predicted_score >= 80:
        return {
            "state": "happy",
            "message": "Great work! Your performance is on track."
        }

    # Default
    return {
        "state": "neutral",
        "message": "Keep working steadily. You are doing fine."
    }
