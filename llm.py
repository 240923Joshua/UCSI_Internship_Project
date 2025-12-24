import os
os.environ["HF_HOME"] = "hf_cache"
os.environ["TORCH_HOME"] = "torch_cache"
os.environ["TTS_HOME"] = "tts_cache"

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from TTS.api import TTS

# -----------------------------
# DEVICE SETUP
# -----------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# -----------------------------
# LLM SETUP
# -----------------------------
MODEL_ID = "google/gemma-2b-it"

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    dtype=torch.float16 if device == "cuda" else torch.float32
)
model = model.to(device)
model.eval()

# -----------------------------
# TTS SETUP (STABLE MODEL)
# -----------------------------
tts = TTS(
    model_name="tts_models/en/ljspeech/tacotron2-DDC",
    progress_bar=False
).to(device)

# -----------------------------
# LLM RESPONSE GENERATION
# -----------------------------
def generate_response(prompt, max_tokens=90):
    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9
        )

    full_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

    # Remove prompt from output
    reply = full_text[len(prompt):].strip()
    return reply


# -----------------------------
# TTS FUNCTION
# -----------------------------
def synthesize_speech(text, output_file="response.wav"):
    print("🔊 Synthesizing speech...")
    tts.tts_to_file(
        text=text,
        file_path=output_file
    )
    print(f"✅ Audio saved as {output_file}")

def build_avatar_prompt(
    attendance_percentage,
    predicted_score,
    risk_level,
    internship_domain,
    user_question,
    memory
):
    return f"""
You are a virtual internship mentor.
Your role is to guide interns in a teacher-like, supportive way.

Intern data:
- Internship domain: {internship_domain}
- Attendance percentage: {attendance_percentage}%
- Predicted performance score: {predicted_score}
- Risk level: {risk_level}

Guidelines for your response:
- Speak like a supportive internship mentor or teacher
- Be clear, calm, and encouraging
- Explain briefly before giving advice
- Give 1–2 actionable suggestions
- Keep the response concise (3–5 sentences)
- Do not repeat the intern data
- Do not ask follow-up questions
- Use positive and motivating language
- No emojis, slang, or internet abbreviations
- No text formatting

Tone example:
"Consistent attendance helps build discipline and trust. Small daily improvements can make a big difference."

Intern asks:
"{user_question}"

Last message in context:
"{memory}"

Respond like a mentor:
"""

# -----------------------------
# QUICK MANUAL TEST
# -----------------------------
# choice = "y"
# while choice.lower() == "y":
#     user_input = input("You: ")
#     response = generate_response(user_input)
#     print("Gemma: ", response)
#     synthesize_speech(response, output_file="response.wav")
#     choice = input("Do you want to continue the chat? (y/n): ")
