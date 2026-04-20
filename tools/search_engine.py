import lancedb
import pandas as pd
from pathlib import Path
import os

class SearchEngine:
    def __init__(self, db_path: str = ".lkb_db"):
        self.db_path = Path(db_path)
        # Ensure the directory exists
        os.makedirs(self.db_path, exist_ok=True)
        self.db = lancedb.connect(self.db_path)
        self.table_name = "wiki_articles"

    def index_wiki(self, wiki_dir: str = "wiki"):
        """Indexes all Markdown files in the wiki directory recursively."""
        wiki_path = Path(wiki_dir)
        data = []
        
        if not wiki_path.exists():
            print(f"⚠️ Wiki directory {wiki_dir} does not exist.")
            return

        print(f"🔍 Indexing articles in {wiki_path}...")
        # Use rglob for recursive search
        for file in wiki_path.rglob("*.md"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()
                    data.append({
                        "title": file.stem,
                        "content": content,
                        "path": str(file)
                    })
            except Exception as e:
                print(f"⚠️ Failed to index {file}: {e}")
        
        if not data:
            print(f"⚠️ No articles found in {wiki_path} to index.")
            return

        df = pd.DataFrame(data)
        
        # In this simple version, we drop and recreate the table for simplicity
        if self.table_name in self.db.table_names():
            self.db.drop_table(self.table_name)
        
        self.db.create_table(self.table_name, data=df)
        
        print(f"✅ Indexed {len(data)} articles in LanceDB.")

    def search(self, query: str, limit: int = 5):
        """Performs a basic keyword-based filter search."""
        if self.table_name not in self.db.table_names():
            print("❌ Search index not found. Run 'lkb index' first.")
            return []

        table = self.db.open_table(self.table_name)
        results = table.to_pandas()
        # Simple case-insensitive match for the MVP
        matches = results[results['content'].str.contains(query, case=False, na=False)]
        return matches.head(limit).to_dict('records')
