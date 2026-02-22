"""
Script: research_orchestration.py
Description: Search for Multi-Agent Orchestration Patterns (Python/LLM).
"""

from duckduckgo_search import DDGS
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Orchestration_Search")

def search_patterns():
    queries = [
        "LLM multi-agent orchestration patterns python github",
        "LangChain vs AutoGen orchestration comparison",
        "MetaGPT architecture diagram explained",
        "OpenAI Swarm framework tutorial python",
        "Supervisor worker agent pattern python implementation"
    ]
    
    findings = []
    
    with DDGS() as ddgs:
        for q in queries:
            logger.info(f"🔎 Scanning: {q}")
            try:
                results = list(ddgs.text(q, max_results=2))
                for res in results:
                    findings.append({
                        "query": q,
                        "title": res.get('title'),
                        "link": res.get('href'),
                        "snippet": res.get('body')
                    })
            except Exception as e:
                logger.error(f"Search failed: {e}")

    print(json.dumps(findings, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    search_patterns()