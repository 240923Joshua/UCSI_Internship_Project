from flask import Flask, request, jsonify, render_template
from transformers import pipeline
import torch
import pyttsx3
from huggingface_hub import login

# -------- LOGIN --------
with open(r"C:\Users\PROBOOK\Documents\token_key.txt") as file:
    key = file.read()

login(token=key)

# -------- FLASK APP --------
app = Flask(__name__)

# -------- TEXT TO SPEECH --------
def speak(text):
    engine = pyttsx3.init()
    engine.setProperty("rate", 150)
    engine.say(text)
    engine.runAndWait()
    engine.stop()

# -------- MODEL --------
pipe = pipeline(
    "text-generation",
    model="google/gemma-3-1b-it",
    device="cpu",
    trust_remote_code=True
)

# -------- AI RESPONSE --------
def get_response(prompt):
    prompt_text = (
        "You are a helpful assistant.\n"
        f"User: {prompt}\n"
        "Assistant:"
    )

    output = pipe(prompt_text, max_new_tokens=150, do_sample=True)
    return output[0]["generated_text"].split("Assistant:")[-1].strip()


# -------- ROUTES --------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_input = request.json["message"]
        response = get_response(user_input)
   
        speak(response)
        return jsonify({"reply": response})
    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({"error": str(e)}), 500
# -------- RUN --------
if __name__ == "__main__":
    app.run(debug=True)
