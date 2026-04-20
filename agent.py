import os
import json
import yaml
import ollama
from pathlib import Path
from typing import List, Optional, Any
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from models import get_model

# Structured Output Model for the Wiki
class WikiArticle(BaseModel):
    title: str = Field(description="A concise, descriptive title for the knowledge article.")
    authors: List[str] = Field(default_factory=list, description="The primary authors.")
    affiliation: Optional[str] = Field(None, description="The university or organization.")
    date_published: Optional[str] = Field(None, description="The publication date.")
    journal_or_conference: Optional[str] = Field(None, description="Journal/Conference name.")
    summary: str = Field(description="A 2-3 sentence summary.")
    content: str = Field(description="Main body in Markdown.")
    tags: List[str] = Field(default_factory=list, description="Keywords.")
    related_concepts: List[str] = Field(default_factory=list, description="Other wiki articles to link to.")

def load_template(filename: str) -> str:
    path = Path("templates") / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""

class KnowledgeAgent:
    def __init__(self, wiki_dir: str = "wiki"):
        self.wiki_dir = Path(wiki_dir)
        self.wiki_dir.mkdir(exist_ok=True, parents=True)
        self.structure = load_template("article_structure.md")
        self.instructions = load_template("compiler_instructions.txt")
        
        # Load config to determine provider
        with open("config.yaml", "r") as f:
            self.config = yaml.safe_load(f)
        
        self.provider = self.config.get("llm", {}).get("provider", "gemini")
        self.model_name = self.config.get("llm", {}).get("model", "gemini-2.5-flash")
        
        if self.provider != "ollama":
            # Use pydantic-ai for non-Ollama models
            self.model = get_model()
            self.agent = Agent(self.model, output_type=WikiArticle, instructions=self.instructions)

    async def compile(self, raw_text: str, metadata: dict, attachments: List[str] = None) -> WikiArticle:
        """Transforms raw text into a WikiArticle, branching by provider."""
        attachment_str = ", ".join(attachments) if attachments else "None"
        prompt = f"Source Metadata: {metadata}\nAvailable Image Attachments: {attachment_str}\n\nRaw Content:\n{raw_text}"

        if self.provider == "ollama":
            return await self._compile_ollama(prompt)
        else:
            result = await self.agent.run(prompt)
            return result.output

    async def _compile_ollama(self, prompt: str) -> WikiArticle:
        """Uses native ollama library with JSON mode for robustness."""
        print(f"🤖 [Ollama] Processing with JSON Mode...")
        
        # Add JSON schema requirement to prompt
        full_prompt = f"{self.instructions}\n\nRESPONSE REQUIREMENT: Output valid JSON that matches the WikiArticle schema.\n\n{prompt}"
        
        response = ollama.chat(
            model=self.model_name,
            messages=[{'role': 'user', 'content': full_prompt}],
            format=WikiArticle.model_json_schema(), # Native Schema constraint
            options={
                'temperature': 0.1,
                'num_ctx': 65536 # Ensure long context support
            }
        )
        
        content = response['message']['content']
        data = json.loads(content)
        return WikiArticle(**data)

    def save_to_wiki(self, article: WikiArticle, filename: str):
        """Writes the WikiArticle to a Markdown file using the template."""
        if not filename.endswith(".md"):
            filename += ".md"
        file_path = self.wiki_dir / filename
        
        links = ', '.join([f"[[{concept}]]" for concept in article.related_concepts])
        
        md_content = self.structure
        md_content = md_content.replace("{{tags}}", str(article.tags))
        md_content = md_content.replace("{{source}}", article.title)
        md_content = md_content.replace("{{title}}", article.title)
        md_content = md_content.replace("{{authors}}", ", ".join(article.authors) if article.authors else "Unknown")
        md_content = md_content.replace("{{affiliation}}", article.affiliation or "N/A")
        md_content = md_content.replace("{{date_published}}", article.date_published or "Unknown")
        md_content = md_content.replace("{{journal}}", article.journal_or_conference or "N/A")
        md_content = md_content.replace("{{summary}}", article.summary)
        md_content = md_content.replace("{{content}}", article.content)
        md_content = md_content.replace("{{related_concepts}}", links)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        print(f"✅ Wiki updated: {file_path}")
        return file_path
