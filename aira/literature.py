"""Literature helpers: DOI cleaning, duplicate keys and the Excel matrix reader.

Pure Python (no Streamlit, no database), so it can be tested on its own.
Nothing here fills in a missing field: what is not in your file stays empty.
"""

from __future__ import annotations

import io
import re
import unicodedata

READING_STATUSES = ["not_recorded", "to_read", "reading", "read"]
READING_LABELS = {
    "not_recorded": "Not recorded",
    "to_read": "To read",
    "reading": "Reading",
    "read": "Read",
}
SUMMARY_BASIS = ["full_text", "abstract"]
SUMMARY_BASIS_LABELS = {"full_text": "Full text", "abstract": "Abstract only"}
SOURCE_TYPES = ["journal_article", "book", "book_chapter", "report", "policy_document", "thesis", "other"]
SOURCE_TYPE_LABELS = {
    "journal_article": "Journal article", "book": "Book", "book_chapter": "Book chapter",
    "report": "Report", "policy_document": "Policy document", "thesis": "Thesis", "other": "Other",
}

# The columns of the "Literature review matrix" Excel export, in order.
MATRIX_HEADERS = [
    "PII", "DOI", "EID", "Publication Date", "Open Access", "Content Depth",
    "Source", "Abstract", "Methods", "Results", "Conclusions",
]

_DOI_PREFIX = re.compile(r"^(?:https?://)?(?:dx\.)?(?:www\.)?doi\.org/|^doi:\s*", re.IGNORECASE)


def normalize_doi(value) -> str | None:
    """'https://doi.org/10.1016/ABC' -> '10.1016/abc'. Returns None if empty."""
    if not value:
        return None
    text = _DOI_PREFIX.sub("", str(value).strip()).strip().rstrip(".").lower()
    return text if text.startswith("10.") else None


def normalize_title(value) -> str:
    """Lower case, accents and punctuation removed, single spaces."""
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(text.split())


def source_key(doi=None, scopus_eid=None, title=None, year=None) -> str:
    """The duplicate-check key for a source: DOI first, then Scopus EID, then title and year."""
    clean = normalize_doi(doi)
    if clean:
        return f"doi:{clean}"
    if scopus_eid and str(scopus_eid).strip():
        return f"eid:{str(scopus_eid).strip().lower()}"
    return f"title:{normalize_title(title)}|{year or ''}"


def year_from(value) -> int | None:
    match = re.match(r"^\s*(\d{4})", str(value or ""))
    return int(match.group(1)) if match else None


def is_matrix_header(row) -> bool:
    cells = [str(c).strip() if c is not None else "" for c in row]
    return cells[: len(MATRIX_HEADERS)] == MATRIX_HEADERS


def read_matrix_xlsx(data: bytes, summary_source: str) -> tuple[list[dict], list[str]]:
    """Read a 'Literature review matrix' Excel export into literature_sources rows.

    Returns (rows, problems). Every value is copied as written; nothing is guessed.
    """
    try:
        import openpyxl
    except ImportError:
        return [], ["Excel files need the openpyxl package (listed in requirements.txt)."]
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # not a valid Excel file
        return [], [f"Could not open the Excel file ({type(exc).__name__})."]

    sheet = workbook.worksheets[0]
    rows = list(sheet.iter_rows(values_only=True))
    header_at = next((i for i, row in enumerate(rows[:10]) if is_matrix_header(row)), None)
    if header_at is None:
        return [], [
            "This Excel file is not in the literature review matrix format. Its first "
            "sheet needs the columns: " + ", ".join(MATRIX_HEADERS) + "."
        ]

    def text(value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    result, problems = [], []
    for number, row in enumerate(rows[header_at + 1:], start=header_at + 2):
        cells = list(row) + [None] * (len(MATRIX_HEADERS) - len(row))
        pii, doi, eid, pub, open_access, depth, title, abstract, methods, results, conclusions = cells[:11]
        if not any(text(c) for c in cells[:11]):
            continue  # empty row
        if not text(title):
            problems.append(f"Row {number}: no title in the Source column")
            continue
        depth_text = (text(depth) or "").lower()
        basis = "full_text" if depth_text == "full text" else "abstract" if depth_text == "abstract" else None
        clean_doi = normalize_doi(doi)
        year = year_from(pub)
        result.append({
            "import_key": source_key(clean_doi, text(eid), text(title), year),
            "title": text(title),
            "year": year,
            "publication_date": text(pub),
            "doi": clean_doi,
            "url": f"https://doi.org/{clean_doi}" if clean_doi else None,
            "abstract": text(abstract),
            "methodology": text(methods),
            "key_findings": text(results),
            "conclusions": text(conclusions),
            "open_access": text(open_access),
            "summary_basis": basis,
            "summary_source": summary_source,
            "pii": text(pii),
            "scopus_eid": text(eid),
            "reading_status": "not_recorded",
        })
    return result, problems
