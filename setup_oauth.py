#!/usr/bin/env python3
"""
YouTube OAuth Token Generator for GitHub Actions
==================================================
Run this script ONCE on your local machine (with a web browser) to generate
the OAuth refresh token needed for headless GitHub Actions runs.

Instructions:
1. Go to Google Cloud Console (https://console.cloud.google.com).
2. Enable 'YouTube Data API v3'.
3. Create OAuth 2.0 Credentials (Desktop App) and download 'client_secret.json'.
4. Place 'client_secret.json' in this folder and run:
       python setup_oauth.py
5. Copy the printed JSON output and paste it into GitHub Repository Secrets as:
       YOUTUBE_CLIENT_SECRET
"""

import os
import json
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = "client_secret.json"
TOKEN_OUTPUT_FILE = "token.json"

def main():
    print("=" * 60)
    print("  YouTube Data API v3 - Headless Token Generator")
    print("=" * 60)

    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"[ERROR] '{CLIENT_SECRETS_FILE}' not found in current directory.")
        print("Please download your OAuth 2.0 Desktop Client JSON from Google Cloud Console")
        print(f"and save it as '{CLIENT_SECRETS_FILE}' here.\n")
        sys.exit(1)

    print("\nStarting local browser authentication flow...")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    creds = flow.run_local_server(port=8080, prompt="consent", access_type="offline")

    token_json_str = creds.to_json()

    with open(TOKEN_OUTPUT_FILE, "w") as f:
        f.write(token_json_str)

    print("\n" + "=" * 60)
    print("✅ AUTHENTICATION SUCCESSFUL!")
    print("=" * 60)
    print(f"Saved local credentials to '{TOKEN_OUTPUT_FILE}'.")
    print("\n👉 COPY THE ENTIRE JSON BLOCK BELOW AND ADD IT AS A GITHUB SECRET:")
    print("   Repository -> Settings -> Secrets and variables -> Actions")
    print("   Name: YOUTUBE_CLIENT_SECRET")
    print("-" * 60)
    print(token_json_str)
    print("-" * 60)
    print("\nWith this secret configured, GitHub Actions will publish daily without browser prompts!\n")

if __name__ == "__main__":
    main()
