LAST_MESSAGE = {}

def get_last_message(user_id, internship_id):
    return LAST_MESSAGE.get((user_id, internship_id))

def set_last_message(user_id, internship_id, message):
    LAST_MESSAGE[(user_id, internship_id)] = message
