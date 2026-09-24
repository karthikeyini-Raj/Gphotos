# Photo Backup AI Agent - Setup Guide

Run this once a week whenever you're at your laptop. No phone cable needed -
your phone folders sync to your PC automatically over Wi-Fi in the
background (near-zero battery cost), and the AI agent does the smart work
whenever you open your laptop.

---

## Step 1: Get credentials.json from Google (one-time, ~10 min)

1. https://console.cloud.google.com/ -> sign in with any one of your accounts.
2. New Project -> name it anything -> Create.
3. Search "Photos Library API" -> Enable.
4. APIs & Services -> OAuth consent screen -> External -> fill basic info ->
   under "Test users" add all 3 of your Gmail addresses.
5. APIs & Services -> Credentials -> Create Credentials -> OAuth client ID
   -> Application type: Desktop app -> Create -> Download JSON.
6. Rename the downloaded file to `credentials.json`, put it in this folder.

## Step 2: Get your OpenAI API key ready

You said you already have one. Set it as an environment variable so it's
never stored in a plain file:

**Windows (Command Prompt, run once):**
```
setx OPENAI_API_KEY "sk-your-key-here"
```
Close and reopen Command Prompt after this for it to take effect.

## Step 3: Install Python + packages

Install Python from https://python.org (tick "Add to PATH"). Then in this
folder:
```
pip install -r requirements.txt
```

## Step 4: Log into each of your 3 Google accounts (one-time)

```
python auth_setup.py account1
python auth_setup.py account2
python auth_setup.py account3
```
Browser opens each time - log into the matching account, click Allow.

## Step 5: Sync phone folders to PC with Syncthing (one-time setup, then automatic forever)

This replaces "connecting the phone every week" - it happens quietly over
Wi-Fi with almost no battery cost, since it only activates when there's an
actual new file, not on a timer.

1. Phone: install **Syncthing** from Play Store.
2. PC: install Syncthing from https://syncthing.net.
3. On the phone app, share 3 folders: Camera (DCIM/Camera), WhatsApp
   Images, Screenshots.
4. On the PC, accept them into:
   - `C:/PhotosSync/Camera`
   - `C:/PhotosSync/WhatsApp`
   - `C:/PhotosSync/Screenshots`
5. Leave both apps running in the background. That's it - no more manual
   connecting, ever.

## Step 6: Run the agent (this is your weekly routine)

Whenever you're at your laptop - once a week is perfect:

```
python weekly_agent.py
```

What it does automatically:
- Finds every new photo since last time (skips anything already uploaded -
  to any of your 3 accounts, so duplicates across accounts are impossible).
- Groups burst/near-identical shots taken seconds apart.
- Asks the AI to judge which ones in each group are actually worth keeping.
- Uploads the keepers to the correct account.
- Moves the likely throwaways into `C:/PhotosSync/Review_Before_Delete`
  for you to glance at and delete - nothing is removed from your phone
  automatically.
- Prints a friendly summary of what it did.

That's the entire weekly routine - one command, a few seconds of your time.

## Step 7: Free up phone storage

Once you've confirmed a batch is uploaded, use **Google Photos app ->
profile icon -> Free up device space** on your phone. It only deletes
photos it's confirmed are safely backed up.

## Step 8 (one-time): Clean up duplicates that already existed before this agent

Use `find_cross_account_duplicates.py` - see the comments at the top of
that file. This is a one-time job, not part of the weekly routine.

---

### A note on privacy
When the AI judges burst-photo clusters, small resized copies of those
specific photos are sent to OpenAI's API for that judgment call. Photos
with no similar duplicates nearby are never sent anywhere except your own
Google account.
