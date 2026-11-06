#!/usr/bin/env python3
"""VIFIX P1 scope C, step 2: classify a live sweep (vifix_live_sweep.mjs output) into findings.

Run:  python3 vifix_live_report.py <sweep.json> [--md out.md] [--json out.json]

A visible string is a finding when, after removing placeholders, numbers, codes and the VF1
allowlist (vifix_common), it still has an English word (>= 3 letters) and no Vietnamese
letter, or it is Vietnamese with an English word of >= 4 letters inside (mixed). Data values
(list cells, field values, chat bodies: `data: true` from the collector) are reported apart:
they are records, not product strings. Strings that the po scan knows as an msgid of one of
our modules are tagged with that module, which points the fix at a .po edit rather than code.
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vifix_common as C  # noqa: E402

import polib  # noqa: E402
import vifix_po_scan as PS  # noqa: E402


def wrong_vietnamese(text):
    """Seed-list hits (vifix_po_scan.SUSPICIOUS) in visible Vietnamese, e.g. 'SÂN KHẤU 2 / 5'."""
    if not C.has_vietnamese(text):
        return []
    hits = []
    for rx, seed, why in PS.SUSPICIOUS_RES:
        if seed != "odoo" and rx.search(text) and not any(seed in h for h in hits):
            hits.append(seed)
    return hits

# Demo-world proper names and data-ish tokens that are not product strings.
IGNORE_RE = re.compile(
    r"^(?:QA Test|QT|VI|EN|Payobook Vietnam JSC|Payobook(?: [A-Z][a-z]+)*|PayAI|[A-Z]{1,4}\d*|"
    r"[\d\s.,:/%+\-–—₫$€()x×]+|T\d{1,2}(?:/\d{2,4})?|Q\d|v?\d+(?:\.\d+)+.*)$")


def english_in(s, min_len=3):
    return [w for w in C.latin_words(s) if len(w) >= min_len and C.classify_word(w) == "en"]


def msgid_index():
    idx = collections.defaultdict(set)
    for m in C.our_modules():
        for fn in ("vi_VN.po", m + ".pot"):
            p = os.path.join(C.REPO, m, "i18n", fn)
            if not os.path.exists(p):
                continue
            for e in polib.pofile(p, wrapwidth=0):
                if e.msgid:
                    idx[C.norm(e.msgid)].add(m)
    return idx


def source_blob():
    """Lower-cased text of every msgid and every source file of our modules (static/src js and
    xml, Python outside i18n/tests). A visible string found here is product text; one that is
    not is a record (demo names, departments, pay-run names) or built at runtime."""
    parts = []
    for m in C.our_modules():
        if m.startswith(("pb_demo", "rize_")):
            continue  # demo-world generators: what they write is records, not product text
        base = os.path.join(C.REPO, m)
        for root, dirs, files in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d not in ("tests", "__pycache__", "node_modules", "i18n", "lib"))
            for f in sorted(files):
                if f.endswith((".js", ".xml", ".py")):
                    try:
                        parts.append(open(os.path.join(root, f), encoding="utf-8", errors="replace").read())
                    except OSError:
                        pass
        for fn in ("vi_VN.po", m + ".pot"):
            p = os.path.join(base, "i18n", fn)
            if os.path.exists(p):
                parts.extend(e.msgid for e in polib.pofile(p, wrapwidth=0))
    blob = "\n".join(parts).lower()
    return re.sub(r"\s+", " ", blob)


def in_source(text, blob):
    t = re.sub(r"\s+", " ", text.strip().lower())
    if t in blob:
        return True
    # strings with numbers/names filled in at runtime: try the longest static fragment
    frags = sorted((f.strip() for f in re.split(r"[\d₫%]+|·|—|\(|\)", t)), key=len, reverse=True)
    return bool(frags and len(frags[0]) >= 12 and frags[0] in blob)


def classify(text):
    if IGNORE_RE.match(text.strip()):
        return None
    if C.has_vietnamese(text):
        en = C.english_words(text, 4)
        return ("mixed", en) if en else None
    en = english_in(text)
    if not en:
        return None
    return ("english", en)


def build(sweep):
    idx = msgid_index()
    blob = source_blob()
    rows = []
    for r in sweep["records"]:
        found, data_found, wrong = [], [], []
        for item in r.get("texts", []) + [{"t": x["t"]} for x in r.get("attrs", [])]:
            for seed in wrong_vietnamese(item["t"]):
                wrong.append({"t": item["t"], "seed": seed})
        for item in r.get("texts", []):
            c = classify(item["t"])
            if not c:
                continue
            entry = {"t": item["t"], "how": c[0], "ctx": item.get("ctx", ""),
                     "po": sorted(idx.get(C.norm(item["t"]), []))}
            is_data = item.get("data") or (not entry["po"] and not in_source(item["t"], blob))
            (data_found if is_data else found).append(entry)
        for item in r.get("attrs", []):
            c = classify(item["t"])
            if c:
                found.append({"t": item["t"], "how": c[0] + ":" + item["a"], "ctx": item.get("ctx", ""),
                              "po": sorted(idx.get(C.norm(item["t"]), []))})
        found.sort(key=lambda x: (x["t"], x["how"]))
        rows.append({"path": r["path"], "kind": r["kind"], "shot": r.get("shot", ""), "url": r.get("url", ""),
                     "count": len(found), "strings": found, "wrong": wrong, "data_strings": sorted(data_found, key=lambda x: x["t"]),
                     "missing": r.get("missing", ""), "console": r.get("console", []), "opened": r.get("opened", "")})
    return rows


def esc(s):
    return s.replace("|", "\\|").replace("\n", " ")


def to_md(rows, sweep, per_row=25):
    out = ["# VIFIX P1 — live Vietnamese sweep (generated by vifix_live_report.py)", ""]
    out.append("Screens recorded: %d (rail entries %d). Skipped: %d." % (
        len(rows), len([e for e in sweep.get("entries", []) if not e.get("sectionLocked")]), len(sweep.get("skipped", []))))
    allstr = collections.Counter()
    for r in rows:
        for s in r["strings"]:
            allstr[s["t"]] += 1
    out.append("Distinct English/mixed strings across all screens: %d; findings summed per screen: %d." % (
        len(allstr), sum(r["count"] for r in rows)))
    common = [t for t, n in allstr.items() if n >= max(3, len(rows) // 2)]
    out.append("Chrome strings on half the screens or more (counted once here, left out of the rows): %s" % (
        "; ".join("`%s`" % esc(t) for t in sorted(common)) or "none"))
    out.append("Strings not found in our source (records such as names, departments, pay-run names, "
               "or text built at runtime) are counted in the Data column and listed in the JSON only.")
    out += ["", "| Screen (as the menu shows it) | Count | Data | Strings still English / mixed (first %d) | Reads wrong (seed) | Screenshot |" % per_row,
            "|---|---|---|---|---|---|"]
    for r in rows:
        strs = [s for s in r["strings"] if s["t"] not in common]
        if r["missing"]:
            cell = "_%s_" % r["missing"]
        else:
            cell = "; ".join("`%s`%s" % (esc(s["t"][:80]), " (po: %s)" % ",".join(s["po"][:2]) if s["po"] else "")
                             for s in strs[:per_row]) or "—"
        wrong = "; ".join(sorted({"`%s` (%s)" % (esc(w["t"][:60]), w["seed"]) for w in r["wrong"]})) or "—"
        out.append("| %s | %d | %d | %s | %s | %s |" % (esc(r["path"]), len(strs), len(r["data_strings"]), cell, wrong, r["shot"]))
    if sweep.get("skipped"):
        out += ["", "## Not opened", ""] + ["- %s: %s" % (s["path"], s["why"]) for s in sweep["skipped"]]
    cons = [(r["path"], c) for r in rows for c in r["console"]]
    if cons:
        out += ["", "## Console errors seen", ""] + ["- %s: %s" % (p, esc(c[:160])) for p, c in cons[:40]]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sweep")
    ap.add_argument("--md")
    ap.add_argument("--json")
    a = ap.parse_args()
    sweep = json.load(open(a.sweep, encoding="utf-8"))
    rows = build(sweep)
    if a.json:
        json.dump(rows, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = to_md(rows, sweep)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md)
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
