import asyncio
import argparse
import yaml
import os
import re
import json
import shutil
from pathlib import Path
from dotenv import load_dotenv
from processor import DocumentProcessor
from agent import KnowledgeAgent
from tools.health_checker import WikiHealthChecker
from tools.search_engine import SearchEngine

load_dotenv()

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

def slugify(text, wiki_dir="synthesized", max_len=50):
    """Turns a query string into a filesystem-safe filename, avoiding
    collisions with existing files by appending a numeric suffix."""
    slug = re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')[:max_len]
    slug = slug or "query"
    path = Path(wiki_dir)
    candidate = slug
    i = 2
    while (path / f"{candidate}.md").exists():
        candidate = f"{slug}_{i}"
        i += 1
    return candidate

def get_model_suffix(config):
    llm = config.get("llm", {})
    provider = llm.get("provider", "gemini")
    model = llm.get("model", "flash").replace(":", "_").replace(".", "_")
    return f"{provider}_{model}"

def get_state_file(config):
    return f".lkb_state_{get_model_suffix(config)}.json"

def load_state(config):
    state_file = get_state_file(config)
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_state(processed_files, config):
    state_file = get_state_file(config)
    with open(state_file, "w") as f:
        json.dump(list(processed_files), f)

async def ingest_file(file_path, config, topic="default"):
    processor = DocumentProcessor(attachments_dir=config.get("attachments_dir", "attachments"))
    wiki_root = Path(config.get("wiki_dir", "wiki"))
    model_suffix = get_model_suffix(config)
    topic_dir = wiki_root / model_suffix / topic.lower().replace(" ", "_")
    agent = KnowledgeAgent(wiki_dir=str(topic_dir))

    print(f"📄 Processing [{topic}] with [{model_suffix}]: {file_path}")
    # PyMuPDF/pdftext aren't safe for concurrent multi-threaded use, so this
    # stays synchronous (blocking the event loop briefly); the slow part —
    # the LLM compile call — still runs concurrently via asyncio.to_thread.
    text, metadata, attachments = processor.process(file_path)
    
    if not text or "Error extracting PDF" in text or len(text) < 50:
        print(f"⚠️ Skipping {file_path}: Insufficient or invalid content.")
        return False

    try:
        article = await agent.compile(text, metadata, attachments=attachments)
        
        if "Extraction Error" in article.title or "Missing Content" in article.title:
            print(f"⚠️ LLM flagged extraction error for {file_path}. Skipping save.")
            return False
            
        file_stem = Path(file_path).stem
        agent.save_to_wiki(article, filename=file_stem)
        return True
    except Exception as e:
        print(f"❌ LLM Compilation failed for {file_path}: {e}")
        return False

async def sync_sources(config):
    """Processes new files across all sources once, with bounded concurrency."""
    model_suffix = get_model_suffix(config)
    print(f"🔄 Starting LKB Sync for model: {model_suffix}")

    sources = config.get("sources", [])
    processed_files = load_state(config)
    new_count = 0
    state_lock = asyncio.Lock()
    parallelism = config.get("llm", {}).get("sync_parallelism", 4)
    semaphore = asyncio.Semaphore(parallelism)

    pending = []
    for source in sources:
        path = Path(source['path'])
        topic = source.get('name', 'default')

        if not path.exists():
            print(f"⚠️ Source path does not exist: {path}")
            continue

        for file in path.glob("**/*"):
            if file.is_file() and str(file) not in processed_files:
                if file.suffix.lower() in ['.pdf', '.md', '.txt', '.html']:
                    pending.append((file, topic))

    async def process_one(file, topic):
        nonlocal new_count
        async with semaphore:
            success = await ingest_file(str(file), config, topic=topic)
        if success:
            async with state_lock:
                processed_files.add(str(file))
                new_count += 1
                # ATOMIC SAVE: Save state after EVERY successful file
                save_state(processed_files, config)

    await asyncio.gather(*(process_one(file, topic) for file, topic in pending))

    print(f"✅ Sync complete. {new_count} new files processed for {model_suffix}.")

def clean_wiki(config):
    """Removes junk files from the current model's wiki directory."""
    wiki_root = Path(config.get("wiki_dir", "wiki"))
    model_suffix = get_model_suffix(config)
    target_dir = wiki_root / model_suffix
    
    junk_patterns = ["PDF_Extraction_Error", "Missing_Content", "Error-", "Untitled", "Content_Extraction_Failure"]
    removed = 0
    
    print(f"🧹 Cleaning current model wiki at {target_dir}...")
    for md_file in target_dir.glob("**/*.md"):
        if any(pattern.lower() in md_file.name.lower() for pattern in junk_patterns):
            md_file.unlink()
            removed += 1
            continue
        try:
            if md_file.stat().st_size < 200:
                md_file.unlink()
                removed += 1
        except FileNotFoundError:
            continue
            
    print(f"✨ Removed {removed} junk articles from {model_suffix} wiki.")

async def watch_sources(config):
    print("🚀 LKB Watcher Started (Press Ctrl+C to stop)...")
    interval = config.get("sync_interval_minutes", 5) * 60
    while True:
        await sync_sources(config)
        print(f"💤 Sleeping for {interval/60} minutes...")
        await asyncio.sleep(interval)

def main():
    parser = argparse.ArgumentParser(description="LLM Knowledge Base (LKB) CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a file into the knowledge base")
    ingest_parser.add_argument("path", help="Path to the file to ingest")
    ingest_parser.add_argument("--topic", default="default", help="Topic/Category for this file")

    # Watch command
    watch_parser = subparsers.add_parser("watch", help="Watch configured directories periodically")

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Run a one-time sync of all sources")

    # Clean command
    clean_parser = subparsers.add_parser("clean", help="Remove junk/error articles from the current model wiki")

    # Resync command
    resync_parser = subparsers.add_parser("resync", help="Clear state and re-process all sources for CURRENT model")

    # Health command
    health_parser = subparsers.add_parser("health", help="Run a wiki health check")

    # Search command
    search_parser = subparsers.add_parser("query", help="Query the wiki search index")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--save", action="store_true", help="Save the synthesized answer to synthesized/")

    # Index command
    index_parser = subparsers.add_parser("index", help="Index the wiki for search")

    args = parser.parse_args()
    config = load_config()

    if args.command == "ingest":
        asyncio.run(ingest_file(args.path, config, topic=args.topic))
    elif args.command == "sync":
        asyncio.run(sync_sources(config))
    elif args.command == "resync":
        state_file = get_state_file(config)
        if os.path.exists(state_file):
            os.remove(state_file)
        asyncio.run(sync_sources(config))
    elif args.command == "clean":
        clean_wiki(config)
    elif args.command == "watch":
        try:
            asyncio.run(watch_sources(config))
        except KeyboardInterrupt:
            print("\n👋 LKB Watcher stopped.")
    elif args.command == "health":
        model_wiki = Path(config.get("wiki_dir", "wiki")) / get_model_suffix(config)
        checker = WikiHealthChecker(wiki_dir=str(model_wiki))
        report = asyncio.run(checker.run_check())
        checker.print_report(report)
    elif args.command == "index":
        model_wiki = Path(config.get("wiki_dir", "wiki")) / get_model_suffix(config)
        engine = SearchEngine(db_path=f".lkb_db_{get_model_suffix(config)}")
        engine.index_wiki(wiki_dir=str(model_wiki))
    elif args.command == "query":
        engine = SearchEngine(db_path=f".lkb_db_{get_model_suffix(config)}")
        results = engine.search(args.query)
        if not results:
            print(f"❌ No matches found for '{args.query}'")
        else:
            agent = KnowledgeAgent(wiki_dir="synthesized")
            article = asyncio.run(agent.synthesize(args.query, results))
            print(f"\n💡 {article.title}\n{'=' * 60}\n")
            print(article.summary)
            print(f"\n{article.content}\n")
            print("📚 Sources:")
            for res in results:
                print(f"  - {res['title']} ({res['path']})")
            if args.save:
                filename = slugify(args.query)
                agent.save_to_wiki(article, filename=filename)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
