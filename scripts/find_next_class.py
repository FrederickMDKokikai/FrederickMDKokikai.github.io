#!/usr/bin/env python3
"""
Scrapes Frederick County Parks & Rec to find the next scheduled Aikido class.

Usage:
    python3 scripts/find_next_class.py
    python3 scripts/find_next_class.py --keyword "intermediate aikido"
    python3 scripts/find_next_class.py --all
"""

import argparse
import re
import sys
from datetime import date, datetime
from playwright.sync_api import sync_playwright

BASE_URL = (
    "https://anc.apm.activecommunities.com/frederickcntyparksandrec/activity/search"
    "?locale=en-US&activity_select_param=2&activity_keyword={keyword}&viewMode=list"
)

KEYWORDS = {
    "beginner":     "aikido%20for%20beginners",
    "intermediate": "intermediate%20aikido",
    "demo":         "aikido%20demo",
}

DATE_PATTERN = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2},?\s+\d{4}\b",
    re.IGNORECASE,
)


def parse_date(text: str) -> date | None:
    text = text.replace(",", "")
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def scrape(keyword_encoded: str, label: str) -> tuple[list[tuple[date, str]], bool]:
    """Returns (results, not_listed) where not_listed=True means the site said 'No results found'."""
    url = BASE_URL.format(keyword=keyword_encoded)
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30_000)

        # Wait for activity cards to appear
        try:
            page.wait_for_selector("[class*='activity']", timeout=10_000)
        except Exception:
            pass

        text = page.inner_text("body")
        html = page.content()
        browser.close()

    not_listed = "no results found" in text.lower()

    # Extract all date-like strings from the page HTML
    raw_matches = DATE_PATTERN.findall(html)
    today = date.today()

    for raw in raw_matches:
        d = parse_date(raw)
        if d and d >= today:
            results.append((d, label))

    return results, not_listed


def main():
    parser = argparse.ArgumentParser(description="Find next Aikido class date.")
    parser.add_argument(
        "--keyword",
        choices=list(KEYWORDS.keys()),
        default="beginner",
        help="Which class type to search (default: beginner)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Search all class types and show the next date for each",
    )
    args = parser.parse_args()

    today = date.today()
    print(f"Today: {today}\n")

    search_set = KEYWORDS.items() if args.all else [(args.keyword, KEYWORDS[args.keyword])]

    for label, encoded in search_set:
        print(f"Searching '{label}' classes...")
        hits, not_listed = scrape(encoded, label)
        if not_listed and not hits:
            print(f"  Not yet listed on Parks & Rec — registration not open yet.\n")
            continue
        if not hits:
            print(f"  No future dates found.\n")
            continue
        hits.sort()
        # Deduplicate
        seen: set[date] = set()
        unique = [(d, lbl) for d, lbl in hits if not (d in seen or seen.add(d))]
        next_date = unique[0][0]
        print(f"  Next class starts: {next_date.strftime('%B %-d, %Y')}")
        if len(unique) > 1:
            print(f"  Other upcoming dates: {', '.join(d.strftime('%b %-d') for d, _ in unique[1:5])}")
        print()


if __name__ == "__main__":
    main()
