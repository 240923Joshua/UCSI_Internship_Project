INTENT_PRIORITY = [
    "attendance",
    "risk",
    "weekly_guidance",
    "performance",
    "general_internship",
    "greeting",
    "farewell",
]


INTENT_KEYWORDS = {
    "attendance": ["attendance", "absent", "present", "late"],
    "performance": ["performance", "improve", "score", "marks", "struggling"],
    "risk": ["risk", "warning", "fail"],
    "weekly_guidance": ["week", "weekly", "focus"],
    "general_internship": ["internship", "mentor", "guidance"],
    "greeting": ["hello", "hi", "hey", "greetings"],
    "farewell": ["bye", "goodbye", "see you", "later"]
}

def detect_intent_with_confidence(message: str):
    message = message.lower()

    scores = {}

    for intent, keywords in INTENT_KEYWORDS.items():
        scores[intent] = sum(1 for word in keywords if word in message)

    # Remove zero-score intents
    scores = {k: v for k, v in scores.items() if v > 0}

    # No match at all
    if not scores:
        return {
            "intent": "unsupported",
            "confidence": "none"
        }

    # Sort by highest score
    sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    top_intent, top_score = sorted_intents[0]

    top_score_intents = [intent for intent, score in scores.items() if score == top_score]

    if len(top_score_intents) > 1:
        # Resolve tie using priority
        for intent in INTENT_PRIORITY:
            if intent in top_score_intents:
                return {
                    "intent": intent,
                    "confidence": "high"
                }

    # Single weak match
    if top_score == 1:
        return {
            "intent": top_intent,
            "confidence": "low"
        }

    # Strong match
    return {
        "intent": top_intent,
        "confidence": "high"
    }


# for debugging purposes
#print(detect_intent_with_confidence(input()))