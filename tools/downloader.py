import re
import os
import requests
from pathlib import Path

# Paths
md_file = "/Users/languo/src/personal_kb/raw/benchmark_research.md"
dest_dir = "/Users/languo/src/agentic_memory_eval/"
os.makedirs(dest_dir, exist_ok=True)

# Read the markdown file
with open(md_file, "r") as f:
    content = f.read()

# Extract all URLs
urls = re.findall(r'https?://[^\s\)\>\]]+', content)
urls = list(set(urls)) # Deduplicate

print(f"Found {len(urls)} unique URLs. Starting downloads...")

for url in urls:
    # Handle arXiv abs to pdf conversion
    download_url = url
    filename = url.split("/")[-1]
    
    if "arxiv.org/abs/" in url:
        download_url = url.replace("/abs/", "/pdf/")
        filename = url.split("/")[-1] + ".pdf"
    elif "openreview.net/forum?id=" in url:
        download_url = url.replace("/forum?id=", "/pdf?id=")
        filename = url.split("id=")[-1] + ".pdf"
    elif "arxiv.org/html/" in url:
        # Some are HTML versions, keep as HTML
        filename = url.split("/")[-1] + ".html"
    elif not filename or "." not in filename:
        filename = re.sub(r'\W+', '_', url.replace("https://", "")) + ".html"

    # Add .html if no extension
    if not any(filename.lower().endswith(ext) for ext in [".pdf", ".html", ".md", ".txt", ".png", ".jpg"]):
        filename += ".html"
    
    dest_path = os.path.join(dest_dir, filename)
    
    if os.path.exists(dest_path):
        # Skip already downloaded
        continue

    print(f"Downloading: {download_url} -> {filename}")
    try:
        response = requests.get(download_url, timeout=10, stream=True)
        if response.status_code == 200:
            with open(dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        else:
            print(f"  Failed (Status {response.status_code})")
    except Exception as e:
        print(f"  Error: {e}")

print("\nAll reachable references have been downloaded.")
