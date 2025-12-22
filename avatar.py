def get_avatar_response(attendance_percentage, risk_level, predicted_score):
    # Priority 1: High risk
    stateDict = [{"state": "risk", "message": "Your performance is at high risk. Immediate action is required."},
    {"state": "warning", "message": "Your attendance is low. Try to be more consistent."}, 
    {"state": "happy", "message": "Great work! Your performance is on track."}, 
    {"state": "neutral", "message": "Keep working steadily. You are doing fine."}]
    
    if attendance_percentage is None or predicted_score is None or risk_level is None:
        return {"state": "neutral", "message": "Insufficient data to determine avatar state."}

    if risk_level == "High":
        return stateDict[0]

    # Priority 2: Attendance issues
    if attendance_percentage < 75:
        return stateDict[1]

    # Priority 3: Good performance
    if predicted_score >= 80:
        return stateDict[2]

    # Default
    return stateDict[3]
