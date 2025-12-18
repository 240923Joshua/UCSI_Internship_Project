from pyexpat.errors import messages
from transformers import pipeline
import torch
import pyttsx3
from huggingface_hub import login
with open(r"C:\Users\PROBOOK\Documents\token_key.txt") as file:
    key = file.read()

login(token=key)
def speak(text):
    engine = pyttsx3.init()
    engine.setProperty('rate', 150) 
    engine.say(text)
    engine.runAndWait()
    engine.stop()
    
pipe = pipeline("text-generation", model="google/gemma-3-1b-it", torch_dtype=torch.bfloat16)

def get_response(prompt):
    messages = [
    [
        {
            "role": "system",
            "content": [{"type": "text", "text": "You are a helpful assistant."},]
        },
        {
            "role": "user",
            "content": [{"type": "text", "text": prompt},]
        },
    ]
    ]
    output = pipe(messages, max_new_tokens=150)
    return str(output[0][0]['generated_text'][2]['content'])

exit_con = {"quit", "exit", "goodbye", "bye"}
print("Chatbot: Hi there! How can I help you?")
speak("Hi there! How can I help you?")
while True:
    user_input = input("You: ")
    if user_input.lower() in exit_con:
        print("Chatbot: Goodbye!")
        speak("Goodbye!")
        break
    response = get_response(user_input)
    print("Chatbot:", response)
    speak(str(response))