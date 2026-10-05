"""Shared helpers: cached downloads and text normalization. Standard library only."""
import hashlib
import html
import os
import re
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, "sources", "cache")
MANUAL = os.path.join(ROOT, "sources", "manual")

# SEC requires a descriptive User-Agent with contact details:
#   export SEC_USER_AGENT="Your Name your@email.com"
UA = os.environ.get("SEC_USER_AGENT", "")


def url_key(url):
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def fetch(url, offline=False):
    """Return page bytes. Order: manual copy, cache, download (saved to cache)."""
    key = url_key(url)
    for folder in (MANUAL, CACHE):
        for ext in (".html", ".htm", ".txt", ".csv"):
            p = os.path.join(folder, key + ext)
            if os.path.exists(p):
                return open(p, "rb").read()
    if offline:
        raise FileNotFoundError(f"not cached: {url} (key {key})")
    if "sec.gov" in url and not UA:
        raise RuntimeError("set SEC_USER_AGENT='Name email' before downloading from sec.gov")
    req = urllib.request.Request(url, headers={"User-Agent": UA or "Mozilla/5.0 (research replication)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, key + ".html"), "wb") as f:
        f.write(data)
    if "sec.gov" in url:
        time.sleep(0.2)  # SEC fair-access limit is 10 requests per second
    return data


QUOTES = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u00a0": " ", "\u2013": "-", "\u2014": "-"}


def normalize(text):
    """HTML to plain text: unescape, drop tags, straighten quotes, collapse whitespace."""
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    for a, b in QUOTES.items():
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip()


# ---------- SEC EDGAR helpers ----------
import json


def sec_json(url, offline=False):
    return json.loads(fetch(url, offline).decode("utf-8"))


def ticker_to_cik(ticker, offline=False):
    data = sec_json("https://www.sec.gov/files/company_tickers.json", offline)
    for v in data.values():
        if v["ticker"].upper() == ticker.upper():
            return int(v["cik_str"])
    raise KeyError(f"ticker not found: {ticker}")


def filings(cik, forms=("8-K", "10-Q", "10-K"), start=None, end=None, offline=False):
    """Filings from the EDGAR submissions API, including older pages."""
    sub = sec_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", offline)
    pages = [sub["filings"]["recent"]]
    # "recent" holds only the newest ~1,000 filings. Companies with many Form 4s push
    # older 8-Ks into extra pages, listed in "files" with their date range.
    for f in sub["filings"].get("files", []):
        if (end and f.get("filingFrom", "") > end) or (start and f.get("filingTo", "9999") < start):
            continue
        pages.append(sec_json("https://data.sec.gov/submissions/" + f["name"], offline))
    out, seen = [], set()
    for r in pages:
        for form, date, acc, doc in zip(r["form"], r["filingDate"], r["accessionNumber"], r["primaryDocument"]):
            if acc in seen:
                continue
            if form in forms and (not start or date >= start) and (not end or date <= end):
                seen.add(acc)
                out.append({"form": form, "date": date, "acc": acc, "primary": doc})
    return out


def filing_documents(cik, acc, offline=False):
    """URLs of the .htm/.txt documents in one filing (primary document and exhibits)."""
    nodash = acc.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{nodash}/"
    idx = sec_json(base + "index.json", offline)
    keep = []
    for i in idx["directory"]["item"]:
        name = i["name"].lower()
        if not name.endswith((".htm", ".html", ".txt")) or "index" in name:
            continue
        # R1.htm, R2.htm, ...: the SEC's XBRL table views (often 100+ per 10-K/10-Q);
        # FilingSummary and full-submission .txt duplicate the other documents
        if re.fullmatch(r"r\d+\.htm", name) or name.startswith("filingsummary") or name.endswith("-index.htm") \
                or re.fullmatch(r"\d{10}-\d{2}-\d{6}\.txt", name):
            continue
        keep.append(base + i["name"])
    return keep


def sentences(text):
    """Split normalized text into sentences (simple rule; good enough for filings)."""
    return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z(])", text) if s.strip()]

