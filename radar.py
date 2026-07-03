"""
radar.py
API querying, deduplication, date filtering, and seen-paper persistence
for Literature Radar. No Streamlit dependency — pure logic layer.

API used: Semantic Scholar Graph API (https://api.semanticscholar.org/graph/v1)
Free to use without a key for up to 100 requests per 5 minutes.
With a free API key (https://www.semanticscholar.org/product/api) the limit
rises to 1 request per second. If you intend to run frequent sweeps, register
for a key and pass it as the S2_API_KEY environment variable.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

# ── constants ────────────────────────────────────────────────────────────────

S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

# Fields requested from Semantic Scholar on every paper
S2_FIELDS = ",".join([
    "paperId",
    "title",
    "abstract",
    "year",
    "authors",
    "externalIds",
    "publicationDate",
    "citationCount",
    "openAccessPdf",
    "publicationTypes",
    "journal",
    "venue",
])

# Local file that tracks which paper IDs the user has marked as read.
# Stored next to this script so it travels with the project folder.
SEEN_FILE = Path(__file__).parent / "seen_papers.json"

# Delay between successive API calls to be respectful of rate limits.
REQUEST_DELAY = 0.6  # seconds


# ── persistence ──────────────────────────────────────────────────────────────

def load_seen() -> set:
    """Load the set of paper IDs the user has already reviewed."""
    if not SEEN_FILE.exists():
        return set()
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("seen_ids", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen(seen_ids: set) -> None:
    """Persist the seen-paper set to disk."""
    payload = {
        "seen_ids":    list(seen_ids),
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def clear_seen() -> None:
    """Delete the seen-paper file, resetting the radar to a blank slate."""
    if SEEN_FILE.exists():
        SEEN_FILE.unlink()


# ── API layer ────────────────────────────────────────────────────────────────

def _get_headers() -> dict:
    key = os.environ.get("S2_API_KEY", "")
    if key:
        return {"x-api-key": key}
    return {}


def search_s2(query: str, limit: int = 50) -> tuple[list[dict], str | None]:
    """
    Query Semantic Scholar for papers matching `query`.

    Returns (papers, error_message). If the request succeeds, error_message
    is None. If it fails, papers is an empty list and error_message describes
    what went wrong.
    """
    params = {
        "query":  query,
        "fields": S2_FIELDS,
        "limit":  min(limit, 100),
    }
    try:
        response = requests.get(
            S2_SEARCH_URL,
            params=params,
            headers=_get_headers(),
            timeout=20,
        )
        if response.status_code == 429:
            return [], "Rate limit hit. Wait a minute and try again."
        response.raise_for_status()
        data = response.json()
        return data.get("data", []), None

    except requests.exceptions.Timeout:
        return [], "Request timed out. Check your connection and try again."
    except requests.exceptions.ConnectionError:
        return [], "Could not reach Semantic Scholar. Check your internet connection."
    except requests.exceptions.HTTPError as e:
        return [], f"HTTP error: {e}"
    except Exception as e:
        return [], f"Unexpected error: {e}"


# ── date handling ─────────────────────────────────────────────────────────────

def parse_date(paper: dict) -> datetime | None:
    """
    Extract a publication date from a paper dict. Semantic Scholar returns
    publicationDate as 'YYYY-MM-DD' when the exact date is known, or only
    year as an integer when it is not. We fall back to 1 January of the year
    so that year-only papers still survive date filtering.
    """
    pub_date = paper.get("publicationDate")
    if pub_date:
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                return datetime.strptime(pub_date, fmt)
            except ValueError:
                continue

    year = paper.get("year")
    if year:
        try:
            return datetime(int(year), 1, 1)
        except (ValueError, TypeError):
            pass

    return None


def filter_by_days(papers: list[dict], days_back: int) -> list[dict]:
    """Keep papers whose publication date falls within the last `days_back` days."""
    cutoff = datetime.now() - timedelta(days=days_back)
    return [p for p in papers if (d := parse_date(p)) and d >= cutoff]


# ── deduplication and enrichment ──────────────────────────────────────────────

def deduplicate(papers: list[dict]) -> list[dict]:
    """
    Merge papers that share the same Semantic Scholar ID. When a paper matches
    multiple search terms, the matched_terms lists are combined.
    """
    merged: dict[str, dict] = {}
    for paper in papers:
        pid = paper.get("paperId")
        if not pid:
            continue
        if pid in merged:
            existing_terms = set(merged[pid].get("matched_terms", []))
            new_terms      = set(paper.get("matched_terms", []))
            merged[pid]["matched_terms"] = sorted(existing_terms | new_terms)
        else:
            merged[pid] = paper
    return list(merged.values())


def format_authors(authors: list[dict], max_n: int = 4) -> str:
    """Format an author list to 'A, B, C et al.' style."""
    if not authors:
        return "Unknown authors"
    names = [a.get("name", "").strip() for a in authors[:max_n] if a.get("name")]
    result = ", ".join(names)
    if len(authors) > max_n:
        result += " et al."
    return result


def get_paper_url(paper: dict) -> str:
    """Return the best URL for a paper: DOI first, then Semantic Scholar page."""
    ext = paper.get("externalIds") or {}
    doi = ext.get("DOI")
    if doi:
        return f"https://doi.org/{doi}"
    pid = paper.get("paperId", "")
    return f"https://www.semanticscholar.org/paper/{pid}" if pid else ""


def get_pdf_url(paper: dict) -> str | None:
    """Return an open-access PDF URL if one is available."""
    oa = paper.get("openAccessPdf")
    if isinstance(oa, dict):
        return oa.get("url")
    return None


def get_venue(paper: dict) -> str:
    """Return the best available venue/journal name."""
    journal = paper.get("journal") or {}
    name = journal.get("name", "").strip()
    if name:
        return name
    venue = (paper.get("venue") or "").strip()
    return venue if venue else "Venue unknown"


# ── main sweep ───────────────────────────────────────────────────────────────

def sweep(
    terms: list[str],
    days_back: int,
    results_per_term: int = 50,
) -> tuple[list[dict], list[str]]:
    """
    Run a full radar sweep.

    For each search term, query Semantic Scholar, tag each result with the
    term that matched it, then deduplicate across terms and filter by date.
    Results are sorted by publication date descending (most recent first).

    Returns (papers, errors) where errors is a list of any per-term failures.
    """
    all_papers: list[dict] = []
    errors: list[str] = []

    for i, term in enumerate(terms):
        papers, err = search_s2(term, limit=results_per_term)
        if err:
            errors.append(f'"{term}": {err}')
        for p in papers:
            p["matched_terms"] = [term]
        all_papers.extend(papers)

        # Small pause between requests to stay inside the rate limit.
        if i < len(terms) - 1:
            time.sleep(REQUEST_DELAY)

    deduped  = deduplicate(all_papers)
    recent   = filter_by_days(deduped, days_back)

    # Sort by date, most recent first. Papers with only a year sort to the
    # start of that year, which puts them below papers with an exact date.
    recent.sort(
        key=lambda p: parse_date(p) or datetime.min,
        reverse=True,
    )

    return recent, errors
