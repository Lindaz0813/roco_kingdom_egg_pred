"""
Scrape a single pokemon page and merge it into data/pokemon.json.

Usage:
    python3 scrape_single.py <pokemon_name>
    python3 scrape_single.py 喵喵
    python3 scrape_single.py "石肤蜥"

This script adds a long random delay before each request to avoid bot detection.
Run this manually for any pokemon that failed during the bulk scraper run.
"""

import json
import os
import random
import sys
import time

from scraper import DATA_PATH, get_known_pokemon_links, scrape_pokemon_page

LONG_DELAY_MIN = 8   # seconds — wait at least this long before fetching
LONG_DELAY_MAX = 20  # seconds — wait at most this long


def merge(existing: list, new_entry: dict) -> list:
    """Replace an existing entry by name, or append if new."""
    for i, p in enumerate(existing):
        if p["name"] == new_entry["name"]:
            existing[i] = new_entry
            return existing
    existing.append(new_entry)
    return existing


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scrape_single.py <pokemon_name>")
        print("\nKnown pokemon:")
        for entry in get_known_pokemon_links():
            print(f"  {entry['name']}")
        sys.exit(1)

    target_name = sys.argv[1].strip()

    # Find the URL for this pokemon
    links = get_known_pokemon_links()
    link = next((l for l in links if l["name"] == target_name), None)
    if link is None:
        print(f"Unknown pokemon: {target_name!r}")
        print("Run without arguments to see the full list.")
        sys.exit(1)

    url = link["url"]
    print(f"Target: {target_name}")
    print(f"URL:    {url}")

    # Human-like delay to avoid bot detection
    delay = random.uniform(LONG_DELAY_MIN, LONG_DELAY_MAX)
    print(f"Waiting {delay:.1f}s before fetching (anti-bot)…")
    time.sleep(delay)

    data = scrape_pokemon_page(url, target_name)
    if data is None:
        print(f"\n✗ Failed to scrape {target_name}. Try again later or check the URL.")
        sys.exit(1)

    print(f"\n✓ Scraped {data['name']}:")
    print(f"  Size:     {data['size_min']}~{data['size_max']} M")
    print(f"  Weight:   {data['weight_min']}~{data['weight_max']} KG")
    print(f"  Hatchable: {data['is_hatchable']}")

    # Load existing data
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = []

    existing = merge(existing, data)

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    hatchable = sum(1 for p in existing if p.get("is_hatchable", True))
    print(f"\nSaved. Total in database: {len(existing)} pokemon ({hatchable} hatchable)")


if __name__ == "__main__":
    main()
