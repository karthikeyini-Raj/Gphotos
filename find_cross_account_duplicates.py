"""
ONE-TIME cleanup helper for photos that were already duplicated across your
3 accounts BEFORE this agent existed.

Google does not allow any script to delete photos it didn't upload itself,
so this can't delete anything automatically - but it does 95% of the tedious
work by finding every duplicate for you and telling you exactly which copies
to keep and which to trash.

Setup (one-time, manual - Google requires this, no way around it):
  1. Go to https://takeout.google.com for Account 1 -> select only Google
     Photos -> export -> download & unzip -> note the folder path.
  2. Repeat for Account 2 and Account 3.
  3. Edit the EXPORT_FOLDERS list below with the 3 unzip locations.

Then run:
    python find_cross_account_duplicates.py

Output: duplicates_report.csv - open it in Excel. Each row is one duplicate
group: which accounts have a copy, and which file to KEEP (the earliest one)
vs which to manually trash from the other account(s) in the Google Photos
website.
"""

import os
import hashlib
import csv

# EDIT THESE 3 PATHS to where you unzipped each account's Takeout export
EXPORT_FOLDERS = {
    "account1": "C:/Takeout/account1/Google Photos",
    "account2": "C:/Takeout/account2/Google Photos",
    "account3": "C:/Takeout/account3/Google Photos",
}

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

    with open("duplicates_report.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fingerprint", "keep_account", "keep_file", "trash_account", "trash_file"])

        for fp, entries in duplicate_groups.items():
            entries_sorted = sorted(entries, key=lambda e: e[2])  # oldest first
            keep = entries_sorted[0]
            for trash in entries_sorted[1:]:
                writer.writerow([fp[:12], keep[0], keep[1], trash[0], trash[1]])

    print(f"Found {len(duplicate_groups)} duplicate group(s) across your accounts.")
    print("Full details written to duplicates_report.csv - open it in Excel.")
    print("\nFor each row: keep the 'keep_file' copy, and manually delete the")
    print("'trash_file' copy from that account in Google Photos (search by")
    print("filename or date to find it fast).")


if __name__ == "__main__":
    main()
