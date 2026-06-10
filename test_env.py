import os
from dotenv import load_dotenv
from pathlib import Path

print("--- Running test_env.py ---")
print("Current working directory:", os.getcwd())

# Try loading from the current directory explicitly
dotenv_path = Path('./.env')
if dotenv_path.is_file():
    print(f"'.env' file found at: {dotenv_path.resolve()}")
    success = load_dotenv(dotenv_path=dotenv_path)
    print(f"load_dotenv() returned: {success}") # Should be True if loaded variables
else:
    print("Error: '.env' file NOT found at expected path.")
    success = False # Indicate failure if file not found

print("\n--- Environment Variables After Load ---")
telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
google_key = os.getenv("GOOGLE_API_KEY")

print(f"Retrieved TELEGRAM_BOT_TOKEN: '{telegram_token}' (Length: {len(telegram_token) if telegram_token else 'None'})")
print(f"Retrieved GOOGLE_API_KEY: '{google_key}' (Length: {len(google_key) if google_key else 'None'})")

if telegram_token and google_key:
    print("\nSUCCESS: Both keys loaded successfully!")
else:
    print("\nFAILURE: One or both keys failed to load.")
print("--- End test_env.py ---")