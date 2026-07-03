# Scilit Sonar

A research monitoring tool for second language acquisition, digital game-based language learning, and educational technology. Scilit Sonar queries the Semantic Scholar API across a configurable set of search terms, deduplicates results, filters by publication date, and separates papers you have already reviewed from ones you have not seen yet. The goal is simple: spend less time manually trawling databases and more time actually reading.

**[Live demo](https://scilit-sonar.streamlit.app)** — reading history does not persist between sessions in the hosted version; see the note on local installation below.

---

## What it does

Each time you run a sweep, Scilit Sonar sends your configured search terms to Semantic Scholar, merges any paper that matched multiple terms into a single result (combining the term tags), filters everything outside your chosen date window, and sorts the remaining papers newest first. Results are split into two groups: papers you have not seen before, marked with a blue dot, and papers already in your reading history.

From there you can mark individual papers as read, clear the entire queue at once, sort everything by citation count instead of date, or export the full sweep as a CSV. The CSV includes each paper's title, authors, venue, publication date, citation count, DOI link, open-access PDF link, abstract, and which search terms matched it.

The default search terms are pre-loaded for research in DGBLL and SLA, covering extramural English, COTS game engagement, vocabulary acquisition, situated learning, and self-determination theory. They are fully editable in the sidebar.

---

## Key concepts

**Semantic Scholar**
Scilit Sonar uses the Semantic Scholar Graph API, which is free and does not require registration for basic use. Semantic Scholar indexes over 200 million academic papers across disciplines and returns rich metadata including abstracts, citation counts, venue names, and open-access PDF links when available. The API is maintained by the Allen Institute for AI.

**Deduplication across search terms**
A paper on vocabulary acquisition in commercial games might match several of your search terms simultaneously. Rather than showing it multiple times, Scilit Sonar merges duplicate results by their Semantic Scholar paper ID and combines all matched terms into a single tag list. This matters in practice because broad search strategies across related terms frequently produce significant overlap.

**Reading history**
Scilit Sonar keeps a local file called `seen_papers.json` that records the ID of every paper you mark as read. On the next sweep, anything in that file is moved to a separate "already read" tab rather than surfacing again as new. This is deliberately simple: the file is human-readable, easily backed up, and completely under your control. Clearing reading history deletes the file and starts fresh.

**Rate limiting**
The Semantic Scholar API allows up to 100 requests per five-minute window without authentication. Scilit Sonar adds a short delay between successive queries and handles 429 (rate limit) responses gracefully. If you plan to run frequent sweeps across many search terms, registering for a free API key raises the limit to one request per second. See the configuration section below.

---

## Usage

**Sidebar configuration**

Set your search terms, one per line. The date range slider controls how far back to look, from 30 to 365 days. The results-per-term slider controls how many results Semantic Scholar returns for each query before deduplication and date filtering, up to a maximum of 100.

Hit **Run radar sweep** to execute. Subsequent sweeps in the same session remember your reading history from earlier in the session; history saved to disk persists across sessions when running locally.

**Tabs**

The **New papers** tab shows only papers not yet in your reading history. You can mark papers individually or clear the whole tab at once. The **All papers** tab shows everything from the sweep, sortable by date or citation count. The **Export** tab provides a full CSV download of the sweep results with status column indicating whether each paper was new or already read at sweep time.

---

## Local installation

Running locally is recommended for actual research use, since reading history persists correctly between sessions only when the app has access to a stable filesystem.

```bash
git clone https://github.com/vijithvaratharajan/scilit-sonar.git
cd scilit-sonar
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`. Reading history is saved to `seen_papers.json` in the project folder.

**Optional: API key for higher rate limits**

Register for a free key at [semanticscholar.org/product/api](https://www.semanticscholar.org/product/api), then set it as an environment variable before launching:

```bash
export S2_API_KEY=your_key_here
streamlit run app.py
```

---

## Note on the hosted demo

The live demo is fully functional for exploring the tool, running sweeps, and testing exports. The one thing it cannot do is maintain reading history between sessions, because the hosted filesystem resets when the app goes to sleep. Every new session starts with a blank slate. For a persistent workflow, local installation is the right approach.

---

## Tech

- Python 3.10+
- [Streamlit](https://streamlit.io) for the interface
- [Semantic Scholar Graph API](https://api.semanticscholar.org/graph/v1) for paper data
- requests and pandas for HTTP and data handling

## License

MIT