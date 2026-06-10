import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv() # Make sure this loads your GOOGLE_API_KEY correctly
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

print("Attempting to list models...")
try:
    models = genai.list_models()
    for model in models:
        print(f"Model Name: {model.name} | Supported Methods: {model.supported_generation_methods}")
    if not list(models): # Convert to list to check if empty
        print("\nNo generative models found for your current region/API key.")
except Exception as e:
    print(f"\nAn error occurred while listing models: {e}")
    print("This often indicates a region restriction or an invalid API key.")
print("--- Model Listing Complete ---")