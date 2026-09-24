"""
Run this ONCE per Google account (3 times total) to create a saved login token.

Usage:
    python auth_setup.py account1
    python auth_setup.py account2
    python auth_setup.py account3

Each run opens your browser, asks you to log into ONE Google account, and
saves a file called token_<name>.json in this folder. After that, the
upload agent uses this file forever and never needs you to log in again
(unless you revoke access).

Requires a "credentials.json" file in this same folder, downloaded from
Google Cloud Console (see README.md, Step 1).
"""

import sys
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/photoslibrary.appendonly",
    "https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata",
]

def main():
    if len(sys.argv) != 2:
        print("Usage: python auth_setup.py <account_name>")
        print("Example: python auth_setup.py account1")
        sys.exit(1)

    name = sys.argv[1]
    token_file = f"token_{name}.json"

    if not os.path.exists("credentials.json"):
        print("ERROR: credentials.json not found in this folder.")
        print("Download it from Google Cloud Console first (see README.md Step 1).")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)

    with open(token_file, "w") as f:
        f.write(creds.to_json())

    print(f"\nSuccess! Saved login for '{name}' to {token_file}")
    print("Now add this account + its watch folder to config.json")

if __name__ == "__main__":
    main()
