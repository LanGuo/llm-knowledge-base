"""
One-off downloader for the paper list in https://github.com/thinkwee/awesomeopd
Fetches full-text PDFs from arXiv where available, falling back to the
abstract page when the PDF can't be retrieved. Output goes to raw/distillation/,
which is picked up by `python lkb.py sync` as a tracked source.
"""
import os
import re
import time
import requests
from pathlib import Path

ARXIV_IDS_FILE = Path(__file__).parent.parent / "scratch_arxiv_ids.txt"
DEST_DIR = Path(__file__).parent.parent / "raw" / "distillation"
DEST_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

def load_ids():
    with open(ARXIV_IDS_FILE) as f:
        return [line.strip() for line in f if line.strip()]

def fetch_pdf(arxiv_id):
    url = f"https://arxiv.org/pdf/{arxiv_id}"
    dest = DEST_DIR / f"{arxiv_id}.pdf"
    r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
    if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("application/pdf"):
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return True
    return False

def fetch_abstract(arxiv_id):
    url = f"https://arxiv.org/abs/{arxiv_id}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        return False
    html = r.text
    title_m = re.search(r'<h1 class="title mathjax">(?:<span[^>]*>.*?</span>)?\s*(.*?)</h1>', html, re.S)
    authors_m = re.search(r'<div class="authors">(.*?)</div>', html, re.S)
    abstract_m = re.search(r'<blockquote class="abstract mathjax">(?:<span[^>]*>.*?</span>)?\s*(.*?)</blockquote>', html, re.S)

    def clean(s):
        return re.sub(r'<[^>]+>', '', s or "").strip()

    title = clean(title_m.group(1)) if title_m else arxiv_id
    authors = clean(authors_m.group(1)) if authors_m else "Unknown"
    abstract = clean(abstract_m.group(1)) if abstract_m else "No abstract found."

    dest = DEST_DIR / f"{arxiv_id}_abstract.md"
    with open(dest, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n**arXiv:** {arxiv_id}\n**Authors:** {authors}\n**Source:** {url}\n\n## Abstract\n\n{abstract}\n")
    return True

def main():
    ids = load_ids()
    print(f"Found {len(ids)} arXiv IDs to fetch.")
    full_text, abstract_only, failed = 0, 0, 0

    for i, arxiv_id in enumerate(ids, 1):
        existing_pdf = DEST_DIR / f"{arxiv_id}.pdf"
        existing_abs = DEST_DIR / f"{arxiv_id}_abstract.md"
        if existing_pdf.exists() or existing_abs.exists():
            print(f"[{i}/{len(ids)}] {arxiv_id}: already present, skipping")
            continue

        print(f"[{i}/{len(ids)}] {arxiv_id}: fetching PDF...")
        try:
            if fetch_pdf(arxiv_id):
                full_text += 1
                print(f"  -> full text saved")
            else:
                print(f"  -> PDF unavailable, falling back to abstract")
                if fetch_abstract(arxiv_id):
                    abstract_only += 1
                    print(f"  -> abstract saved")
                else:
                    failed += 1
                    print(f"  -> FAILED")
        except Exception as e:
            failed += 1
            print(f"  -> ERROR: {e}")

        time.sleep(1.2)  # be polite to arXiv

    print(f"\nDone. Full text: {full_text}, Abstract only: {abstract_only}, Failed: {failed}")

if __name__ == "__main__":
    main()
