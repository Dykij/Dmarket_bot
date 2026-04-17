"""
HLTV/Liquipedia Native Scraper (v8.0).
Bypasses the need for BeautifulSoup by using regex on simplified mobile views
or public tournament calendars.

Updates data/cs2_events.json automatically.
"""

import aiohttp
import asyncio
import re
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("EventScraper")

EVENTS_FILE = Path(__file__).parent.parent.parent / "data" / "cs2_events.json"

class EventScraper:
    # Liquipedia's tournament portal is usually easier to parse than HLTV
    SOURCE_URL = "https://liquipedia.net/counterstrike/Portal:Tournaments"
    
    def __init__(self):
        self.headers = {
            "User-Agent": "DMarketBot-Quantitative-Engine/8.0 (Native Scraper; +https://github.com/Dykij/Dmarket_bot)"
        }

    async def fetch_events(self):
        """Fetch and parse upcoming events."""
        logger.info(f"🌐 Fetching tournament data from {self.SOURCE_URL}...")
        
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(self.SOURCE_URL, timeout=15) as response:
                    if response.status != 200:
                        logger.error(f"❌ Failed to fetch events: HTTP {response.status}")
                        return []
                    
                    html = await response.text()
                    return self._parse_html(html)
        except Exception as e:
            logger.error(f"⚠️ Scraper error: {e}")
            return []

    def _parse_html(self, html: str):
        """
        Regex-based parsing of Liquipedia tournament tables.
        Looks for patterns like:
        <span class="tournaments-list-name"><a ...>Event Name</a></span>
        <span class="tournaments-list-dates">Month Day - Day, Year</span>
        """
        events = []
        
        # Pattern for Tournament Name & Link
        # <a href="/counterstrike/IEM/Krakow/2026" title="IEM Krakow 2026">IEM Krakow 2026</a>
        name_pattern = re.compile(r'title="([^"]+?Major[^"]*?|[^"]+?IEM[^"]*?|[^"]+?ESL[^"]*?|[^"]+?BLAST[^"]*?)"')
        
        # Pattern for Dates: "Jan 28 - Feb 08, 2026"
        date_pattern = re.compile(r'>([A-Z][a-z]{2}\s\d{1,2}\s-\s(?:[A-Z][a-z]{2}\s)?\d{1,2},\s202[5-7])<')

        # This is a simplified approach for v8.0 Native.
        # In a real scenario, we'd need more robust block-level parsing.
        
        names = name_pattern.findall(html)
        dates = date_pattern.findall(html)
        
        logger.info(f"🔍 Found {len(names)} potential premium events and {len(dates)} date strings.")
        
        # Map them if possible (simple heuristic for v8.0)
        # For the sake of the bot's safety, we only auto-add MAJORS.
        for i in range(min(len(names), len(dates))):
            name = names[i]
            date_str = dates[i]
            
            if "Major" in name or "Cologne" in name or "Katowice" in name:
                parsed_dates = self._convert_dates(date_str)
                if parsed_dates:
                    events.append({
                        "name": name,
                        "start": parsed_dates[0],
                        "end": parsed_dates[1],
                        "type": "major" if "Major" in name else "tier1",
                        "effect": "caution",
                        "margin_multiplier": 2.0 if "Major" in name else 1.5,
                        "notes": f"Auto-detected {name} via Native Scraper."
                    })
        
        return events

    def _convert_dates(self, date_str: str):
        """Converts 'Jan 28 - Feb 08, 2026' to ('2026-01-28', '2026-02-08')."""
        try:
            # Simplify: Extract the year first
            year_match = re.search(r'202\d', date_str)
            if not year_match: return None
            year = year_match.group()
            
            # Split the range
            parts = date_str.replace(",", "").split(" - ")
            if len(parts) != 2: return None
            
            start_raw = f"{parts[0]} {year}"
            # End might be "Feb 08 2026" or just "08 2026"
            end_raw = parts[1]
            if len(end_raw.split()) == 1: # Just the day
                month = start_raw.split()[0]
                end_raw = f"{month} {end_raw}"
            else:
                end_raw = f"{end_raw}"

            start_dt = datetime.strptime(start_raw, "%b %d %Y")
            end_dt = datetime.strptime(end_raw, "%b %d %Y")
            
            return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")
        except:
            return None

    def update_local_calendar(self, new_events: list):
        """Merge new events into data/cs2_events.json."""
        if not new_events: return
        
        try:
            with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                current = json.load(f)
            
            existing_names = {ev["name"] for ev in current}
            added = 0
            
            for ne in new_events:
                if ne["name"] not in existing_names:
                    current.append(ne)
                    added += 1
            
            if added > 0:
                with open(EVENTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(current, f, indent=2, ensure_ascii=False)
                logger.info(f"✅ Added {added} new events to calendar.")
            else:
                logger.info("ℹ️ No new unique events found.")
                
        except Exception as e:
            logger.error(f"❌ Failed to update calendar file: {e}")

async def main():
    scraper = EventScraper()
    events = await scraper.fetch_events()
    scraper.update_local_calendar(events)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
