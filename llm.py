import os
import re
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
MODEL_ID = "google/gemma-2-2b-it"

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
    model_name="tts_models/en/vctk/vits",
    progress_bar=False,
).to(device)

def clean_text_for_tts(text: str) -> str:
    # Remove emojis / non-ascii
    text = text.encode("ascii", "ignore").decode()

    # Remove markdown symbols
    text = re.sub(r"[*_#>`~\-]", " ", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Minimum length safety
    if len(text.split()) < 6:
        text += " Please continue working consistently."

    # Ensure punctuation
    if not text.endswith((".", "!", "?")):
        text += "."

    return text

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
def synthesize_speech(text, output_file="static/audio/response.wav"):
    print("🔊 Synthesizing speech...")
    safe_text = clean_text_for_tts(text)
    tts.tts_to_file(text=safe_text, file_path=output_file,speaker="p262")
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
You are a virtual internship mentor and teacher.

Your role:
- Help interns only with internship-related topics
- Speak in a calm, supportive, teacher-like manner
- Give short, practical guidance

Intern context (for reference only, do not repeat):
- Internship domain: {internship_domain}
- Attendance percentage: {attendance_percentage}%
- Predicted performance score: {predicted_score}
- Risk level: {risk_level}

Rules:
- Respond in plain sentences only
- Do not use bullet points, lists, markdown, or emojis
- Keep responses concise (3 to 4 sentences)
- Do not repeat the intern data
- Do not ask follow-up questions
- Do not mention being an AI model
- Do not hallucinate or make up facts

Decision step (do NOT show this step in the answer):
- If the question is related to internships, learning, skills, performance, attendance, communication, or professional growth, then answer it as a mentor.
- If the question is NOT related to internships or professional development, politely say that you can only help with internship-related topics.

Intern question:
{user_question}

Last Message in context:
{memory if memory else "No previous messages."}

Mentor response:

"""


# choice = "y"
# while choice.lower() == "y":
#     user_input = input("You: ")
#     response = generate_response(user_input)
#     print("Gemma: ", response)
#     synthesize_speech(response, output_file="response.wav")


#     choice = input("Do you want to continue the chat? (y/n): ")
