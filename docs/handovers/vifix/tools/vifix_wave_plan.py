#!/usr/bin/env python3
"""VIFIX P1 scope F: group the scan findings into fix waves (offline, deterministic).

Run:  python3 vifix_wave_plan.py --po po.json --lit lit.json [--live rows.json] [--md out.md]
(po.json from vifix_po_scan.py --json, lit.json from vifix_literal_scan.py --json,
rows.json from vifix_live_report.py --json.)

Per wave it counts, for installed modules only:
  po_fix      existing msgstr to rewrite (suspicious, word order, mixed, same-text, placeholder)
  po_new      strings that need a NEW translation: template text/attributes and wrapped
              _t()/_() strings with no Vietnamese, plus .po entries the .pot drops
  code        code changes before translation: template-expression literals, JS strings outside
              _t(), Python UI strings outside _(), glued sentences
  markers     entries that never load (missing marker/occurrence)
  model_terms po_fix rows that are MODEL terms (field labels, menus, selections, views): stored
              per database, so the deploy needs the guarded overwrite load (LEARNREV LR20/LR29)
Effort (days) = po_fix/250 + po_new/200 + code/120 + markers/400, + 0.5 when model_terms > 0.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vifix_common as C  # noqa: E402

WAVES = [
    ("W1", "Home, the app frame and the employee's own pages",
     "everyone who signs in: staff on Home, every employee on My Payobook",
     "pb_home_hub pb_dashboard pb_hub pb_sidebar biz_theme biz_errors pb_theme pb_today pb_ask_hr pb_hr_comm "
     "pb_rnr pb_login_language pb_me_portal pb_me_portal_comm pb_me_portal_website pb_me_expense pb_me_trip "
     "pb_me_project_time pb_ess_workforce"),
    ("W2", "Approvals (the inbox and every approval card)",
     "every approver and requester",
     "pb_approval pb_approval_config biz_approval_workflow biz_approval_chain"),
    ("W3", "Payroll: running a month",
     "payroll staff every month",
     "pb_payhub pb_payruns pb_payrun_wizard pb_payrun_results pb_payrun_ledgers pb_payslip pb_payslip_review "
     "pb_pay_delivery pb_records pb_import pb_import_advanced pb_import_batch pb_import_kit pb_import_wizard "
     "pb_payroll_templates pb_hr_fullandfinal pb_workforce_payroll_bridge pb_trip_payroll_bridge"),
    ("W4", "Payroll: setup, formulas and the Vietnamese rules",
     "payroll leads and implementers",
     "pb_hr_payroll_base pb_hr_payroll_formula pb_hr_payroll_vietnam pb_statutory pb_pack_vn pb_pack_id pb_pack_in "
     "pb_pack_my pb_pack_sg pb_pack_th pb_scheme_map pb_formula_studio pb_structures pb_source_atlas pb_blueprint"),
    ("W5", "People and the joining-to-leaving boards",
     "HR every day",
     "pb_people_hub pb_people pb_people_advanced pb_employee_vault pb_contracts pb_contract_lifecycle pb_lifecycle "
     "pb_onboarding pb_probation pb_offboarding pb_assets pb_team"),
    ("W6", "Hiring and Talent",
     "HR and hiring managers",
     "pb_hiring pb_talent_hub pb_goals pb_training pb_pip"),
    ("W7", "Time, leave and expenses",
     "HR, team leads and every employee who clocks in or claims",
     "pb_time_hub pb_mission pb_hr_workforce pb_attendance_flow pb_close pb_timeoff pb_schedule pb_timesheet_approval "
     "pb_wf_kit pb_workseg pb_driver_checkin biz_week_grid biz_geo_tracking pb_hr_flow pb_expenses_hub "
     "pb_business_trip pb_trip_expense_bridge"),
    ("W8", "Insights and Compliance",
     "managers, finance and compliance",
     "pb_insights_hub pb_insights pb_explorer pb_hr_payroll_analytics pb_workforce_insights pb_budget "
     "pb_decision_room pb_comp_ben pb_group pb_pay pb_hr_payroll_demand pb_compliance_hub pb_govt_reports pb_hr_govt "
     "pb_audit pb_bank_ocr pb_young_worker biz_audit_trail"),
    ("W9", "Settings, access, connections, PayAI and the rest",
     "administrators; the tenant console only the Payobook team",
     "pb_settings biz_access pb_vendor_access pb_integrations pb_zoho_bridge pb_zoho_sso pb_payai_actions "
     "pb_payroll_ai_insights biz_doc_ocr pb_website pb_tenants pb_tenancy pb_demo pb_demo_portal pb_demo_seed "
     "biz_debrand biz_deroute biz_deroute_website biz_mail_debrand biz_geo_tracking"),
]

PO_FIX = {"suspicious", "word_order", "mixed", "same_text", "placeholders"}
LIT_NEW = {"xml_text", "xml_attr", "js_wrapped_uncovered", "py_wrapped_uncovered"}
LIT_CODE = {"xml_expr", "js_unwrapped", "py_unwrapped", "js_concat"}


def days_of(c):
    return c["po_fix"] / 250 + c["po_new"] / 200 + c["code"] / 120 + c["markers"] / 400 + (0.5 if c["model_terms"] else 0)


def plan(po, lit, live=None, split=0.0):
    wave_of = {}
    for code, _t, _who, mods in WAVES:
        for m in mods.split():
            wave_of.setdefault(m, code)
    per_mod = collections.defaultdict(collections.Counter)
    acc = collections.OrderedDict((w[0], collections.Counter()) for w in WAVES)
    acc["--"] = collections.Counter()
    mods_of = collections.defaultdict(set)
    unmapped = set()
    seen_fix = set()
    for check, rows in po["findings"].items():
        if check.startswith("drift"):
            continue
        for r in rows:
            m = r["module"]
            if m not in C.INSTALLED or m == "pb_learn":
                continue
            w = wave_of.get(m)
            if not w:
                unmapped.add(m)
                w = "--"
            mods_of[w].add(m)
            if check in PO_FIX:
                k = (m, r["line"], r["msgid"])
                if k in seen_fix:
                    continue  # one entry with two problems is one fix
                seen_fix.add(k)
                acc[w]["po_fix"] += 1
                per_mod[m]["po_fix"] += 1
                if "model" in r["kind"]:
                    acc[w]["model_terms"] += 1
                    per_mod[m]["model_terms"] += 1
            elif check == "pot_dropped":
                acc[w]["po_new"] += 1
                per_mod[m]["po_new"] += 1
            elif check == "markers":
                acc[w]["markers"] += 1
                per_mod[m]["markers"] += 1
    for r in lit:
        m = r["module"]
        if not r.get("installed"):
            continue
        w = wave_of.get(m)
        if not w:
            unmapped.add(m)
            w = "--"
        mods_of[w].add(m)
        if r["cls"] in LIT_NEW:
            acc[w]["po_new"] += 1
            per_mod[m]["po_new"] += 1
        elif r["cls"] in LIT_CODE:
            acc[w]["code"] += 1
            per_mod[m]["code"] += 1
    if split:
        sub = []
        for code, title, who, mods in WAVES:
            order = [m for m in mods.split() if m in mods_of.get(code, ())]
            chunks, cur, cur_d = [], [], 0.0
            for m in order:
                d = days_of(per_mod[m])
                if cur and cur_d + d > split:
                    chunks.append(cur)
                    cur, cur_d = [], 0.0
                cur.append(m)
                cur_d += d
            if cur:
                chunks.append(cur)
            for i, ch in enumerate(chunks):
                c = collections.Counter()
                for m in ch:
                    c.update(per_mod[m])
                d = days_of(c)
                big = [m for m in ch if days_of(per_mod[m]) > split]
                sub.append(dict(wave=code + ("abcdefghij"[i] if len(chunks) > 1 else ""), title=title, who=who,
                                modules=ch, days=round(d, 1),
                                note=("split by screen inside %s" % ", ".join(big)) if big else "",
                                risk=_risk(c), **{k: c[k] for k in ("po_fix", "po_new", "code", "markers", "model_terms")}))
        return sub, sorted(unmapped)
    out = []
    for code, title, who, _m in WAVES + [("--", "Unmapped", "", "")]:
        c = acc.get(code, collections.Counter())
        if code == "--" and not c:
            continue
        days = days_of(c)
        risk = _risk(c)
        out.append(dict(wave=code, title=title, who=who, modules=sorted(mods_of.get(code, ())),
                        days=round(days, 1), risk=risk, **{k: c[k] for k in ("po_fix", "po_new", "code", "markers", "model_terms")}))
    return out, sorted(unmapped)


def _risk(c):
    if c["model_terms"] > 50:
        return "higher: many stored labels, guarded overwrite load on 4 databases"
    if c["model_terms"]:
        return "normal: a few stored labels (guarded overwrite load)"
    return "low: screen text only, a restart loads it"


def to_md(rows, unmapped):
    out = ["| Wave | Area | Who sees it | Modules | Rewrite Vietnamese | New Vietnamese | Code changes | Never-loading entries | Stored labels at deploy | Days (est.) | Risk |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append("| %s | %s | %s | %d | %d | %d | %d | %d | %d | %.1f | %s |" % (
            r["wave"], r["title"], r["who"], len(r["modules"]), r["po_fix"], r["po_new"], r["code"], r["markers"],
            r["model_terms"], r["days"], r["risk"] + ("; " + r["note"] if r.get("note") else "")))
    out += ["", "Modules per wave:", ""]
    for r in rows:
        out.append("- **%s** %s" % (r["wave"], ", ".join(r["modules"])))
    if unmapped:
        out += ["", "Unmapped installed modules: " + ", ".join(unmapped)]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--po", required=True)
    ap.add_argument("--lit", required=True)
    ap.add_argument("--json")
    ap.add_argument("--md")
    ap.add_argument("--split", type=float, default=0.0, help="cut each wave into sub-waves of at most N days")
    a = ap.parse_args()
    rows, unmapped = plan(json.load(open(a.po, encoding="utf-8")), json.load(open(a.lit, encoding="utf-8")),
                          split=a.split)
    if a.json:
        json.dump({"waves": rows, "unmapped": unmapped}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = to_md(rows, unmapped)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md)
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
