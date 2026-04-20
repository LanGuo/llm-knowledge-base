import os
import re
from pathlib import Path
from typing import List, Set
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from models import get_model
import yaml

class HealthReport(BaseModel):
    broken_links: List[str] = Field(description="Links to articles that do not exist.")
    orphaned_articles: List[str] = Field(description="Articles with no incoming or outgoing links.")
    knowledge_gaps: List[str] = Field(description="Concepts mentioned but not yet defined as articles.")
    suggestions: List[str] = Field(description="LLM-generated suggestions for new research topics.")

def load_template(filename: str) -> str:
    path = Path("templates") / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""

# Load Model and Instructions
model = get_model()
instructions = load_template("health_instructions.txt")

health_agent = Agent(
    model,
    output_type=HealthReport,
    instructions=instructions
)

class WikiHealthChecker:
    def __init__(self, wiki_dir: str = "wiki"):
        self.wiki_dir = Path(wiki_dir)

    def _get_all_links(self, content: str) -> Set[str]:
        """Extracts Obsidian wikilinks like [[Concept]]."""
        return set(re.findall(r"\[\[(.*?)\]\]", content))

    async def run_check(self) -> HealthReport:
        if not self.wiki_dir.exists():
            return HealthReport(broken_links=[], orphaned_articles=[], knowledge_gaps=[], suggestions=["Wiki directory not found."])

        all_files = list(self.wiki_dir.glob("**/*.md"))
        file_names = {f.stem for f in all_files}
        
        all_links = set()
        file_to_links = {}
        
        for file in all_files:
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()
                links = self._get_all_links(content)
                file_to_links[file.stem] = links
                all_links.update(links)

        broken_links = [link for link in all_links if link not in file_names]
        
        # Simple Orphan detection
        linked_to = set()
        for links in file_to_links.values():
            linked_to.update(links)
        
        orphans = [name for name in file_names if name not in linked_to and not file_to_links[name]]

        # Prepare context for LLM
        wiki_summary = f"Existing Articles: {', '.join(file_names)}\n"
        wiki_summary += f"Missing Concepts: {', '.join(broken_links)}\n"
        
        prompt = f"Wiki State Analysis:\n{wiki_summary}\nPlease generate a health report."
        result = await health_agent.run(prompt)
        
        # Enrich the LLM report with our local findings
        report = result.output
        report.broken_links = broken_links
        report.orphaned_articles = orphans
        
        return report

    def print_report(self, report: HealthReport):
        print("\n=== 🏥 Wiki Health Report ===")
        print(f"\n❌ Broken Links ({len(report.broken_links)}):")
        for link in report.broken_links: print(f"  - {link}")
        
        print(f"\n👻 Orphaned Articles ({len(report.orphaned_articles)}):")
        for orphan in report.orphaned_articles: print(f"  - {orphan}")
        
        print(f"\n🕳️ Knowledge Gaps:")
        for gap in report.knowledge_gaps: print(f"  - {gap}")
        
        print(f"\n💡 AI Suggestions:")
        for suggestion in report.suggestions: print(f"  - {suggestion}")
        print("\n============================\n")
