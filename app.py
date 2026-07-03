"""
app.py — Literature Radar
A research monitoring tool for second language acquisition and
digital game-based language learning.

Queries Semantic Scholar for recent publications matching your
configured search terms, tracks which papers you have already
reviewed, and surfaces only new work each time you open the app.
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from radar import (
    clear_seen,
    format_authors,
    get_paper_url,
    get_pdf_url,
    get_venue,
    load_seen,
    parse_date,
    save_seen,
    sweep,
)

# ── default search terms pre-loaded for Vijith's research stream ─────────────

DEFAULT_TERMS = """\
digital game-based language learning
commercial video games second language acquisition
extramural English vocabulary
narrative games EFL learners
COTS games language learning
self-determination theory second language
situated learning game-based
vocabulary acquisition informal learning
out-of-school digital game English\
"""


# ── session state initialisation ─────────────────────────────────────────────

def init_state() -> None:
    if "seen_ids" not in st.session_state:
        st.session_state.seen_ids = load_seen()
    if "papers" not in st.session_state:
        st.session_state.papers = []
    if "sweep_errors" not in st.session_state:
        st.session_state.sweep_errors = []
    if "last_sweep" not in st.session_state:
        st.session_state.last_sweep = None
    if "sweep_done" not in st.session_state:
        st.session_state.sweep_done = False


# ── helpers ───────────────────────────────────────────────────────────────────

def mark_seen(paper_id: str) -> None:
    st.session_state.seen_ids.add(paper_id)
    save_seen(st.session_state.seen_ids)


def mark_all_seen(papers: list[dict]) -> None:
    for p in papers:
        pid = p.get("paperId")
        if pid:
            st.session_state.seen_ids.add(pid)
    save_seen(st.session_state.seen_ids)


def is_new(paper: dict) -> bool:
    return paper.get("paperId") not in st.session_state.seen_ids


def format_date(paper: dict) -> str:
    pub_date = paper.get("publicationDate")
    if pub_date:
        try:
            d = datetime.strptime(pub_date, "%Y-%m-%d")
            return d.strftime("%-d %b %Y")
        except (ValueError, AttributeError):
            pass
    year = paper.get("year")
    return str(year) if year else "Date unknown"


# ── paper card ────────────────────────────────────────────────────────────────

def render_paper(paper: dict, show_mark_btn: bool = True) -> None:
    pid      = paper.get("paperId", "")
    title    = paper.get("title") or "Untitled"
    authors  = format_authors(paper.get("authors") or [])
    venue    = get_venue(paper)
    date_str = format_date(paper)
    citations = paper.get("citationCount") or 0
    abstract = (paper.get("abstract") or "").strip()
    url      = get_paper_url(paper)
    pdf_url  = get_pdf_url(paper)
    terms    = paper.get("matched_terms") or []
    new      = is_new(paper)

    with st.container(border=True):
        # title row
        title_display = f"[{title}]({url})" if url else title
        new_badge = " 🔵" if new else ""
        st.markdown(f"**{title_display}**{new_badge}")

        # meta row
        meta_parts = [authors, venue, date_str]
        st.caption("  ·  ".join(p for p in meta_parts if p))

        # citation count + matched terms + PDF link
        col_left, col_right = st.columns([3, 1])

        with col_left:
            if terms:
                term_pills = "  ".join(
                    f"`{t}`" for t in terms
                )
                st.markdown(term_pills)

        with col_right:
            st.caption(f"Cited {citations:,}×")
            if pdf_url:
                st.markdown(f"[Open PDF]({pdf_url})")

        # abstract
        if abstract:
            preview = abstract[:280]
            if len(abstract) > 280:
                preview += "…"
            with st.expander("Abstract"):
                st.write(abstract)
        else:
            st.caption("_Abstract not available_")

        # action buttons
        if show_mark_btn and new:
            if st.button("Mark as read", key=f"mark_{pid}"):
                mark_seen(pid)
                st.rerun()


# ── paper list views ─────────────────────────────────────────────────────────

def render_paper_list(papers: list[dict], show_mark_btn: bool = True) -> None:
    if not papers:
        st.info("No papers to show here.")
        return
    for paper in papers:
        render_paper(paper, show_mark_btn=show_mark_btn)


# ── export helpers ────────────────────────────────────────────────────────────

def papers_to_dataframe(papers: list[dict]) -> pd.DataFrame:
    rows = []
    for p in papers:
        rows.append({
            "Title":        p.get("title", ""),
            "Authors":      format_authors(p.get("authors") or []),
            "Year":         p.get("year", ""),
            "Date":         p.get("publicationDate", ""),
            "Venue":        get_venue(p),
            "Citations":    p.get("citationCount", 0),
            "URL":          get_paper_url(p),
            "PDF":          get_pdf_url(p) or "",
            "Abstract":     (p.get("abstract") or "").strip(),
            "MatchedTerms": "; ".join(p.get("matched_terms") or []),
            "Status":       "read" if not is_new(p) else "new",
        })
    return pd.DataFrame(rows)


# ── main app ─────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="Literature Radar",
        page_icon="📡",
        layout="wide",
    )

    init_state()

    # ── header ──
    st.markdown("## 📡 Literature Radar")
    st.markdown(
        "<span style='font-size:14px;opacity:0.6;'>"
        "Monitoring recent publications in DGBLL, SLA, and educational technology"
        "</span>",
        unsafe_allow_html=True,
    )

    st.divider()

    # ── sidebar ──
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")

        st.markdown("**Search terms** (one per line)")
        raw_terms = st.text_area(
            "Search terms",
            value=DEFAULT_TERMS,
            height=220,
            label_visibility="collapsed",
            help="Each line is sent as a separate query to Semantic Scholar.",
        )
        terms = [t.strip() for t in raw_terms.strip().splitlines() if t.strip()]

        st.markdown("**Date range**")
        days_back = st.select_slider(
            "Show papers from the last",
            options=[30, 60, 90, 120, 180, 365],
            value=90,
            format_func=lambda d: f"{d} days",
            label_visibility="collapsed",
        )

        st.markdown("**Results per term**")
        per_term = st.slider(
            "Results per term",
            min_value=10,
            max_value=100,
            value=50,
            step=10,
            label_visibility="collapsed",
            help=(
                "How many results to fetch from Semantic Scholar per search "
                "term before deduplication and date filtering. Higher values "
                "are more complete but slower."
            ),
        )

        st.divider()

        run_sweep = st.button(
            "▶  Run radar sweep",
            use_container_width=True,
            type="primary",
        )

        if st.session_state.last_sweep:
            st.caption(f"Last sweep: {st.session_state.last_sweep}")

        st.divider()

        st.markdown("**Reading history**")
        seen_count = len(st.session_state.seen_ids)
        st.caption(f"{seen_count} papers marked as read")

        if st.button("Clear reading history", use_container_width=True):
            clear_seen()
            st.session_state.seen_ids = set()
            st.success("Reading history cleared.")
            st.rerun()

        st.divider()

        st.markdown(
            "<div style='font-size:12px;opacity:0.55;line-height:1.6;'>"
            "Data from <a href='https://www.semanticscholar.org' target='_blank'>"
            "Semantic Scholar</a>. "
            "The 🔵 badge marks papers not yet in your reading history. "
            "Seen papers persist between sessions in <code>seen_papers.json</code> "
            "in the app folder. "
            "For higher API rate limits, set the <code>S2_API_KEY</code> "
            "environment variable with a free key from "
            "<a href='https://www.semanticscholar.org/product/api' target='_blank'>"
            "semanticscholar.org</a>."
            "</div>",
            unsafe_allow_html=True,
        )

    # ── sweep execution ──
    if run_sweep:
        if not terms:
            st.warning("Add at least one search term in the sidebar.")
        else:
            with st.spinner(
                f"Querying Semantic Scholar across {len(terms)} search "
                f"terms for the last {days_back} days…"
            ):
                papers, errors = sweep(terms, days_back, per_term)

            st.session_state.papers      = papers
            st.session_state.sweep_errors = errors
            st.session_state.last_sweep  = datetime.now().strftime(
                "%-d %b %Y at %H:%M"
            )
            st.session_state.sweep_done  = True

    # ── results ──
    if not st.session_state.sweep_done:
        st.markdown(
            "Configure your search terms and date range in the sidebar, "
            "then click **Run radar sweep** to fetch recent papers."
        )
        st.markdown(
            "The default terms are pre-loaded for research in digital "
            "game-based language learning and second language acquisition. "
            "Edit them to match your current focus."
        )
        return

    papers = st.session_state.papers

    # surface any API errors that occurred
    if st.session_state.sweep_errors:
        with st.expander(
            f"⚠️  {len(st.session_state.sweep_errors)} query error(s) — click to expand"
        ):
            for err in st.session_state.sweep_errors:
                st.warning(err)

    if not papers:
        st.warning(
            f"No papers found in the last {days_back} days across "
            f"{len(terms)} search terms. Try widening the date range "
            f"or broadening your search terms."
        )
        return

    new_papers  = [p for p in papers if is_new(p)]
    seen_papers = [p for p in papers if not is_new(p)]

    # summary row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total papers",  len(papers))
    col2.metric("New (unread)",  len(new_papers))
    col3.metric("Already read",  len(seen_papers))
    col4.metric("Search terms",  len(terms))

    st.divider()

    # ── tabs ──
    tab_new, tab_all, tab_export = st.tabs(
        [f"New papers ({len(new_papers)})",
         f"All papers ({len(papers)})",
         "Export"]
    )

    with tab_new:
        if not new_papers:
            st.success(
                "You are up to date. All papers from this sweep are "
                "already in your reading history."
            )
        else:
            col_hdr, col_btn = st.columns([4, 1])
            with col_btn:
                if st.button("Mark all as read", key="mark_all"):
                    mark_all_seen(new_papers)
                    st.rerun()
            render_paper_list(new_papers, show_mark_btn=True)

    with tab_all:
        sort_by = st.radio(
            "Sort by",
            ["Date (newest first)", "Citations (highest first)"],
            horizontal=True,
        )
        if sort_by == "Citations (highest first)":
            sorted_papers = sorted(
                papers,
                key=lambda p: p.get("citationCount") or 0,
                reverse=True,
            )
        else:
            sorted_papers = papers  # already sorted by date from sweep()

        render_paper_list(sorted_papers, show_mark_btn=True)

    with tab_export:
        st.markdown(
            "Download the full results of this sweep as a CSV file. "
            "The Status column records whether each paper was new or "
            "already in your reading history at the time of the sweep."
        )
        df = papers_to_dataframe(papers)
        st.dataframe(df, use_container_width=True, hide_index=True)

        date_slug = datetime.now().strftime("%Y-%m-%d")
        st.download_button(
            "⬇  Download CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=f"literature_radar_{date_slug}.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
