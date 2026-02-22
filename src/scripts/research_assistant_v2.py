"""
Script: research_assistant_v2.py
Description: Advanced Research extraction using DuckDuckGo.
Target: Specific academic papers validating 'Mean Reversion' in CS2/Steam markets.
"""

from duckduckgo_search import DDGS
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Academia_Probe")

def get_verified_proof():
    # Specific queries targeting the papers found in preliminary scan
    queries = [
        "Samuel Pettersson Price Dynamics in the Counter-Strike 2 Skin Market mean reversion",
        "M Roth Predicting price trends Steam Community Market forecasting",
        "T Glaus Seasonality of In-Game Item Returns Steam Community Market"
    ]
    
    findings = []
    
    with DDGS() as ddgs:
        for q in queries:
            logger.info(f"🔬 Deep Scanning: {q}")
            try:
                # Fetching results
                results = list(ddgs.text(q, max_results=2))
                for res in results:
                    findings.append({
                        "source": res.get('title'),
                        "url": res.get('href'),
                        "evidence": res.get('body')
                    })
            except Exception as e:
                logger.error(f"Scan error: {e}")

    # Output for Arkady
    print(json.dumps(findings, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    get_verified_proof()