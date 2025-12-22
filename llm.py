import os
os.environ["HF_HOME"] = "hf_cache"

from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"

MODEL_ID = "google/gemma-2b-it"  # you already used this earlier

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    dtype=torch.float16 if device == "cuda" else torch.float32
)

model = model.to(device)

def generate_response(prompt, max_tokens=150):
    inputs = tokenizer(prompt, return_tensors="pt")
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_tokens,
        do_sample=True,
        temperature=0.7,
        top_p=0.9
    )
    full_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    reply = full_text[len(prompt):].strip()

    return reply

def build_avatar_prompt(
    attendance_percentage,
    predicted_score,
    risk_level,
    internship_domain,
    user_question
):
    return f"""
You are a virtual internship mentor.
Your role is to guide interns in a teacher-like, supportive way.

Intern data:
- Internship domain: {internship_domain}
- Attendance percentage: {attendance_percentage}%
- Predicted performance score: {predicted_score}
- Risk level: {risk_level}

Rules:
- Answer ONLY internship-related questions
- Be supportive and constructive
- Do not give medical, legal, or personal advice
- Keep response under 5 sentences

Intern asks:
"{user_question}"

Respond like a mentor:
"""

# Example interaction loop (uncomment to use)

# choice = 'y'

# while choice.lower() == "y":
#     user_input = input("You: ")
#     response = generate_response(user_input)
#     print("Gemma: ", response)
#     choice = input("Do you want to continue the chat? (y/n): ")
    
