#!/usr/bin/env python3
"""VIFIX P1 scope A: static scan of every vi_VN.po of our modules (offline, deterministic).

Run:  python3 docs/handovers/vifix/tools/vifix_po_scan.py [--json out.json] [--md out.md]

What it reads, exactly as the server does (odoo/tools/translate.py PoFileReader, checked on
the box 2026-10-21): ``<m>/i18n/vi_VN.po`` merged with ``<m>/i18n/<m>.pot`` when that .pot
exists. polib's merge takes msgid, occurrences and extracted comments (``#.``) from the
.pot, keeps the .po msgstr, and marks every .po entry that the .pot lacks OBSOLETE, which
the reader skips. So with a .pot, the markers that count are the .pot's, and a .po-only
entry never loads.

Checks (one finding list each):
  same_text      msgstr identical to the English msgid, minus the VF1 allowlist
  empty          effective msgstr empty (incl. .pot entries the .po does not translate)
  pot_dropped    .po entries obsoleted by the .pot merge (translated but never loaded)
  drift          one English msgid translated several ways across modules (top 100 by use)
  suspicious     seed list of literal machine translations + any "odoo" (msgid or msgstr)
  mixed          English word (>= 4 letters) inside a Vietnamese msgstr
  no_diacritics  msgstr that is Latin-only, differs from the English and reads as
                 Vietnamese typed without tone marks
  loanwords      English loanwords inside Vietnamese msgstr (email, file...): for the glossary
  markers        crash: comment does not start with ``module:``/``modules:``;
                 dropped: no occurrence, malformed occurrence, or a ``code:`` occurrence
                 without ``odoo-python``/``odoo-javascript``
  placeholders   placeholder multiset differs between msgid and msgstr
"""
import argparse
import collections
import json
import os
import re
import sys

import polib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vifix_common as C  # noqa: E402

# Seed list of literal translations (handover A); extended during P1, each with the reason.
SUSPICIOUS = [
    ("cú đấm", "punch = a blow; a time-clock punch is 'lượt chấm công'"),
    ("đấm", "punch = a blow"),
    ("hết tiền", "'out of money'; money out = 'tiền chi ra'"),
    ("trần nhà", "a room's ceiling; contribution ceiling = 'mức trần'"),
    ("bề mặt", "'surface' of an object; a screen area = 'màn hình'/'khu vực'"),
    ("giao diện tìm kiếm", "search surface, literal"),
    ("ống kính", "camera lens; a report lens/view = 'góc nhìn'/'chế độ xem'"),
    ("diễn viên", "a film actor; the person who acted = 'người thực hiện'"),
    ("chân nhân viên", "leg; employee share = 'phần người lao động'"),
    ("chân chủ", "leg; employer share = 'phần doanh nghiệp'"),
    ("hiển thị tên", "word order wrong for 'Display Name' = 'Tên hiển thị'"),
    ("phiếu lương đợt", "word-for-word 'Payslip Batch' = 'Đợt chi lương'/'Bảng lương'"),
    ("đường ray", "railway rail; a UI rail = 'thanh bên'"),
    ("làn đường", "a road lane; a UI lane = 'cột'/'nhóm'"),
    ("cái kệ", "shelf, literal"),
    ("vé", "ticket (travel); a support ticket = 'yêu cầu'"),
    ("dấu vết", "trace/trail literal; audit trail = 'lịch sử thay đổi'"),
    ("hạt giống", "seed (plant); seed data = 'dữ liệu mẫu'"),
    ("người chạy", "runner (a person running)"),
    ("cửa hàng", "store (shop); data store = 'kho dữ liệu'"),
    ("bánh mì", "breadcrumb literal"),
    ("vụn bánh", "breadcrumb literal"),
    ("chìa khóa", "physical key; a data key = 'khóa'/'mã'"),
    ("cái móc", "hook literal"),
    ("mỏ neo", "anchor literal"),
    ("ngăn kéo", "drawer (furniture); a slide-over panel = 'bảng bên'"),
    ("con chip", "microchip; a UI chip = 'nhãn'"),
    ("viên thuốc", "pill literal; a UI pill = 'nhãn'"),
    ("sân khấu", "theatre stage; a step of a process = 'bước'/'giai đoạn' (seen live: 'SÂN KHẤU 2 / 5')"),
    ("odoo", "white-label rule: never 'Odoo' on screen"),
]
SUSPICIOUS_RES = [(re.compile(r"(?<![\wÀ-ỹ])" + re.escape(s) + r"(?![\wÀ-ỹ])", re.I), s, why)
                  for s, why in SUSPICIOUS]


def effective_entries(po_path, pot_path):
    po = polib.pofile(po_path, wrapwidth=0)
    # line numbers of the .po entries (polib keeps .linenum)
    po_lines = {e.msgid_with_context: e.linenum for e in po}
    dropped = []
    if pot_path:
        pot = polib.pofile(pot_path, wrapwidth=0)
        pot_ids = {e.msgid_with_context for e in pot}
        dropped = [e for e in po if not e.obsolete and e.msgid_with_context not in pot_ids]
        po.merge(pot)
    entries = [e for e in po if not e.obsolete]
    return entries, dropped, po_lines


def check_markers(e):
    out = []
    comment = e.comment or ""
    if not re.match(r"(module[s]?): (\w+)", comment):
        out.append("crash: comment does not start with 'module:'")
    if not e.occurrences:
        out.append("dropped: no occurrence")
    has_marker = "odoo-python" in comment or "odoo-javascript" in comment
    for occ, _line in e.occurrences:
        if re.match(r"(model|model_terms):([\w.]+),([\w]+):(\w+)\.([^ ]+)", occ):
            continue
        if re.match(r"(code):([\w/.]+)", occ):
            if not has_marker:
                out.append("dropped: code occurrence without odoo-python/odoo-javascript")
            continue
        if re.match(r"(selection|sql_constraint|constraint):", occ):
            out.append("dropped: deprecated occurrence %s" % occ)
            continue
        out.append("dropped: malformed occurrence %s" % occ)
    return sorted(set(out))


def kind_of(e):
    kinds = set()
    for occ, _ in e.occurrences:
        if occ.startswith("code:"):
            kinds.add("code")
        elif occ.startswith(("model:", "model_terms:")):
            kinds.add("model")
    return "+".join(sorted(kinds)) or "none"


def scan(repo=C.REPO):
    res = collections.defaultdict(list)
    per_module = collections.OrderedDict()
    by_msgid = collections.defaultdict(list)
    accented, plain = collections.Counter(), collections.Counter()
    plain_rows = []
    for m in C.our_modules(repo):
        po_path = os.path.join(repo, m, "i18n", "vi_VN.po")
        if not os.path.exists(po_path):
            per_module[m] = {"has_po": False, "installed": m in C.INSTALLED}
            continue
        pot_path = os.path.join(repo, m, "i18n", m + ".pot")
        pot_path = pot_path if os.path.exists(pot_path) else None
        entries, dropped, po_lines = effective_entries(po_path, pot_path)
        stats = collections.Counter()
        stats["entries"] = len(entries)
        relpo = C.rel(po_path, repo)

        def add(check, e, **kw):
            row = {"module": m, "file": relpo, "line": po_lines.get(e.msgid_with_context, 0),
                   "kind": kind_of(e), "msgid": e.msgid, "msgstr": e.msgstr}
            row.update(kw)
            res[check].append(row)
            stats[check] += 1

        for e in dropped:
            add("pot_dropped", e)
        for e in entries:
            msgid, msgstr = e.msgid, e.msgstr
            if e.msgid_plural:
                msgstr = e.msgstr_plural.get(0, "") if e.msgstr_plural else ""
            if msgid and msgstr:
                by_msgid[msgid.strip()].append((m, msgstr))
            for prob in check_markers(e):
                add("markers", e, problem=prob)
            if not msgstr.strip():
                add("empty", e)
                # an empty msgstr still shows its English; check the English for the brand word
                for rx, seed, why in SUSPICIOUS_RES:
                    if seed == "odoo" and rx.search(msgid):
                        add("suspicious", e, seed=seed, where="msgid", why=why)
                continue
            if msgstr.strip() == msgid.strip():
                if not C.same_text_is_legit(msgid):
                    add("same_text", e)
            hit = []
            for rx, seed, why in SUSPICIOUS_RES:
                if any(seed in h for h in hit):
                    continue  # "đấm" inside an already reported "cú đấm"
                if rx.search(msgstr):
                    hit.append(seed)
                    add("suspicious", e, seed=seed, where="msgstr", why=why)
                elif seed == "odoo" and rx.search(msgid):
                    add("suspicious", e, seed=seed, where="msgid", why=why)
            if C.has_vietnamese(msgstr):
                en = C.english_words(msgstr)
                if en:
                    add("mixed", e, words=sorted(set(en)))
                lw = C.loanwords(msgstr)
                if lw:
                    add("loanwords", e, words=sorted({w.lower() for w in lw}))
            elif msgstr.strip() != msgid.strip():
                en = C.english_words(msgstr)
                if en and len(en) * 2 >= len([w for w in C.latin_words(msgstr) if len(w) >= 2]):
                    add("mixed", e, words=sorted(set(en)), problem="no Vietnamese at all")
                else:
                    plain_rows.append({"module": m, "file": relpo, "line": po_lines.get(e.msgid_with_context, 0),
                                       "kind": kind_of(e), "msgid": e.msgid, "msgstr": msgstr})
            # Python %-formatting only applies to odoo-python code terms, and never to a stored
            # Python expression (mail/report name templates: "'Budget %s' % (object.fy)").
            py_fmt = ("odoo-python" in (e.comment or "") and kind_of(e).startswith("code")
                      and not re.search(r"['\"]\s*%\s*\(", msgid))
            pm, ps = C.placeholders(msgid), C.placeholders(msgstr)
            if pm != ps:
                add("placeholders", e, msgid_ph=pm, msgstr_ph=ps)
            elif not py_fmt:
                pass  # JS _t() formats only %(name)s / %s; a stray % is harmless there
            elif C.bare_percent(msgstr) and not C.bare_percent(msgid):
                add("placeholders", e, msgid_ph=pm, msgstr_ph=ps,
                    problem="stray % in the Vietnamese next to placeholders (format error risk)")
            elif C.bare_percent(msgid):
                add("placeholders", e, msgid_ph=pm, msgstr_ph=ps,
                    problem="stray % in the English next to placeholders (format error risk)")
            for w in C.WORD_RE.findall(C.clean_text(msgstr)):
                lw = w.lower()
                if C.has_vietnamese(lw):
                    accented[C.strip_accents(lw)] += 1
                elif lw.isascii():
                    plain[lw] += 1
        per_module[m] = dict(has_po=True, has_pot=bool(pot_path), installed=m in C.INSTALLED, **stats)

    # Vietnamese typed without tone marks: a Latin-only msgstr whose words, across the whole
    # corpus, are written WITH tone marks at least 5 times as often as without ("Luong", "Thang").
    for row in plain_rows:
        words = [w.lower() for w in C.latin_words(row["msgstr"]) if len(w) >= 2]
        bad = [w for w in words if accented[w] >= 5 * max(1, plain[w]) and accented[w] >= 5]
        if bad and len(bad) * 2 >= len(words):
            res["no_diacritics"].append(dict(row, words=sorted(set(bad))))

    # terminology drift
    drift = []
    for msgid, rows in by_msgid.items():
        variants = collections.defaultdict(set)
        for m, s in rows:
            variants[C.norm(s)].add((m, s.strip()))
        if len(variants) < 2:
            continue
        drift.append({
            "msgid": msgid, "uses": len(rows), "modules": len({m for m, _ in rows}),
            "variants": sorted(([sorted({s for _, s in v})[0], len(v), sorted({mm for mm, _ in v})]
                                for v in variants.values()), key=lambda x: (-x[1], x[0])),
        })
    drift.sort(key=lambda d: (-d["uses"], -len(d["variants"]), d["msgid"]))
    res["drift_all"] = drift
    res["drift"] = drift[:100]
    for k in list(res):
        if k not in ("drift", "drift_all"):
            res[k].sort(key=lambda r: (r["module"], r["line"], r["msgid"], r.get("problem", ""), r.get("seed", "")))
    return {"modules": per_module, "findings": res,
            "other_nonstandard_with_po": [m for m in C.other_nonstandard_modules(repo)
                                          if os.path.exists(os.path.join(repo, m, "i18n", "vi_VN.po"))]}


CHECKS = ["same_text", "empty", "pot_dropped", "suspicious", "mixed", "no_diacritics",
          "loanwords", "markers", "placeholders"]


def short(s, n=90):
    s = re.sub(r"\s+", " ", s or "").strip()
    return (s[: n - 1] + "…") if len(s) > n else s


def to_md(data, limit=40):
    f = data["findings"]
    mods = data["modules"]
    out = ["# VIFIX P1 — static .po scan (generated by vifix_po_scan.py)", ""]
    with_po = [m for m, s in mods.items() if s.get("has_po")]
    out.append("Modules in scope: %d; with vi_VN.po: %d; without: %d (%s)." % (
        len(mods), len(with_po), len(mods) - len(with_po),
        ", ".join(m for m, s in mods.items() if not s.get("has_po"))))
    out.append("Effective entries (after the .pot merge): %d." % sum(mods[m].get("entries", 0) for m in with_po))
    out.append("Other non-standard modules with a vi_VN.po (outside the pb_/biz_/biztinct_ scope): %s." %
               (", ".join(data["other_nonstandard_with_po"]) or "none"))
    out += ["", "## Totals", "", "| Check | Findings | In installed modules | Modules |", "|---|---|---|---|"]
    for c in CHECKS:
        rows = f.get(c, [])
        inst = [r for r in rows if r["module"] in C.INSTALLED]
        out.append("| %s | %d | %d | %d |" % (c, len(rows), len(inst), len({r["module"] for r in rows})))
    out.append("| drift (msgids with >1 translation) | %d | | |" % len(f.get("drift_all", [])))
    out += ["", "## Top modules per check", ""]
    for c in CHECKS:
        cnt = collections.Counter(r["module"] for r in f.get(c, []))
        if cnt:
            out.append("- **%s**: %s" % (c, ", ".join("%s %d" % kv for kv in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:8])))
    for c in CHECKS:
        rows = f.get(c, [])
        if not rows:
            continue
        out += ["", "## %s (%d; first %d)" % (c, len(rows), min(limit, len(rows))), "",
                "| Module | Line | Kind | English | Vietnamese now | Note |", "|---|---|---|---|---|---|"]
        for r in rows[:limit]:
            note = r.get("problem") or (r.get("seed") and "%s (%s) — %s" % (r["seed"], r["where"], r["why"])) \
                or (r.get("words") and ", ".join(r["words"])) \
                or (("ph %s vs %s" % (r["msgid_ph"], r["msgstr_ph"])) if "msgid_ph" in r else "")
            out.append("| %s | %s | %s | %s | %s | %s |" % (
                r["module"], r["line"], r["kind"], short(r["msgid"]).replace("|", "\\|"),
                short(r["msgstr"]).replace("|", "\\|"), short(str(note), 120).replace("|", "\\|")))
    out += ["", "## Terminology drift (top %d of %d)" % (len(f["drift"]), len(f["drift_all"])), "",
            "| English | Uses | Modules | Variants (Vietnamese ×entries) |", "|---|---|---|---|"]
    for d in f["drift"]:
        out.append("| %s | %d | %d | %s |" % (short(d["msgid"], 60).replace("|", "\\|"), d["uses"], d["modules"],
                   " · ".join("%s ×%d" % (short(v[0], 40).replace("|", "\\|"), v[1]) for v in d["variants"][:5])))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--md")
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args()
    data = scan()
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
    md = to_md(data, a.limit)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(md)
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
