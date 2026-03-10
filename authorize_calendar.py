from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ["https://www.googleapis.com/auth/calendar"]

flow = InstalledAppFlow.from_client_secrets_file("google_credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("google_token.json", "w") as f:
    f.write(creds.to_json())

print("Authorization complete! google_token.json saved.")
