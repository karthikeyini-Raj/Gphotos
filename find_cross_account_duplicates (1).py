"""
ONE-TIME cleanup helper for photos already duplicated across your 3
accounts BEFORE the weekly agent existed.

Google blocks any script from reading your full existing library live, or
from deleting photos it didn't upload itself - so this can't touch your
actual Google accounts directly. What it CAN do is compare exports of all
3 accounts and hand you a ready-to-review folder + report, so the manual
part (deleting on photos.google.com) takes minutes instead of hours.

Setup (one-time, manual - required by Google, no way around it):
  1. https://takeout.google.com for Account 1 -> select ONLY Google Photos
     -> export -> download & unzip -> note the folder path.
  2. Repeat for Account 2 and Account 3.
  3. Edit EXPORT_FOLDERS below with the 3 unzip locations.

Run:
    python find_cross_account_duplicates.py

Output:
  - duplicates_report.csv        - full details, open in Excel
  - Duplicates_To_Delete/ folder - actual copies of every DUPLICATE (the
    "keep" copy is left out), renamed with the account name so you know
    exactly where to go delete it from. Browse this folder, then delete
    the matching photo in that account's Google Photos (search by
    filename/date shown in the copied file's name).

Deleting files from this local folder does NOT delete anything from your
real Google Photos accounts - it's just for your review. The actual
deletion still happens on photos.google.com, one click per photo.
"""

import os
import hashlib
import csv
import shutil

# EDIT THESE 3 PATHS to where you unzipped each account's Takeout export
EXPORT_FOLDERS = {
    "account1": "C:/Takeout/account1/Google Photos",
    "account2": "C:/Takeout/account2/Google Photos",
    "account3": "C:/Takeout/account3/Google Photos",
}

REVIEW_FOLDER = "Duplicates_To_Delete"
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".mp4", ".mov", ".3gp", ".mkv"}


def file_fingerprint(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    fingerprints = {}  # hash -> list of (account, filepath, mtime)

    for account, folder in EXPORT_FOLDERS.items():
        if not os.path.isdir(folder):
            print(f"WARNING: folder not found for {account}: {folder} (skipping)")
            continue

        for root, _, files in os.walk(folder):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in VALID_EXTENSIONS:
                    continue
                fpath = os.path.join(root, fname)
                try:
                    fp = file_fingerprint(fpath)
                    mtime = os.path.getmtime(fpath)
                except OSError:
                    continue
                fingerprints.setdefault(fp, []).append((account, fpath, mtime))

    duplicate_groups = {fp: entries for fp, entries in fingerprints.items() if len(entries) > 1}

    os.makedirs(REVIEW_FOLDER, exist_ok=True)
    copied_count = 0

    with open("duplicates_report.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fingerprint", "keep_account", "keep_file", "trash_account", "trash_file", "copied_to"])

        for fp, entries in duplicate_groups.items():
            entries_sorted = sorted(entries, key=lambda e: e[2])  # oldest first = the one to keep
            keep = entries_sorted[0]

            for trash in entries_sorted[1:]:
                trash_account, trash_path, _ = trash
                original_name = os.path.basename(trash_path)
                # prefix with account name so you know where to go delete it from,
                # and so two files with the same name from different accounts don't collide
                safe_name = f"{trash_account}__{original_name}"
                dest_path = os.path.join(REVIEW_FOLDER, safe_name)

                # handle any remaining name collisions
                counter = 1
                base, ext = os.path.splitext(dest_path)
                while os.path.exists(dest_path):
                    dest_path = f"{base}_{counter}{ext}"
                    counter += 1

                shutil.copy2(trash_path, dest_path)
                copied_count += 1

                writer.writerow([fp[:12], keep[0], keep[1], trash_account, trash_path, dest_path])

    print(f"Found {len(duplicate_groups)} duplicate group(s) across your accounts.")
    print(f"Copied {copied_count} duplicate file(s) into '{REVIEW_FOLDER}/' for you to review.")
    print(f"Full details in duplicates_report.csv (open in Excel).")
    print(f"\nNext step: browse '{REVIEW_FOLDER}/', and for each file, go delete the matching")
    print(f"photo from that account in Google Photos (the filename tells you which account -")
    print(f"e.g. 'account2__IMG_1234.jpg' means go delete it from account2).")


if __name__ == "__main__":
    main()
