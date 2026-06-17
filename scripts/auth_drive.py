"""
One-time OAuth2 authorisation for Google Drive.

Run this once to authorise the app to upload files to your Drive.
A token file is saved and reused automatically for all future runs.

Steps:
  1. Go to GCP Console → APIs & Services → Credentials
  2. Create Credentials → OAuth client ID → Desktop app → Download JSON
  3. Save the JSON to the path set in GOOGLE_OAUTH_CLIENT_JSON (.env)
  4. Run: python3 scripts/auth_drive.py
  5. A browser window opens → sign in with your Google account → allow access
  6. Token saved to credentials/drive_token.json
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv(Path(__file__).parent.parent / ".env")

# Full Drive scope (not drive.file): drive.file can only see files this OAuth client
# created, so hand-copied / web-UI date folders are invisible. Full scope lets the
# pipeline read and re-upload those folders too. Must match lib/drive_client.py SCOPES.
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

client_json = os.getenv("GOOGLE_OAUTH_CLIENT_JSON", "")
token_json = str(Path(__file__).parent.parent / "credentials" / "drive_token.json")

if not client_json or not Path(client_json).exists():
    print("Set GOOGLE_OAUTH_CLIENT_JSON in .env to the path of your OAuth2 client credentials.")
    print("Download it from: GCP Console → APIs & Services → Credentials → OAuth 2.0 Client IDs")
    sys.exit(1)

flow = InstalledAppFlow.from_client_secrets_file(client_json, SCOPES)
creds = flow.run_local_server(port=0, open_browser=True)

token_path = Path(token_json)
token_path.parent.mkdir(parents=True, exist_ok=True)
token_path.write_text(creds.to_json())
print(f"Token saved to {token_path}")
print("Drive uploads will now use your personal Google account.")
