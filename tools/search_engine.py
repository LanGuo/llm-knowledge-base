import lancedb
import pandas as pd
import pyarrow as pa
import yaml
import ollama
from pathlib import Path
import os

# Max characters of an article's content fed into the embedding model.
# nomic-embed-text has a 2048-token context window; at roughly 3-4 chars/token
# (less for text with LaTeX/code, which many papers here contain) 8000 chars
# was found to overflow it in practice, so this is kept conservative. Note
# this is a known limitation: articles are NOT chunked, just truncated —
# anything past this length isn't reflected in the vector. The full,
# untruncated text is still stored in the "content" field for display purposes.
MAX_EMBED_CHARS = 4000


class SearchEngine:
    def __init__(self, db_path: str = ".lkb_db"):
        self.db_path = Path(db_path)
        # Ensure the directory exists
        os.makedirs(self.db_path, exist_ok=True)
        self.db = lancedb.connect(self.db_path)
        self.table_name = "wiki_articles"

        # Load embedding config the same way models.py::get_model() loads llm config.
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
        embedding_config = config.get("embedding", {})
        self.embed_model = embedding_config.get("model", "nomic-embed-text")

    def _embed(self, text: str) -> list[float]:
        """Embeds text via the local Ollama embedding model.

        The input is truncated to MAX_EMBED_CHARS to stay within the embedding
        model's context window; callers that need the full text for display
        should keep it separately (this only affects the vector, not storage).
        """
        truncated = text[:MAX_EMBED_CHARS]
        response = ollama.embeddings(model=self.embed_model, prompt=truncated)
        return response["embedding"]

    def index_wiki(self, wiki_dir: str = "wiki"):
        """Indexes all Markdown files in the wiki directory recursively, embedding
        each article's content with the local Ollama model for semantic vector search."""
        wiki_path = Path(wiki_dir)
        data = []
        dim = None

        if not wiki_path.exists():
            print(f"⚠️ Wiki directory {wiki_dir} does not exist.")
            return

        print(f"🔍 Indexing (and embedding) articles in {wiki_path}...")
        # Use rglob for recursive search
        for file in wiki_path.rglob("*.md"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()

                try:
                    vector = self._embed(content)
                except Exception as e:
                    print(f"⚠️ Failed to embed {file}: {e}")
                    continue

                if dim is None:
                    dim = len(vector)

                data.append({
                    "title": file.stem,
                    "content": content,
                    "path": str(file),
                    "vector": vector
                })
            except Exception as e:
                print(f"⚠️ Failed to index {file}: {e}")

        if not data:
            print(f"⚠️ No articles found in {wiki_path} to index.")
            return

        # Build an explicit schema so the vector column is a proper fixed-size
        # float32 list, as required for LanceDB's native vector search.
        schema = pa.schema([
            pa.field("title", pa.string()),
            pa.field("content", pa.string()),
            pa.field("path", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), dim)),
        ])

        table_data = pa.table({
            "title": [d["title"] for d in data],
            "content": [d["content"] for d in data],
            "path": [d["path"] for d in data],
            "vector": pa.array([d["vector"] for d in data], type=pa.list_(pa.float32(), dim)),
        }, schema=schema)

        # In this simple version, we drop and recreate the table for simplicity
        if self.table_name in self.db.table_names():
            self.db.drop_table(self.table_name)

        self.db.create_table(self.table_name, data=table_data, schema=schema)

        print(f"✅ Indexed {len(data)} articles in LanceDB.")

    def search(self, query: str, limit: int = 5):
        """Performs semantic vector search: embeds the query and finds the
        nearest articles by vector similarity."""
        if self.table_name not in self.db.table_names():
            print("❌ Search index not found. Run 'lkb index' first.")
            return []

        table = self.db.open_table(self.table_name)
        query_vector = self._embed(query)
        results = table.search(query_vector).limit(limit).to_pandas()
        return results.to_dict('records')
