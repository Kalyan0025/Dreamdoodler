import google.generativeai as gen
import os

# Option 1 — read key from environment (if you set it locally)
api_key = os.getenv("GEMINI_API_KEY")

# Option 2 — paste your key directly here temporarily for the test
# api_key = "YOUR_API_KEY_HERE"

if not api_key:
    raise SystemExit("No GEMINI_API_KEY set in your environment")

gen.configure(api_key=api_key)

model = gen.GenerativeModel("gemini-pro")

resp = model.generate_content("Say 'hello' in one short sentence.")
print("RAW RESPONSE:")
print(resp)
print("\nTEXT:")
print(resp.text)
