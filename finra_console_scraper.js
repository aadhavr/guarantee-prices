// FINRA trade history: collect all pages of the request that the bond page itself makes.
//
// How to use (Chrome, on the FINRA bond page, after you accept the user agreement):
//  1. Open DevTools (Cmd+Option+I) > Network > Fetch/XHR. Tick "Keep log".
//  2. In the page, open the trade history and set the date range (e.g. 11/13/2025 to today).
//  3. Right-click the newest "CorporateAndAgencyTradeHistory..." request >
//     Copy > Copy as fetch.
//  4. Go to the Console tab. Paste THIS whole file, but first replace the line
//        const COPIED = null;
//     with
//        const COPIED = [ <paste the two arguments of the copied fetch here> ];
//     i.e. the copied text looks like  fetch("https://...", { ... });
//     take the URL string and the { ... } object and put them in the brackets:
//        const COPIED = ["https://...", { ... }];
//  5. Set DEAL_ID below, press Enter, and wait. The browser downloads
//     <DEAL_ID>_finra_raw.json when it is done. Move it to data/bond_trades/raw/.
//
// It asks for one page of 50 trades at a time, with a pause between pages,
// exactly as if you clicked "next page" in the table. It stops at the first
// page with fewer than 50 trades.

(async () => {
  const COPIED = null;          // <-- replace (step 4), OR use option B below
  const DEAL_ID = "APLD_2030";  // <-- APLD_2030 or CRWV_2030

  // Option B, if your browser has no "Copy as fetch". Click the request in the list:
  //   REQUEST_URL   : Headers tab > General > Request URL
  //   REQUEST_BODY  : Payload tab > "View source"; paste the text between the backticks
  //   EXTRA_HEADERS : Headers tab > Request Headers: copy any header whose name starts
  //                   with "x-" (for example x-xsrf-token), as "name": "value"
  const REQUEST_URL = null;
  const REQUEST_BODY = ``;
  const EXTRA_HEADERS = {};
  const PAUSE_MS = 1500;        // pause between pages
  const MAX_PAGES = 400;        // safety stop (20,000 trades)

  let url, init;
  if (COPIED) {
    [url, init] = COPIED;
  } else if (REQUEST_URL && REQUEST_BODY.trim()) {
    if (typeof EXTRA_HEADERS !== "object" || EXTRA_HEADERS === null || Array.isArray(EXTRA_HEADERS) ||
        Object.keys(EXTRA_HEADERS).some(k => /^\d+$/.test(k))) {
      console.error('EXTRA_HEADERS must be an object like { "x-name": "value" } or {} (not text in quotes, not a list).');
      return;
    }
    try { JSON.parse(REQUEST_BODY); } catch (e) {
      console.error("REQUEST_BODY is not valid JSON: copy it again from Payload > View source."); return;
    }
    url = REQUEST_URL;
    init = { method: "POST", mode: "cors", credentials: "include", body: REQUEST_BODY.trim(),
             headers: { "Content-Type": "application/json", "Accept": "application/json, text/plain, */*",
                        ...EXTRA_HEADERS } };
  } else {
    console.error("Set COPIED (step 4), or REQUEST_URL and REQUEST_BODY (option B)."); return;
  }
  const body = JSON.parse(init.body);
  const limit = body.limit || 50;

  const parse = (text) => {
    try { return JSON.parse(text); } catch (e) { return null; }
  };
  const isTrade = (x) => x && typeof x === "object" && !Array.isArray(x) &&
    Object.keys(x).some(k => /tradeExecutionDate/i.test(k));
  // the trades: the first array of trade objects anywhere in the response,
  // also inside text fields that contain JSON (some APIs nest it that way)
  const findRecords = (obj, depth = 0) => {
    if (typeof obj === "string") {
      if (depth < 4 && /^\s*[\[{]/.test(obj)) { const p = parse(obj); if (p) return findRecords(p, depth + 1); }
      return null;
    }
    if (Array.isArray(obj)) {
      if (obj.length && isTrade(obj[0])) return obj;
      for (const x of obj) { const r = findRecords(x, depth); if (r) return r; }
      return null;
    }
    if (obj && typeof obj === "object") {
      for (const v of Object.values(obj)) { const r = findRecords(v, depth); if (r) return r; }
    }
    return null;
  };

  const pages = [];
  let all = [];
  for (let page = 0; page < MAX_PAGES; page++) {
    const b = { ...body, offset: page * limit, limit };
    const resp = await fetch(url, { ...init, body: JSON.stringify(b) });
    if (!resp.ok) { console.error(`page ${page}: HTTP ${resp.status}; stopping`); break; }
    const text = await resp.text();
    const data = parse(text);
    let recs = data ? findRecords(data) : null;
    if (!recs) {
      if (page > 0) { console.log(`page ${page}: no more trades (end)`); break; }  // total was a multiple of the page size
      console.error(`page 0: no trade records found; response starts: ${text.slice(0, 300)}`); break;
    }
    pages.push({ offset: b.offset, count: recs.length });
    all = all.concat(recs);
    console.log(`page ${page}: ${recs.length} trades (total ${all.length})`);
    if (recs.length < limit) break;
    await new Promise(r => setTimeout(r, PAUSE_MS));
  }

  const out = {
    deal_id: DEAL_ID,
    collected_at: new Date().toISOString(),
    page_url: location.href,
    request_url: url,
    request_body_first_page: body,
    pages,
    records: all,
  };
  const blob = new Blob([JSON.stringify(out, null, 1)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${DEAL_ID}_finra_raw.json`;
  a.click();
  console.log(`done: ${all.length} trades in ${pages.length} pages -> ${DEAL_ID}_finra_raw.json`);
})();
