"""
THE AI AGENT. Run this once a week (whenever you open your laptop - no
phone cable needed, Syncthing keeps the folders in sync over Wi-Fi already).

What makes this an "agent" and not just a script:
  - It doesn't just upload blindly. When it finds a cluster of near-identical
    shots taken seconds apart (burst photos, "just in case" retakes), it
    shows them to an AI vision model and asks it to judge which one is
    actually the best (sharpest, best framed, eyes open, etc.) and whether
    the rest are true throwaways.
  - It only uploads the keeper(s). The rest go to a local "Review_Before_Delete"
    folder on your PC (never auto-deleted from your phone) so you can glance
    and confirm before removing them for good.
  - It writes you a short plain-English summary of everything it did.

Requires:
  - OPENAI_API_KEY set as an environment variable (see README.md)
  - Google account tokens already created via auth_setup.py
  - Syncthing already mirroring your phone folders (see README.md)

Privacy note: photo thumbnails from burst-clusters are sent to OpenAI's API
for the AI judgment step. Photos with no near-duplicates are never sent
anywhere except your own Google account.
"""

import json
import os
import hashlib
import base64
import io
import shutil
from collections import defaultdict

import requests
from PIL import Image
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

CONFIG_FILE = "config.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".3gp", ".mkv"}
VALID_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

UPLOAD_URL = "https://photoslibrary.googleapis.com/v1/uploads"
BATCH_CREATE_URL = "https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


# ---------- small helpers ----------

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def file_fingerprint(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def get_credentials(token_file):
    creds = Credentials.from_authorized_user_file(token_file)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "w") as f:
            f.write(creds.to_json())
    return creds


# ---------- Google Photos upload ----------

def upload_file(filepath, creds):
    access_token = creds.token
    filename = os.path.basename(filepath)

    with open(filepath, "rb") as f:
        file_bytes = f.read()

    upload_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-type": "application/octet-stream",
        "X-Goog-Upload-Content-Type": "application/octet-stream",
        "X-Goog-Upload-Protocol": "raw",
    }
    resp = requests.post(UPLOAD_URL, headers=upload_headers, data=file_bytes)
    resp.raise_for_status()
    upload_token = resp.text

    batch_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-type": "application/json",
    }
    body = {"newMediaItems": [{"description": filename, "simpleMediaItem": {"uploadToken": upload_token}}]}
    resp = requests.post(BATCH_CREATE_URL, headers=batch_headers, json=body)
    resp.raise_for_status()
    status = resp.json()["newMediaItemResults"][0]["status"]
    if status.get("code") and status["code"] != 0:
        raise RuntimeError(f"Upload failed for {filename}: {status}")


# ---------- AI burst-cluster judging ----------

def image_to_data_url(path, max_size=512):
    """Shrink an image before sending it to the AI - keeps things fast and cheap."""
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_size, max_size))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def ask_ai_which_to_keep(filepaths, api_key):
    """
    Sends a small cluster of similar photos to the AI and asks which to keep.
    Returns a list of filenames to KEEP; everything else in the cluster is
    treated as a throwaway.
    """
    content = [{
        "type": "text",
        "text": (
            "These images were taken within seconds of each other on the same phone "
            "(likely burst shots or retakes of the same moment). "
            "Pick the best one(s) to keep (sharpest focus, best framing/expression). "
            "It's fine to keep more than one if they're meaningfully different. "
            "Respond ONLY with JSON: {\"keep\": [<index numbers starting at 0>], \"reason\": \"...\"}"
        ),
    }]
    for idx, path in enumerate(filepaths):
        content.append({"type": "text", "text": f"Image index {idx}: {os.path.basename(path)}"})
        content.append({"type": "image_url", "image_url": {"url": image_to_data_url(path)}})

    body = {
        "model": CONFIG.get("openai_model", "gpt-4o-mini"),
        "messages": [{"role": "user", "content": content}],
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = requests.post(OPENAI_URL, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    result = json.loads(resp.json()["choices"][0]["message"]["content"])
    keep_indices = result.get("keep", list(range(len(filepaths))))  # default: keep all if unsure
    return [filepaths[i] for i in keep_indices if 0 <= i < len(filepaths)], result.get("reason", "")


def summarize_run(events, api_key):
    """Ask the AI to write a short, friendly summary of what happened this run."""
    prompt = (
        "Write a short (3-5 sentence) friendly summary of this photo backup run for the user. "
        "Be specific with numbers. Here is the raw log:\n\n" + "\n".join(events)
    )
    body = {
        "model": CONFIG.get("openai_model", "gpt-4o-mini"),
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        resp = requests.post(OPENAI_URL, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        return "\n".join(events)  # fall back to raw log if the summary call fails


# ---------- main ----------

CONFIG = {}


def main():
    global CONFIG
    CONFIG = load_json(CONFIG_FILE, None)
    if CONFIG is None:
        print("ERROR: config.json not found.")
        return

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set. See README.md.")
        return

    manifest = load_json(CONFIG["manifest_file"], {})
    os.makedirs(CONFIG["review_folder"], exist_ok=True)

    events = []
    burst_window = CONFIG.get("burst_window_seconds", 8)

    for account in CONFIG["accounts"]:
        name = account["name"]
        folder = account["watch_folder"]
        token_file = account["token_file"]

        if not os.path.isdir(folder):
            events.append(f"[{name}] watch folder not found, skipped: {folder}")
            continue
        if not os.path.exists(token_file):
            events.append(f"[{name}] no login token yet, skipped (run auth_setup.py {name})")
            continue

        creds = get_credentials(token_file)

        # find new files (not already in manifest)
        new_files = []
        for fname in os.listdir(folder):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in VALID_EXTENSIONS:
                continue
            fpath = os.path.join(folder, fname)
            fp = file_fingerprint(fpath)
            if fp not in manifest:
                new_files.append((fpath, fp, os.path.getmtime(fpath)))

        if not new_files:
            events.append(f"[{name}] no new files this run")
            continue

        # cluster images (not videos) taken within burst_window seconds of each other
        new_files.sort(key=lambda x: x[2])
        clusters = []
        current_cluster = []
        for fpath, fp, mtime in new_files:
            is_image = os.path.splitext(fpath)[1].lower() in IMAGE_EXTENSIONS
            if not is_image:
                clusters.append([(fpath, fp, mtime)])  # videos always go alone
                continue
            if current_cluster and (mtime - current_cluster[-1][2]) <= burst_window:
                current_cluster.append((fpath, fp, mtime))
            else:
                if current_cluster:
                    clusters.append(current_cluster)
                current_cluster = [(fpath, fp, mtime)]
        if current_cluster:
            clusters.append(current_cluster)

        uploaded_count = 0
        reviewed_count = 0

        for cluster in clusters:
            if len(cluster) == 1:
                to_keep = [cluster[0][0]]
                to_review = []
            else:
                paths = [c[0] for c in cluster]
                try:
                    to_keep, reason = ask_ai_which_to_keep(paths, api_key)
                except Exception as e:
                    events.append(f"[{name}] AI judging failed ({e}), keeping all in cluster")
                    to_keep = paths
                to_review = [p for p in paths if p not in to_keep]

            for fpath in to_keep:
                fp = file_fingerprint(fpath)
                try:
                    upload_file(fpath, creds)
                    manifest[fp] = {"account": name, "filename": os.path.basename(fpath)}
                    save_json(CONFIG["manifest_file"], manifest)
                    uploaded_count += 1
                except Exception as e:
                    events.append(f"[{name}] FAILED upload {os.path.basename(fpath)}: {e}")

            for fpath in to_review:
                dest = os.path.join(CONFIG["review_folder"], os.path.basename(fpath))
                shutil.move(fpath, dest)
                reviewed_count += 1

        events.append(f"[{name}] uploaded {uploaded_count} file(s), sent {reviewed_count} likely-throwaway shot(s) to Review_Before_Delete")

    print("\n--- Run log ---")
    for e in events:
        print(e)

    print("\n--- AI Summary ---")
    print(summarize_run(events, api_key))

    print(f"\nCheck '{CONFIG['review_folder']}' and delete anything you agree is a throwaway - "
          f"nothing there was removed from your phone automatically.")


if __name__ == "__main__":
    main()
