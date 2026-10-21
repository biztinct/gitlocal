#!/usr/bin/env python3
"""VIFIX P1 scope E — the replica drift report.

Every practice copy ("replica") of a real screen in Learn, checked against the
real screen's own files, offline, over this checkout. Not only the 16 screens
that have a lesson manifest (those are already gated by the replica half of
`pb_learn/tests/guide_truth.py`): every builder in
`pb_learn/static/src/engine/screens.js`.

    python3 docs/handovers/vifix/tools/vifix_replica_drift.py            # markdown on stdout
    python3 docs/handovers/vifix/tools/vifix_replica_drift.py --json out.json

Stdlib only. Reuses `guide_truth.py` (imported by path) for `.po` parsing
(`live_po`, `_msgids`) and cross-checks every builder region against its
`replica_region` rule (a warning on stderr if they ever disagree).
Deterministic: every list is sorted, nothing reads the clock or the
environment. About a minute on a laptop.

WHERE A REPLICA'S WORDS COME FROM
---------------------------------
`screens.js` holds one zero-argument builder per replica (`SCREENS.<id>()`).
A builder's visible words are the bilingual pairs it draws:

  * `B("en", "vi")`, `EN("en")` (product English in both languages) and
    `{ en: "…", vi: "…" }` literals, in the builder itself, in the top-level
    helpers it calls (`runCard(…)`, `mapTop(…)`, …) and in the top-level
    constants it names (`KIND_LABEL`, `LEDGER_TABS`, …);
  * `T("key")` chrome strings (`learn_content.json` › chrome);
  * the state labels `statusChip("<kind>", …)` prints (fixture STATUS_LABELS);
  * the practice data blocks it reads (`PRACTICE.<path>` in
    `pb_learn/static/src/engine/fixture.js`, the generated copy of
    `docs/tutorial_poc/author/practice-data.js` — same bytes plus a banner, so
    reading either is the same; the tool reads the shipped one, as the gate
    does). A local alias (`const t = PRACTICE.wftoday`) narrows the block to
    the fields the builder actually reads (`t.tiles`, `t.needs`), so one
    screen is not charged with another screen's data.

The fixture is walked by a small JS tokenizer (strings, comments, template
literals, regex literals, bracket stack), so every pair knows its key path
(`PRACTICE.exits.desks[1].k`) — that is what tells a label from a data value.

WHAT COUNTS AS A UI LABEL (false-positive control)
-------------------------------------------------
A pair is NOT checked when it is:
  * a fragment glued into a sentence (`B("The ", "Đợt ")`, `B(" run (", …)`):
    raw English starts/ends with a space or ends with `(`;
  * no words (fewer than two letters once numbers are masked) or a lone
    function word (`of`, `with`, `the`, …);
  * fixture DATA: the value of a key in `DATA_KEYS` (names, periods, row
    sub-lines, reasons, notes, roles, demo people/companies…), or a
    non-first element of a `[label, value]` tuple;
  * a demo-world value: carries a demo person's name (read from the
    fixture), a division or place ("Retail", "Hà Nội", "F&B"), or is only a
    period ("July 2026", "Jan", "vs June 2026");
  * practice-only wording (says "practice", "drawn open", "sample data",
    "In Payobook …", a "Home › Announce" breadcrumb — the replica talking
    about itself), or drawn by a practice-only helper (`PRACTICE_ONLY_HELPERS`);
  * a replica NOTE: a sentence of more than six words drawn inside
    `class="lrn-note"` / `lrn-shellnote`. Notes are mostly the lesson
    explaining the screen; they are counted and listed in the JSON as
    `notes_not_on_screen`, never as drift.

HOW A LABEL IS COMPARED
-----------------------
Both sides go through `canon()`: entities resolved, tags dropped, lower case,
`&` read as "and", every number / date / money figure, month name and every
placeholder (`%s`, `%(n)s`, `{{…}}`, `${…}`, `<t t-esc/>`) becomes `#`,
punctuation dropped, whitespace collapsed. So "Week of 27/07 – 02/08/2026"
is "week of #" and the product's `_t("Close week %s")` is "close week #".

A label is FOUND when its canon form is a whole-word run inside one text unit
of the real screen. Text units are, per file:
  * OWL XML: every text node, every element's flattened text (inline markup
    and `t-esc`/`t-out` children as `#`, units up to 240 chars), literal
    `title` / `placeholder` / `aria-label` / `string` / `help` attributes and
    every quoted literal inside a `t-*` expression;
  * JS: every string and template literal (`${…}` as `#`; inline XML in a
    template literal is split at its tags too);
  * Python (labels the screen gets over RPC): every string constant (AST,
    docstrings skipped), remembering whether it is wrapped in `_()` /
    `_lt()` or is a `fields.Selection` label. A Python string matches only
    when it is at most `PY_SLACK` (3) words longer than the label — a payload
    label is a whole string; a label inside a long message is an accident.

Three levels, first hit wins:
  1. `screen`  — the mapped template(s) plus what they pull in: the JS
     component whose `template` names a template of the file, `t-call`
     targets and sub-components (two levels, `pb_*`/`biz_*` only), and for
     hubs whose content other modules register (`REGISTERED_FILES`: Settings
     categories, hub tabs) every registering JS file;
  2. `python`  — Python of the screen's modules plus `RPC_MODULES` (a module
     whose models feed the screen without drawing it); the row notes how
     many labels were found only here ("RPC labels");
  3. `module`  — anything else in those modules (other static files, the
     module `.pot` msgids). Found only here = "elsewhere in the module",
     listed as secondary (the label may have moved), NOT counted as drift.
Not found at any level = DRIFT ("gone").

A second drift kind, `hidden-only`: the label (two words or more) exists in
the screen's XML, but every occurrence sits under a `t-if`/`t-elif` whose
condition names an open menu (`…open…` / `…menu…`) or in a tooltip
(`title` / `aria-label`), and in no JS string — the real screen shows it only
after a click or on hover, while the replica draws it as a standing control
(Records' wide layout: "Export" + a drop zone on screen, "Export with data" /
"Import a file" only inside the File menu). A pair the replica itself draws
as a tooltip is not judged.

PSEUDO-REPLICA "(rail and tabs)": the practice shell's rail, sections, hub
tabs and Settings categories (fixture `MENU`), checked against the
`pb.sidebar` data records and every hub-lens / Settings-category
registration.

VIETNAMESE
----------
For a found label whose replica carries Vietnamese, the tool works out what
the real screen shows in Vietnamese:
  * XML/JS text: the msgid with the same canon form in the screen modules'
    live `vi_VN.po` (obsolete entries dropped against the `.pot`, as the
    loader does — `guide_truth.live_po`); when the screen's own modules do
    not have it, any other module's translation is accepted but the verdict
    is marked unsure (whether another module's term reaches this screen
    depends on how the web client scopes terms); a text found only inside a
    longer text uses that longer msgid's msgstr (containment, unsure);
    found in no `.po` at all = the screen shows English;
  * Python-only text: translated when the literal is wrapped in `_()`/`_lt()`
    (by its module's `.po`); a `fields.Selection` label is translated only
    when read as a field, not when the same list is shipped in a payload
    (exits desk lights), so that verdict is unsure; a bare literal reaches
    the screen in English.
Vietnamese drift kinds: `vi-differs` (screen says X, replica says Y),
`vi-screen-english` (screen has no Vietnamese; replica translates it),
`vi-replica-english` (screen translates it; the replica keeps English).
Unsure verdicts are listed with "(?)" and not counted.
A `{en, vi}` object the builder prints raw (`esc(r.en)` / `esc(r.vi)`) is
shown in both languages by the replica, so both sides are checked as English
text and no Vietnamese comparison is made.

SECONDARY: REAL LABELS MISSING FROM THE REPLICA
-----------------------------------------------
Short (1–4 word) visible text nodes of the mapped XML that no replica pair
contains. Replicas draw less than the product by design, so this is a count
in the table and a list in the JSON, never drift.

MAPPING
-------
`MAPPING` below: replica id -> real template file(s), with how each entry was
determined. The main evidence is `pb_learn/static/src/anchors.json`: the
product anchors (`data-coach`) a builder draws are registered with the
template file that lays them; the lesson manifests (`*/learn_manifest.py`
`templates`) cover the 16 gated screens; where a builder draws only `rep-*`
anchors, a distinctive label was grepped. A mapped file that does not exist
makes the row "real screen not found".
"""
import argparse
import ast
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, os.path.join(REPO, 'pb_learn', 'tests'))
import guide_truth as gt  # noqa: E402

#: Pseudo-replica id for the practice shell's rail and tab strips (MENU).
RAIL = '(rail and tabs)'

SCREENS_JS = 'pb_learn/static/src/engine/screens.js'
FIXTURE_JS = 'pb_learn/static/src/engine/fixture.js'
CONTENT_JSON = 'pb_learn/static/content/learn_content.json'

# --------------------------------------------------------------------- mapping
#: replica id -> real template files. One comment per entry: how it was found.
#: "anchors N" = N product anchors the builder draws are registered in
#: anchors.json against that file; "manifest" = the lesson manifest's
#: `templates`; "grep" = a distinctive replica label found in that file.
MAPPING = {
    # manifest (pb_dashboard) + anchors 6 (dash-hero, dash-kpis, …)
    'dashboard': ['pb_dashboard/static/src/xml/pb_dashboard.xml'],
    # manifest + anchors 13 (ai-*); builder comment names inbox.xml
    'approvals': ['pb_approval_config/static/src/xml/inbox.xml'],
    # manifest (people.xml) + anchors 7 there and 3 in contract_360.xml (the drawer drawn open)
    'employees': ['pb_people/static/src/xml/people.xml',
                  'pb_contracts/static/src/xml/contract_360.xml'],
    # anchors 4 in contracts.xml
    'contracts': ['pb_contracts/static/src/xml/contracts.xml'],
    # anchors 5; builder comment names insights.xml
    'insights': ['pb_insights/static/src/xml/insights.xml'],
    # anchors 7; builder comment names explorer.xml (compareHTML = Compare schemes)
    'explorer': ['pb_explorer/static/src/xml/explorer.xml'],
    # anchors 5 in workforce_insights.xml
    'workforcean': ['pb_workforce_insights/static/src/xml/workforce_insights.xml'],
    # anchors 3 + 3; builder comment: Payroll Report (inline template, English) and Budget board
    'reports': ['pb_hr_workforce/static/src/xml/payroll_report.xml',
                'pb_hr_workforce/static/src/js/payroll_report.js',
                'pb_budget/static/src/xml/budget_board.xml'],
    # manifest + anchors 4 (gr-*)
    'govreports': ['pb_govt_reports/static/src/xml/govt_reports.xml'],
    # manifest + anchors 13 (pw-*)
    'runpayroll': ['pb_payrun_wizard/static/src/xml/payrun_wizard.xml'],
    # manifest + anchors 13 (pk-*); builder comment names payruns.xml
    'payruns': ['pb_payruns/static/src/xml/payruns.xml'],
    # manifest + anchors 7
    'payslips': ['pb_payslip_review/static/src/xml/payslip_review.xml'],
    # manifest + anchors 5; builder comment names pb_import import.xml
    'import': ['pb_import/static/src/xml/import.xml'],
    # anchors 6; builder comment names pb_import_wizard
    'importwizard': ['pb_import_wizard/static/src/xml/import_wizard.xml'],
    # manifest + anchors 7 + 2
    'formula': ['pb_formula_studio/static/src/xml/studio.xml',
                'pb_formula_studio/static/src/xml/studio_experience.xml'],
    # no product anchors (rep-settings); builder comment names pb_settings settings_hub.js
    'hub_settings': ['pb_settings/static/src/xml/settings_hub.xml',
                     'pb_settings/static/src/js/settings_hub.js'],
    # anchors 5; builder comment names structures.xml
    'structures': ['pb_structures/static/src/xml/structures.xml'],
    # manifest + anchors 7
    'statutory': ['pb_statutory/static/src/xml/statutory.xml'],
    # anchors 4 + 2 (the connector's own screen); builder comment names integrations.xml
    'integrations': ['pb_integrations/static/src/xml/integrations.xml',
                     'pb_import_advanced/static/src/xml/connector_cockpit.xml'],
    # anchors 7 each (lg-*); ONE template serves all three ledgers
    'fullfinal': ['pb_payrun_ledgers/static/src/xml/ledger.xml'],
    'proration': ['pb_payrun_ledgers/static/src/xml/ledger.xml'],
    'retro': ['pb_payrun_ledgers/static/src/xml/ledger.xml'],
    # anchors 4 + 5 (bp-*)
    'blueprint': ['pb_blueprint/static/src/xml/blueprint.xml',
                  'pb_blueprint/static/src/xml/steps.xml'],
    # anchors 4 in blueprint.xml; the Pay rules step is drawn by steps.xml
    'blueprint_rules': ['pb_blueprint/static/src/xml/blueprint.xml',
                        'pb_blueprint/static/src/xml/steps.xml'],
    # anchors 2 + 2: Mapping › Journey (journey_board.xml) under the Mapping tabs (mapping_studio.xml).
    # NOT the manifest's connection_desk.xml: the copy draws Journey (guide_truth REPLICA_ABSENT)
    'mapping': ['pb_formula_studio/static/src/xml/journey_board.xml',
                'pb_formula_studio/static/src/xml/mapping_studio.xml'],
    # anchors 3 in mapping_studio.xml; grep "spreadsheet here" lands there too
    'mapping_sheet': ['pb_formula_studio/static/src/xml/mapping_studio.xml'],
    # manifest + anchors 10 (+2 for the Mapping tabs)
    'treatment': ['pb_formula_studio/static/src/xml/component_treatment.xml',
                  'pb_formula_studio/static/src/xml/mapping_studio.xml'],
    # manifest + anchors 6
    'matrix': ['pb_approval_config/static/src/xml/matrix_room.xml'],
    # only rep-* anchors; grep "Publish this route" / "Try an example" -> builder.xml
    'matrix_builder': ['pb_approval_config/static/src/xml/builder.xml'],
    # manifest + anchors 7 (rd-*)
    'records': ['pb_records/static/src/xml/records_desk.xml'],
    # anchors 3 (gp-*) in group_room.xml
    'schemes': ['pb_group/static/src/xml/group_room.xml'],
    # anchors: wf-today in pb_today.xml, wf-needs / wf-clean in pb_dock.xml
    'wftoday': ['pb_today/static/src/xml/pb_today.xml',
                'pb_mission/static/src/xml/pb_dock.xml'],
    # manifest (time_hub.xml) + anchors: wf-timeoff/leave queue in pb_timeoff.xml, wf-overtime/ot-* in pb_ot_desk.xml
    'wftime': ['pb_time_hub/static/src/xml/time_hub.xml',
               'pb_timeoff/static/src/xml/pb_timeoff.xml',
               'pb_hr_workforce/static/src/xml/pb_ot_desk.xml'],
    # anchors 4 (wf-close*) in pb_close_lens.xml
    'wfclose': ['pb_mission/static/src/xml/pb_close_lens.xml'],
    # anchors 6 (ac-*); builder comment names biz_access
    'access': ['biz_access/static/src/xml/access_board.xml'],
    # anchors 3 (cp-gen-*) in filing_flow.xml
    'filing_flow': ['pb_govt_reports/static/src/xml/filing_flow.xml'],
    # anchors: cp-bank* in pb_bank_ocr.xml, cp-young in pb_young_worker.xml, cp-audit* in pb_audit.xml
    'compliancemore': ['pb_bank_ocr/static/src/xml/pb_bank_ocr.xml',
                       'pb_young_worker/static/src/xml/pb_young_worker.xml',
                       'pb_audit/static/src/xml/pb_audit.xml'],
    # only rep-* anchors; grep "Say thank you" -> pb_rnr rnr_wall.xml; Home › Announce and its
    # Calendar -> pb_hr_comm (lens key coming_up in comm_announce_lens.js)
    'peoplemore': ['pb_rnr/static/src/xml/rnr_wall.xml',
                   'pb_hr_comm/static/src/xml/comm_announce_lens.xml',
                   'pb_hr_comm/static/src/xml/comm_calendar.xml'],
    # anchors 5 (pp-*) in pay.xml
    'paybands': ['pb_pay/static/src/xml/pay.xml'],
    # manifest (pay_review.xml) + anchors 8 there, 1 in pay.xml (the tabs)
    'payreview': ['pb_pay/static/src/xml/pay_review.xml', 'pb_pay/static/src/xml/pay.xml'],
    # anchors 9 in decision_room.xml
    'decisionroom': ['pb_decision_room/static/src/xml/decision_room.xml'],
    # anchors 11 (hi-*) in hiring_board.xml
    'hiring': ['pb_hiring/static/src/xml/hiring_board.xml'],
    # anchors 1 in hiring_requests_p3.xml; the Open a role dialog lives in hiring_board.xml (grep)
    'hiring_request': ['pb_hiring/static/src/xml/hiring_requests_p3.xml',
                       'pb_hiring/static/src/xml/hiring_board.xml'],
    # anchors 9 + 1 + 1 + 1; builder comment names hiring_board_p1.xml
    'hiringrole': ['pb_hiring/static/src/xml/hiring_board_p1.xml',
                   'pb_hiring/static/src/xml/hiring_p5.xml',
                   'pb_hiring/static/src/xml/hiring_p6.xml',
                   'pb_hiring/static/src/xml/hiring_privacy_p4.xml'],
    # anchors 5; builder comment names hiring_setup.xml
    'hiringsetup': ['pb_hiring/static/src/xml/hiring_setup.xml'],
    # anchors 3; builder comment names hiring_numbers.xml
    'hiringnumbers': ['pb_hiring/static/src/xml/hiring_numbers.xml'],
    # anchors 6 (nj-*) in onboarding_board.xml
    'joiners': ['pb_onboarding/static/src/xml/onboarding_board.xml'],
    # anchors 5 (pr-*) in probation_board.xml
    'probation': ['pb_probation/static/src/xml/probation_board.xml'],
    # anchors 4 (gw-*) in pip_board.xml
    'growth': ['pb_pip/static/src/xml/pip_board.xml'],
    # anchors 5 (cl-*) in contractlife_board.xml
    'contractends': ['pb_contract_lifecycle/static/src/xml/contractlife_board.xml'],
    # anchors 6 (ex2-*) in exits_board.xml
    'exits': ['pb_offboarding/static/src/xml/exits_board.xml'],
    # NAV P3d: anchors 4 (ah-*) in askhr_lens.xml (Home › Ask HR board)
    'askhr': ['pb_ask_hr/static/src/xml/askhr_lens.xml'],
    # anchors 3 (rs-*) in payrun_results.xml
    'results': ['pb_payrun_results/static/src/xml/payrun_results.xml'],
    # anchors 3 (dl-*) in pb_pay_delivery.xml
    'deliver': ['pb_pay_delivery/static/src/xml/pb_pay_delivery.xml'],
    # anchors 2 (pc-*) in paycal_board.xml
    'paycal': ['pb_comp_ben/static/src/xml/paycal_board.xml'],
    # anchors 3 (aw-*) in incentives_board.xml
    'awards': ['pb_comp_ben/static/src/xml/incentives_board.xml'],
    # pseudo-replica: the shell's rail sections/items are pb.sidebar records (grep "Understand"
    # -> pb_sidebar_data.xml); hub tabs and Settings categories join via REGISTERED_FILES
    RAIL: ['pb_sidebar/data/pb_sidebar_data.xml'],
}

#: Modules whose PYTHON also feeds a screen over RPC although none of its
#: templates is drawn (searched at the `python` level).
RPC_MODULES = {
    # the inbox drawer's facts ("Total net pay", "Contains overtime") are written by the
    # request's own model: grep -> pb_payruns/models/hr_payslip_run.py
    'approvals': ['pb_payruns'],
    # component kinds / net roles / pay-run values ("Added to net pay", "Pay month") are
    # served from the formula engine: grep -> pb_hr_payroll_formula/models/formula_net_role.py,
    # formula_rule.py
    'treatment': ['pb_hr_payroll_formula'],
    'mapping': ['pb_hr_payroll_formula'],
    'mapping_sheet': ['pb_hr_payroll_formula'],
    'formula': ['pb_hr_payroll_formula'],
    # the Close lens's flag kinds and handoff come from pb_close (close.py "Missing punch")
    'wfclose': ['pb_close'],
}

#: Screens whose real content is REGISTERED by other modules: every JS file
#: matching the pattern joins the screen's files. Settings categories are
#: added to `registry.category("pb_settings_category")` by each owning module
#: (settings_hub.js:256-271 documents the contract).
REGISTERED_FILES = {
    'hub_settings': r'SETTINGS_CATEGORIES|["\']pb_settings_category["\']',
    # the "rest of People" tiles are tabs other modules register on the People / Talent /
    # Home hubs (pb_workseg workseg_lens.js: registry.category(PEOPLE_LENSES).add("where", …))
    'peoplemore': r'\b(?:PEOPLE|TALENT|HOME)_LENSES\b|["\']pb_(?:people|talent|home)_hub_lens["\']',
    # the pseudo-replica of the practice shell's rail and tab strips (fixture MENU): every
    # hub-lens registration plus the Settings categories
    RAIL: r'\b[A-Z]+_LENSES\b|["\']pb_\w+_(?:hub_)?lens(?:es)?["\']|SETTINGS_CATEGORIES|'
          r'["\']pb_settings_category["\']',
}

#: Data files that also carry real labels for a pseudo-replica: the rail's
#: entries are `pb.sidebar` records (pb_sidebar/data/pb_sidebar_data.xml and
#: each module's data/pb_sidebar.xml).
REGISTERED_DATA = {
    RAIL: r'sidebar[^/]*\.xml$',
}

#: Helpers that draw a practice-only panel (said so on the panel itself):
#: their pairs are not compared. newEmployeeHTML: "New employee — practice
#: form" drawn inline; the product opens its own form view instead.
PRACTICE_ONLY_HELPERS = frozenset(['newEmployeeHTML'])

#: Fixture keys whose values are DATA (rows, people, periods, sub-lines), not
#: UI labels. Determined by dumping every key a fixture pair sits under and
#: reading what it holds.
DATA_KEYS = frozenset('''
    name sub what period title last route say applies job src level next text
    when subtitle_data paidIn type month note due why reason boardDeadline
    division preparing lede headline meaning who rule closedHint budget share
    chip role day line value desc eg to code policy family stage from praise
    announce run where approval outcome reading m months chips_data family
    hints scores waiting list todo done process notes saved money band v
'''.split())

#: A label made only of these (and `#`) is a period or a date — a data value.
MONTH_WORDS = frozenset('''
    jan feb mar apr may jun jul aug sep oct nov dec january february march april june july
    august september october november december vs th tháng so với only chỉ
'''.split())

#: Fixture containers whose whole content is practice DATA: rows of a list,
#: the practice scheme's components and fields, filter values, demo
#: companies. A pair anywhere under one of these keys is not a UI label.
DATA_PATH_KEYS = frozenset('''
    rows components scheme systems sheetColumns fed picked chips missing configs
    recentRuns board slips importBatches connectors arrivals companies compare
    leaver bands feeds transforms requests
'''.split())

#: Demo world words: a label carrying one is a data value (a division, a
#: place, the practice company). Person names are read from the fixture's
#: EMP block at run time and added to this.
DEMO_WORDS = ('Hà Nội', 'Hải Phòng', 'Hoa Sen', 'Retail', 'F&B', 'Singapore', 'Đà Nẵng',
              'Hồ Chí Minh', 'Zoho', 'Excel File', 'Demo / Stub')

#: JS members that end a PRACTICE path (`PRACTICE.importPipe.map`).
JS_MEMBERS = frozenset('map filter length reduce find some every forEach slice join includes '
                       'indexOf findIndex concat flatMap'.split())

#: Lone words that carry no label on their own.
STOP = frozenset('of the and or with by to from in at for a an vs per on is it e g'.split())

PRACTICE_ONLY_RE = re.compile(
    r'\bpractice\b|drawn open|— drawn|sample data|\bin payobook\b|here it sits|'
    r'what it looks like afterwards|thực hành|đang mở sẵn', re.I)

#: A t-if/t-elif condition that means "only after a click opens it".
MENU_COND_RE = re.compile(r'\w*(?:open|Open|menu|Menu)\w*')

LITERAL_ATTRS = ('title', 'placeholder', 'aria-label', 'alt', 'string', 'help', 'label',
                 'data-tooltip', 'data-tip')
PY_SLACK = 3
TOOLTIP_ATTR_RE =re.compile(r'(?:^|-)(?:title|aria-label|data-tooltip|data-tip)$')
SKIP_T_ATTRS = ('t-name', 't-call', 't-foreach', 't-as', 't-key', 't-ref', 't-model',
                't-component', 't-slot', 't-props')


# ------------------------------------------------------------------- reading
def rel_path(*parts):
    return os.path.join(REPO, *parts)


_READ = {}


def read(rel):
    if rel not in _READ:
        path = rel_path(rel)
        if not rel or not os.path.isfile(path):
            _READ[rel] = None
        else:
            with open(path, encoding='utf-8') as fh:
                _READ[rel] = fh.read()
    return _READ[rel]


# ------------------------------------------------------------------- canon
_TAG = re.compile(r'<[^>]*>')
_PLACE = re.compile(r'%\([^)]*\)[sd]|%[sd]|\{\{.*?\}\}|\$\{[^}]*\}|\{\w*\}')
_NUM = re.compile(r'[₫$€£]?\d[\d.,:/–\-_]*(?:\s*(?:%|₫|vnd|h|m)\b)?', re.I)
_PUNCT = re.compile(r'[^\w#]+', re.U)
_HASHES = re.compile(r'#(?:\s+#)+')
_VI_MONTH = re.compile(r'\b(?:tháng|thg|th)\s*#')
#: Month names are data too ("July payroll" vs `_t("%(month)s payroll")`). "may" is
#: left alone: it is also a verb.
_MONTH = re.compile(r'\b(?:january|february|march|april|june|july|august|september|october|'
                    r'november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b')


def canon(s):
    s = html.unescape(str(s or ''))
    s = s.replace('’', "'").replace('‘', "'").replace('\u00a0', ' ')
    s = _TAG.sub(' ', s)
    s = _PLACE.sub(' # ', s)
    s = s.lower().replace('&', ' and ')
    s = _MONTH.sub(' # ', s)
    s = _NUM.sub(' # ', s)
    s = _VI_MONTH.sub(' # ', s)     # "tháng 7/2026", "Th7" are a month, i.e. data
    s = _PUNCT.sub(' ', s).replace('_', ' ')
    s = ' '.join(s.split())
    return _HASHES.sub('#', s)


def letters(s):
    return sum(1 for ch in s if ch.isalpha())


# --------------------------------------------------------------- JS tokenizer
_STR = r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\''
_B_CALL = re.compile(r'B\(\s*(%s)\s*,\s*(%s)\s*\)' % (_STR, _STR), re.S)
_EN_CALL = re.compile(r'EN\(\s*(%s)\s*\)' % _STR, re.S)
_T_CALL = re.compile(r'T\(\s*"([A-Za-z0-9_.]+)"\s*\)')
_ENVI_OBJ = re.compile(r'\{\s*en:\s*(%s)\s*,\s*vi:\s*(%s)\s*\}' % (_STR, _STR), re.S)
_IDENT = re.compile(r'[A-Za-z_$][\w$]*')
_REGEX_PREV = set('(,=:[!&|?{};+-*%<>~^')


def _lit(tok):
    """A JS string literal's value."""
    body = tok[1:-1]
    return re.sub(r'\\(.)', lambda m: {'n': '\n', 't': '\t'}.get(m.group(1), m.group(1)), body)


def scan_js(src):
    """Walk JS source once. Returns (events, strings):
    events  — every bilingual pair / chrome call: dict(pos, kind, en, vi, path, tuple_index)
    strings — every string literal and template-literal text (with `#` for `${…}`)."""
    events, strings = [], []
    stack = []          # containers: dict(ch, path, key, index)
    modes = ['code']    # 'code' | 'tpl'
    tpl_buf = []        # text buffers of open template literals
    pending_root = None
    prev = ''           # previous significant code char / token kind
    i, n = 0, len(src)

    def cur_path():
        if not stack:
            return [pending_root] if pending_root else []
        top = stack[-1]
        p = list(top['path'])
        if top['ch'] == '{' and top['key'] is not None:
            p.append(top['key'])
        elif top['ch'] == '[':
            p.append(top['index'])
        return p

    def tuple_index():
        if len(stack) >= 2 and stack[-1]['ch'] == '[' and stack[-2]['ch'] == '[':
            return stack[-1]['index']
        return None

    while i < n:
        c = src[i]
        if modes[-1] == 'tpl':
            if c == '\\':
                tpl_buf[-1].append(src[i:i + 2])
                i += 2
                continue
            if c == '`':
                strings.append(''.join(tpl_buf.pop()))
                modes.pop()
                i += 1
                prev = 'str'
                continue
            if src.startswith('${', i):
                tpl_buf[-1].append(' # ')
                stack.append({'ch': '${', 'path': cur_path() if stack else [], 'key': None, 'index': 0})
                modes.append('code')
                i += 2
                prev = '{'
                continue
            tpl_buf[-1].append(c)
            i += 1
            continue
        # ---- code
        if c in ' \t\r\n':
            i += 1
            continue
        if src.startswith('//', i):
            j = src.find('\n', i)
            i = n if j < 0 else j
            continue
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in '"\'':
            m = re.compile(_STR).match(src, i)
            if not m:
                i += 1
                continue
            val = _lit(m.group(0))
            strings.append(val)
            j = m.end()
            # a quoted object key
            k = j
            while k < n and src[k] in ' \t':
                k += 1
            if k < n and src[k] == ':' and stack and stack[-1]['ch'] == '{' and prev in ('{', ','):
                stack[-1]['key'] = val
            i = j
            prev = 'str'
            continue
        if c == '`':
            modes.append('tpl')
            tpl_buf.append([])
            i += 1
            continue
        if c == '/' and (prev in _REGEX_PREV or prev in ('', 'return', 'typeof', 'case')):
            j = i + 1
            in_cls = False
            while j < n:
                ch = src[j]
                if ch == '\\':
                    j += 2
                    continue
                if ch == '[':
                    in_cls = True
                elif ch == ']':
                    in_cls = False
                elif ch == '/' and not in_cls:
                    break
                elif ch == '\n':
                    break
                j += 1
            j += 1
            while j < n and src[j].isalpha():
                j += 1
            i = j
            prev = 'regex'
            continue
        if c == '{':
            m = _ENVI_OBJ.match(src, i)
            if m:
                events.append({'pos': i, 'kind': 'obj', 'en': _lit(m.group(1)), 'vi': _lit(m.group(2)),
                               'path': cur_path(), 'tuple_index': tuple_index()})
                strings.extend([_lit(m.group(1)), _lit(m.group(2))])
                i = m.end()
                prev = 'str'
                continue
        if c in '{[(':
            parent_path = cur_path()
            stack.append({'ch': c, 'path': parent_path, 'key': None, 'index': 0})
            i += 1
            prev = c
            continue
        if c in '}])':
            if stack:
                top = stack.pop()
                if top['ch'] == '${':
                    modes.pop()
            i += 1
            prev = c
            continue
        if c == ',':
            if stack:
                stack[-1]['index'] += 1
                if stack[-1]['ch'] == '{':
                    stack[-1]['key'] = None
            i += 1
            prev = ','
            continue
        if c == ';':
            if not stack:
                pending_root = None
            i += 1
            prev = ';'
            continue
        m = _IDENT.match(src, i)
        if m:
            word = m.group(0)
            if word == 'B':
                bm = _B_CALL.match(src, i)
                if bm:
                    en, vi = _lit(bm.group(1)), _lit(bm.group(2))
                    events.append({'pos': i, 'kind': 'B', 'en': en, 'vi': vi,
                                   'path': cur_path(), 'tuple_index': tuple_index()})
                    strings.extend([en, vi])
                    i = bm.end()
                    prev = ')'
                    continue
            if word == 'EN':
                em = _EN_CALL.match(src, i)
                if em:
                    en = _lit(em.group(1))
                    events.append({'pos': i, 'kind': 'EN', 'en': en, 'vi': en,
                                   'path': cur_path(), 'tuple_index': tuple_index()})
                    strings.append(en)
                    i = em.end()
                    prev = ')'
                    continue
            if word == 'T':
                tm = _T_CALL.match(src, i)
                if tm:
                    events.append({'pos': i, 'kind': 'T', 'en': tm.group(1), 'vi': None,
                                   'path': cur_path(), 'tuple_index': tuple_index()})
                    i = tm.end()
                    prev = ')'
                    continue
            j = m.end()
            k = j
            while k < n and src[k] in ' \t':
                k += 1
            if word in ('const', 'let', 'var') and not stack:
                nm = _IDENT.match(src, k)
                if nm:
                    pending_root = nm.group(0)
            elif word == 'get' and stack and stack[-1]['ch'] == '{':
                nm = _IDENT.match(src, k)
                if nm and src[nm.end():nm.end() + 1] == '(':
                    stack[-1]['key'] = nm.group(0)
            elif k < n and src[k] == ':' and stack and stack[-1]['ch'] == '{' and prev in ('{', ','):
                stack[-1]['key'] = word
            i = j
            prev = word if word in ('return', 'typeof', 'case') else 'id'
            continue
        i += 1
        prev = c
    return events, strings


# ------------------------------------------------------------ replica words
def builder_spans(src):
    """{id: (start, end)} char offsets of every SCREENS builder."""
    out = {}
    lines = src.split('\n')
    offs = [0]
    for ln in lines:
        offs.append(offs[-1] + len(ln) + 1)
    start_line = None
    name = None
    for i, ln in enumerate(lines):
        m = re.match(r'^    (\w+)\(\)\s*\{', ln)
        if start_line is None and m:
            start_line, name = i, m.group(1)
            continue
        if start_line is not None and re.match(r'^    \},?\s*$', ln):
            out[name] = (offs[start_line], offs[i + 1])
            start_line = None
    return out


def helper_spans(src):
    out = {}
    for m in re.finditer(r'^function (\w+)\(.*?^\}', src, re.M | re.S):
        out[m.group(1)] = (m.start(), m.end())
    return out


def const_names(events):
    return sorted({e['path'][0] for e in events if e['path'] and isinstance(e['path'][0], str)})


def note_context(src, pos):
    """True when the pair at `pos` sits in a replica note paragraph."""
    before = src[max(0, pos - 260):pos]
    at = max(before.rfind('lrn-note'), before.rfind('lrn-shellnote'))
    if at < 0:
        return False
    return '</p>' not in before[at:] and '</div>' not in before[at:]


#: The replica draws this pair as a tooltip / accessible name itself.
_TIP_CTX = re.compile(r'(?:title|aria-label)="\$\{\s*esc\(\s*(?:tx\(\s*)?$')


def practice_paths(text):
    """PRACTICE paths a piece of builder code reads, narrowed through aliases."""
    paths = set()
    aliases = {}
    for m in re.finditer(r'\b(?:const|let)\s+(\w+)\s*=\s*PRACTICE((?:\.\w+)+)', text):
        aliases[m.group(1)] = m.group(2).strip('.').split('.')
    for m in re.finditer(r'PRACTICE((?:\.\w+)+)', text):
        if re.search(r'\b(?:const|let)\s+\w+\s*=\s*$', text[max(0, m.start() - 40):m.start()]):
            continue    # an alias declaration: its uses below say which fields are read
        paths.add(tuple(m.group(1).strip('.').split('.')))
    for alias, base in aliases.items():
        uses = re.findall(r'(?<![\w.])%s\b(\.\w+)?' % re.escape(alias), text)
        fields = {u[1:] for u in uses if u}
        bare = sum(1 for u in uses if not u) - 1   # minus the declaration
        if bare > 0:
            paths.add(tuple(base))
        for f in fields:
            paths.add(tuple(base) + (f,))
    for m in re.finditer(r'ledgerHTML\(\s*"(\w+)"\s*\)', text):
        paths.add(('ledgers', m.group(1)))
    paths.discard(('ledgers',))
    return sorted(paths)


def replica_labels(screen_id, ctx):
    """Every bilingual pair one replica draws, classified."""
    src, events = ctx['screens_src'], ctx['screens_events']
    b0, b1 = ctx['builders'][screen_id]
    region = src[b0:b1]
    parts = [('builder', b0, b1)]
    for name, (h0, h1) in sorted(ctx['helpers'].items()):
        if re.search(r'\b%s\b' % re.escape(name), region):
            parts.append(('helper:' + name, h0, h1))
    text = '\n'.join(src[a:b] for _w, a, b in parts)
    raw_en = bool(re.search(r'esc\(\s*\w+\.en\s*\)', text))
    out = []

    def add(ev, origin, note=False, tip=False):
        out.append(dict(ev, origin=origin, note=note, tip=tip))

    for where, a, b in parts:
        for ev in events:
            if a <= ev['pos'] < b:
                tip = bool(_TIP_CTX.search(src[max(0, ev['pos'] - 80):ev['pos']]))
                add(ev, where, note_context(src, ev['pos']), tip)
    # top-level consts of screens.js the code names (KIND_LABEL, LEDGER_TABS, EN_DOWNLOAD…)
    spans = [(a, b) for _w, a, b in parts]
    for name in ctx['screen_consts']:
        if name in ('SCREENS',) or not re.search(r'\b%s\b' % re.escape(name), text):
            continue
        for ev in events:
            if ev['path'] and ev['path'][0] == name and not any(a <= ev['pos'] < b for a, b in spans):
                add(ev, 'const:' + name)
    # fixture blocks
    fx = ctx['fixture_events']
    known = ctx['fixture_paths']
    for path in practice_paths(text):
        p = ['PRACTICE'] + list(path)
        # `PRACTICE.importPipe.map(…)` reads importPipe: drop JS methods only.
        # A path with no pairs under it (numbers only) is NOT widened to its
        # parent — that would charge this screen with a sibling's labels.
        while len(p) > 2 and p[-1] in JS_MEMBERS:
            p = p[:-1]
        if tuple(p) not in known:
            continue
        for ev in fx:
            if ev['path'][:len(p)] == p:
                add(ev, 'fixture:' + '.'.join(str(x) for x in p))
    for kind in sorted(set(re.findall(r'statusChip\(\s*"(\w+)"', text))):
        for ev in fx:
            if ev['path'][:2] == ['STATUS_LABELS', kind]:
                add(ev, 'status:' + kind)
    if screen_id == 'hub_settings':
        for idx in ctx['menu_settings_idx']:
            for ev in fx:
                if ev['path'][:2] == ['MENU', idx]:
                    add(ev, 'fixture:MENU.settings')
    # de-duplicate (a pair reached twice) and resolve chrome
    seen = set()
    labels = []
    for ev in sorted(out, key=lambda e: (e['origin'], e['pos'])):
        if ev['kind'] == 'T':
            ch = ctx['chrome'].get(ev['en']) or {}
            if not ch.get('en'):
                continue
            ev = dict(ev, en=ch.get('en'), vi=ch.get('vi'), chrome=ev['en'])
        key = (ev['en'], ev['vi'])
        if key in seen:
            continue
        seen.add(key)
        ev['skip'] = classify(ev, ctx['demo_re'])
        ev['raw'] = raw_en and ev['kind'] == 'obj'
        labels.append(ev)
    return labels


def rail_labels(ctx):
    """The practice shell's rail, sections, hub tabs and Settings categories
    (fixture MENU), as one pseudo-replica."""
    seen, out = set(), []
    for ev in ctx['fixture_events']:
        if not ev['path'] or ev['path'][0] != 'MENU' or (ev['en'], ev['vi']) in seen:
            continue
        seen.add((ev['en'], ev['vi']))
        ev = dict(ev, origin='fixture:MENU', note=False, tip=False, raw=False)
        ev['skip'] = classify(ev, ctx['demo_re'])
        out.append(ev)
    return out


def classify(ev, demo_re):
    """None when the pair is a UI label to check, else the reason it is not."""
    en = ev['en'] or ''
    if en != en.strip() or en.rstrip().endswith('(') or en.lstrip().startswith(')'):
        return 'fragment'
    c = canon(en)
    if letters(c) < 2 or not c.replace('#', '').strip():
        return 'no words'
    if set(c.split()) <= STOP | {'#'}:
        return 'function word'     # "of", "of 6"
    if set(c.split()) <= MONTH_WORDS | {'#'}:
        return 'data'      # "July 2026", "vs June 2026", "Jul 2026 only", "Jan"
    if PRACTICE_ONLY_RE.search(en) or PRACTICE_ONLY_RE.search(ev.get('vi') or ''):
        return 'practice-only'
    if '›' in en:
        return 'practice-only'     # a breadcrumb naming where a screen lives
    if ev['origin'].startswith('helper:') and ev['origin'][7:] in PRACTICE_ONLY_HELPERS:
        return 'practice-only'
    if demo_re.search(en):
        return 'data'
    if ev['origin'].startswith(('fixture:', 'status:')):
        keys = [k for k in ev['path'] if isinstance(k, str)]
        last = keys[-1] if keys else ''
        if last in DATA_KEYS or DATA_PATH_KEYS.intersection(keys):
            return 'data'
        if ev['tuple_index'] not in (None, 0):
            return 'data'
    if ev.get('note') and len(c.split()) > 6:
        return 'note'
    return None


# ------------------------------------------------------------- real screen
class Corpus:
    """Canon text units of a set of files, searchable by whole words."""

    def __init__(self):
        self.units = {}     # canon -> dict(kinds=set, modules=set, wrapped=bool, hidden_all=bool)

    def add(self, text, kind, module, hidden=False, wrapped=0):
        c = canon(text)
        if not c or letters(c) < 1:
            return
        u = self.units.get(c)
        if u is None:
            u = self.units[c] = {'kinds': set(), 'modules': set(), 'wrapped': 0,
                                 'hidden_all': True, 'xml_visible': False}
        u['kinds'].add(kind)
        u['modules'].add(module)
        u['wrapped'] = max(u['wrapped'], wrapped)
        if not hidden:
            u['hidden_all'] = False
            if kind == 'xml':
                u['xml_visible'] = True

    def freeze(self):
        """Python strings match only when they are about the label's length
        (at most PY_SLACK words longer): a payload label is a whole string,
        while a label found inside a long Python message is an accident."""
        self.keys = sorted(self.units)
        self.blob = '|'.join(' %s ' % k for k in self.keys if self.units[k]['kinds'] - {'py'})
        by_len = {}
        for k in self.keys:
            if self.units[k]['kinds'] == {'py'}:
                by_len.setdefault(len(k.split()), []).append(' %s ' % k)
        self.py_blob = {n: '|'.join(v) for n, v in by_len.items()}
        return self

    def _ok(self, label, k):
        return bool(self.units[k]['kinds'] - {'py'}) or len(k.split()) <= len(label.split()) + PY_SLACK

    def has(self, label):
        w = ' %s ' % label
        if w in self.blob:
            return True
        n = len(label.split())
        return any(w in self.py_blob.get(i, '') for i in range(n, n + PY_SLACK + 1))

    def containing(self, label):
        want = ' %s ' % label
        return [k for k in self.keys if want in ' %s ' % k and self._ok(label, k)]

    def hidden_only(self, label):
        """In the XML, but only under an open-menu condition or in a tooltip,
        and never in the JS (a JS string may be drawn anywhere)."""
        hits = [self.units[k] for k in self.containing(label)]
        xml = [u for u in hits if 'xml' in u['kinds']]
        return bool(xml) and not any(u['xml_visible'] for u in xml) and not any(
            'js' in u['kinds'] for u in hits)


def module_of(rel):
    return rel.split('/', 1)[0]


def _resolve_entities(text):
    def rep(m):
        if m.group(1) in ('amp', 'lt', 'gt', 'quot', 'apos'):
            return m.group(0)
        if m.group(1).startswith('#'):
            return m.group(0)
        val = html.unescape(m.group(0))
        return val if val != m.group(0) else ' '
    return re.sub(r'&(#?\w+);', rep, text)


_QUOTED = re.compile(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"")


def xml_units(rel, corpus, kind='xml'):
    src = read(rel)
    if src is None:
        return False
    mod = module_of(rel)
    try:
        root = ET.fromstring(_resolve_entities(src).encode('utf-8'))
    except ET.ParseError:
        # fall back to tag-split text
        for piece in re.split(r'<[^>]+>', src):
            corpus.add(piece, kind, mod)
        return True

    def flatten(el):
        out = [el.text or '']
        for ch in el:
            if ch.get('t-esc') is not None or ch.get('t-out') is not None:
                out.append(' # ')
            else:
                out.append(flatten(ch))
            out.append(ch.tail or '')
        return ''.join(out)

    def walk(el, hidden):
        cond = el.get('t-if') or el.get('t-elif')
        h = hidden or bool(cond and MENU_COND_RE.search(cond))
        if el.text and el.text.strip():
            corpus.add(el.text, kind, mod, h)
        for name, val in sorted(el.attrib.items()):
            # a tooltip is read only on hover: "hidden" for the hidden-only check
            tip = h or bool(TOOLTIP_ATTR_RE.search(name))
            if name in LITERAL_ATTRS:
                corpus.add(val, kind, mod, tip)
            elif name.startswith('t-attf-'):
                corpus.add(val, kind, mod, tip)
            elif name.startswith('t-') and name not in SKIP_T_ATTRS:
                for a, b in _QUOTED.findall(val):
                    corpus.add(a or b, kind, mod, tip)
        has_text = bool((el.text or '').strip()) or any((c.tail or '').strip() for c in el)
        if has_text:
            flat = flatten(el)
            if len(' '.join(flat.split())) <= 240:
                corpus.add(flat, kind, mod, h)
        for ch in el:
            walk(ch, h)
            if ch.tail and ch.tail.strip():
                corpus.add(ch.tail, kind, mod, h)
    walk(root, False)
    return True


def js_units(rel, corpus, kind='js'):
    src = read(rel)
    if src is None:
        return False
    mod = module_of(rel)
    _ev, strings = scan_js(src)
    for s in strings:
        corpus.add(s, kind, mod)
        if '<' in s and '>' in s:
            for piece in re.split(r'<[^>]+>', s):
                corpus.add(piece, kind, mod)
    return True


def _fname(call):
    f = call.func
    return f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else '')


def _tuple_labels(node, out):
    """Second element of every 2-tuple in a list/tuple literal (selection labels)."""
    if isinstance(node, (ast.List, ast.Tuple)):
        for el in node.elts:
            if isinstance(el, ast.Tuple) and len(el.elts) == 2:
                out.add(id(el.elts[1]))


def py_module_units(files, corpus):
    """String constants of a module's Python. `wrapped`: 2 = inside `_()` /
    `_lt()`; 1 = a selection label (a 2-tuple of a list handed to
    `fields.Selection`, directly or by a constant's name) — the ORM translates
    it when it is read as a field, but the same list shipped in a payload is
    English, so a Vietnamese verdict on it is marked unsure; 0 = bare."""
    trees = []
    for rel in files:
        src = read(rel)
        if src is None:
            continue
        try:
            trees.append((module_of(rel), ast.parse(src)))
        except SyntaxError:
            continue
    sel_names, level = set(), {}
    for _mod, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fname = _fname(node)
                if fname in ('_', '_lt'):
                    for a in node.args[:1]:
                        level[id(a)] = 2
                elif fname == 'Selection':
                    args = list(node.args[:1]) + [k.value for k in node.keywords if k.arg == 'selection']
                    for a in args:
                        if isinstance(a, ast.Name):
                            sel_names.add(a.id)
                        sel = set()
                        _tuple_labels(a, sel)
                        for i in sel:
                            level.setdefault(i, 1)
    for _mod, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in sel_names
                                                    for t in node.targets):
                sel = set()
                _tuple_labels(node.value, sel)
                for i in sel:
                    level.setdefault(i, 1)
    docs = set()    # docstrings and bare string statements are not labels
    for _mod, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                docs.add(id(node.value))
    for mod, tree in trees:
        for node in ast.walk(tree):
            if id(node) in docs:
                continue
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                corpus.add(node.value, 'py', mod, wrapped=level.get(id(node), 0))
            elif isinstance(node, ast.JoinedStr):
                txt = ''.join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str)
                              else ' # ' for v in node.values)
                corpus.add(txt, 'py', mod)


# ---- repo indexes (built once)
def walk_files(top, exts):
    out = []
    for dp, dns, fns in os.walk(rel_path(top)):
        dns[:] = sorted(d for d in dns if d not in ('__pycache__', 'node_modules', 'lib', 'tests'))
        for fn in sorted(fns):
            if fn.endswith(exts):
                out.append(os.path.relpath(os.path.join(dp, fn), REPO))
    return out


def our_modules():
    out = []
    for d in sorted(os.listdir(REPO)):
        if d.startswith(('pb_', 'biz_')) and os.path.isfile(rel_path(d, '__manifest__.py')):
            out.append(d)
    return out


def build_indexes():
    tname_file = {}       # t-name -> xml rel
    tpl_js = {}           # t-name -> [js rel] (components whose template is it)
    class_tpl = {}        # Component class name -> t-name
    xml_tnames = {}       # xml rel -> [t-names]
    for mod in our_modules():
        if mod == 'pb_learn':
            continue
        for rel in walk_files(os.path.join(mod, 'static', 'src'), ('.xml',)):
            names = re.findall(r't-name="([\w.]+)"', read(rel) or '')
            xml_tnames[rel] = names
            for nm in names:
                tname_file.setdefault(nm, rel)
        for rel in walk_files(os.path.join(mod, 'static', 'src'), ('.js',)):
            src = read(rel) or ''
            for m in re.finditer(r'class\s+(\w+)\s+extends\s+[\w.]+\s*\{(.{0,1500}?)static\s+template\s*=\s*["\']([\w.]+)["\']',
                                 src, re.S):
                class_tpl.setdefault(m.group(1), m.group(3))
                tpl_js.setdefault(m.group(3), []).append(rel)
            for m in re.finditer(r'\btemplate\s*[=:]\s*["\']([\w.]+)["\']', src):
                lst = tpl_js.setdefault(m.group(1), [])
                if rel not in lst:
                    lst.append(rel)
    return {'tname_file': tname_file, 'tpl_js': tpl_js, 'class_tpl': class_tpl,
            'xml_tnames': xml_tnames}


def expand_files(files, idx, depth=2):
    """The mapped files plus the JS that renders them, their t-call targets and
    sub-component templates (and those components' JS)."""
    xmls = [f for f in files if f.endswith('.xml')]
    jss = [f for f in files if f.endswith('.js')]
    seen_x, seen_j = set(xmls), set(jss)
    frontier = list(xmls)
    for _ in range(depth + 1):
        nxt = []
        for x in frontier:
            for nm in idx['xml_tnames'].get(x, ()):
                for j in idx['tpl_js'].get(nm, ()):
                    if j not in seen_j:
                        seen_j.add(j)
            src = read(x) or ''
            refs = set(re.findall(r't-call="([\w.]+)"', src))
            for comp in set(re.findall(r'<([A-Z]\w+)[\s/>]', src)):
                if comp in idx['class_tpl']:
                    refs.add(idx['class_tpl'][comp])
            for r in refs:
                f = idx['tname_file'].get(r)
                if f and f not in seen_x:
                    seen_x.add(f)
                    nxt.append(f)
                for j in idx['tpl_js'].get(r, ()):
                    seen_j.add(j)
        frontier = nxt
        if not frontier:
            break
    return sorted(seen_x), sorted(seen_j)


# ---- translations
def build_terms():
    """{module: {canon msgid: canon msgstr}} from every live vi_VN.po in the repo."""
    terms = {}
    pots = {}
    for d in sorted(os.listdir(REPO)):
        po = read('%s/i18n/vi_VN.po' % d)
        if po is None:
            continue
        pot = read('%s/i18n/%s.pot' % (d, d))
        live = gt.live_po(po, pot)
        terms[d] = {}
        for k, v in sorted(live.items()):
            ck = canon(k)
            if ck and ck not in terms[d]:
                terms[d][ck] = canon(v)
        if pot:
            pots[d] = sorted({canon(m) for m in gt._msgids(pot) if m})
    return terms, pots


def vi_on_screen(label, corpus, screen_mods, terms, py_only):
    """(kind, [canon vi], unsure) — what the real screen shows in Vietnamese
    for `label`. kind: 'exact' | 'contained' | 'english'.

    XML/JS text: the screen modules' own .po decides when it has the term
    (as `guide_truth.vi_on_screen` does); otherwise any module's translation
    is accepted (the web client merges terms; which one wins is load order).
    Python-only text: translated only when wrapped (see py_module_units)."""
    if py_only:
        units = [k for k in corpus.containing(label) if 'py' in corpus.units[k]['kinds']]
        wrapped = [k for k in units if corpus.units[k]['wrapped']]
        if not wrapped:
            return 'english', [], False
        unsure = all(corpus.units[k]['wrapped'] == 1 for k in wrapped)
        mods = sorted({m for k in wrapped for m in corpus.units[k]['modules']})
        hits = sorted({terms.get(m, {}).get(k) for m in mods for k in wrapped} - {None})
        if not hits:
            return 'english', [], unsure
        return ('exact' if label in wrapped else 'contained'), hits, unsure
    own = sorted({terms[m][label] for m in screen_mods if label in terms.get(m, {})})
    if own:
        return 'exact', own, False
    # Not in the screen's own modules: another module's translation may or may
    # not reach this screen (module-scoped lookup vs merged terms) — unsure.
    anywhere = sorted({t[label] for _m, t in sorted(terms.items()) if label in t})
    if anywhere:
        return 'exact', anywhere, True
    units = [k for k in corpus.containing(label) if corpus.units[k]['kinds'] & {'xml', 'js'}]
    hits = sorted({terms[m][k] for m in screen_mods for k in units if k in terms.get(m, {})})
    if not hits:
        hits = sorted({t[k] for _m, t in sorted(terms.items()) for k in units if k in t})
    if hits:
        return 'contained', hits, True
    return 'english', [], False


# --------------------------------------------------------------- the report
def check_screen(screen_id, ctx):
    files = list(MAPPING.get(screen_id) or [])
    mapped = list(files)
    if screen_id in REGISTERED_FILES:
        pat = re.compile(REGISTERED_FILES[screen_id])
        for mod in our_modules():
            if mod == 'pb_learn':
                continue
            for f in walk_files(os.path.join(mod, 'static', 'src'), ('.js',)):
                if f not in files and pat.search(read(f) or ''):
                    files.append(f)
    if screen_id in REGISTERED_DATA:
        pat = re.compile(REGISTERED_DATA[screen_id])
        for mod in our_modules():
            for f in walk_files(os.path.join(mod, 'data'), ('.xml',)):
                if f not in files and pat.search(f):
                    files.append(f)
    row = {'replica': screen_id, 'templates': mapped,
           'registered_files': sorted(set(files) - set(mapped)), 'missing_templates': [],
           'labels_checked': 0, 'drift': [], 'vi_drift': [], 'elsewhere_in_module': [],
           'notes_not_on_screen': [], 'real_missing_from_replica': [], 'uses_python_labels': [],
           'skipped': {}}
    missing = [f for f in files if read(f) is None]
    row['missing_templates'] = missing
    if not files or len(missing) == len(files):
        row['status'] = 'real screen not found'
        return row
    row['status'] = 'ok'
    xmls, jss = expand_files([f for f in files if f not in missing], ctx['idx'])
    row['pulled_in'] = sorted(set(xmls + jss) - set(files))
    screen = Corpus()
    for f in xmls:
        xml_units(f, screen)
    for f in jss:
        js_units(f, screen)
    screen_mods = sorted({module_of(f) for f in files if f not in missing})
    for m in sorted(set(screen_mods) | set(RPC_MODULES.get(screen_id, ()))):
        py_module_units([f for f in walk_files(m, ('.py',))
                         if os.path.basename(f) not in ('__manifest__.py', 'learn_manifest.py')
                         and '/migrations/' not in f], screen)
    screen.freeze()
    # module level: every other static file of the screen modules, plus the .pot msgids
    module = Corpus()
    for m in screen_mods:
        for f in walk_files(os.path.join(m, 'static', 'src'), ('.xml',)):
            if f not in xmls:
                xml_units(f, module)
        for f in walk_files(os.path.join(m, 'static', 'src'), ('.js',)):
            if f not in jss:
                js_units(f, module)
        for f in walk_files(os.path.join(m, 'views'), ('.xml',)):
            xml_units(f, module, 'view')
        for k in ctx['pots'].get(m, ()):
            module.add(k, 'pot', m)
    module.freeze()

    labels = rail_labels(ctx) if screen_id == RAIL else replica_labels(screen_id, ctx)
    replica_canon = set()
    for lb in labels:
        replica_canon.add(canon(lb['en']))
        if lb.get('vi'):
            replica_canon.add(canon(lb['vi']))
    for lb in labels:
        if lb['skip']:
            row['skipped'][lb['skip']] = row['skipped'].get(lb['skip'], 0) + 1
            if lb['skip'] == 'note':
                ce = canon(lb['en'])
                if not screen.has(ce) and not module.has(ce):
                    row['notes_not_on_screen'].append(lb['en'])
            continue
        texts = [lb['en']] + ([lb['vi']] if lb['raw'] and lb.get('vi') else [])
        for text in texts:
            row['labels_checked'] += 1
            ce = canon(text)
            entry = {'en': text, 'vi': None if lb['raw'] else lb.get('vi'), 'origin': lb['origin']}
            if screen.has(ce):
                kinds = set()
                for k in screen.containing(ce):
                    kinds |= screen.units[k]['kinds']
                py_only = kinds == {'py'}
                if py_only:
                    row['uses_python_labels'].append(text)
                # a one-word label is too common to judge where it sits; a pair the
                # copy itself draws as a tooltip is a tooltip on both sides
                if len(ce.split()) >= 2 and not lb.get('tip') and screen.hidden_only(ce):
                    row['drift'].append(dict(entry, kind='hidden-only'))
                    continue
                if lb['raw'] or not lb.get('vi'):
                    continue
                vkind, vis, unsure = vi_on_screen(ce, screen, screen_mods, ctx['terms'], py_only)
                cv = canon(lb['vi'])
                same_as_en = cv == ce
                if vkind == 'english':
                    if not same_as_en:
                        row['vi_drift'].append(dict(entry, kind='vi-screen-english', screen_vi=None,
                                                    unsure=unsure))
                elif vkind == 'exact':
                    if cv not in vis:
                        row['vi_drift'].append(dict(
                            entry, kind='vi-replica-english' if same_as_en else 'vi-differs',
                            screen_vi=vis, unsure=unsure))
                else:   # contained in a longer text
                    if not any((' %s ' % cv) in (' %s ' % v) for v in vis):
                        row['vi_drift'].append(dict(
                            entry, kind='vi-replica-english' if same_as_en else 'vi-differs',
                            screen_vi=vis, unsure=True))
            elif module.has(ce):
                row['elsewhere_in_module'].append(text)
            else:
                row['drift'].append(dict(entry, kind='gone'))
    # secondary: short visible XML texts of the mapped files the replica never says
    real = Corpus()
    for f in files:
        if f.endswith('.xml') and f not in missing:
            xml_units(f, real)
    real.freeze()
    rblob = '|'.join(' %s ' % c for c in sorted(replica_canon))
    for k in real.keys:
        u = real.units[k]
        words = k.split()
        if u['hidden_all'] or '#' in k or not 1 <= len(words) <= 4 or letters(k) < 3:
            continue
        if len(words) == 1 and k in STOP:
            continue
        if (' %s ' % k) not in rblob:
            row['real_missing_from_replica'].append(k)
    for key in ('drift', 'vi_drift'):
        row[key] = sorted(row[key], key=lambda d: (d['kind'], d['en'], d.get('vi') or ''))
    for key in ('elsewhere_in_module', 'notes_not_on_screen', 'real_missing_from_replica',
                'uses_python_labels'):
        row[key] = sorted(set(row[key]))
    row['skipped'] = dict(sorted(row['skipped'].items()))
    return row


def build_context():
    screens_src = read(SCREENS_JS)
    fixture_src = read(FIXTURE_JS)
    s_events, _s = scan_js(screens_src)
    f_events, _f = scan_js(fixture_src)
    for ev in s_events + f_events:
        ev['path'] = [x for x in ev['path']]
    fixture_paths = set()
    for ev in f_events:
        p = ev['path']
        for i in range(1, len(p) + 1):
            fixture_paths.add(tuple(p[:i]))
    # MENU index of the Settings hub (the one whose src block says key: "settings")
    menu_at = fixture_src.find('const MENU = [')
    menu_settings_idx = []
    for i, blk in enumerate(re.split(r'\n  \},\n  \{', fixture_src[menu_at:fixture_src.find('\n];', menu_at)])):
        if re.search(r'key: "settings"', blk.split('lenses')[0]):
            menu_settings_idx.append(i)
    try:
        chrome = json.loads(read(CONTENT_JSON) or '{}').get('chrome') or {}
    except ValueError:
        chrome = {}
    builders = builder_spans(screens_src)
    for k, (a, b) in sorted(builders.items()):
        # same region rule as the gate's replica half
        if gt.replica_region(screens_src, k) != screens_src[a:b].rstrip('\n'):
            sys.stderr.write('warning: builder %s region differs from guide_truth.replica_region\n' % k)
    terms, pots = build_terms()
    # demo people: plain-string names in the fixture ("Nguyễn Thị Mai", "Lê Thu Trang")
    people = set()
    for m in re.finditer(r'\b(?:name|who|by|to|from|approver)\s*:\s*"([^"]{3,40})"', fixture_src):
        words = m.group(1).split()
        if 2 <= len(words) <= 4 and all(w[:1].isupper() for w in words):
            people.add(m.group(1))
    demo_re = re.compile('|'.join(re.escape(w) for w in sorted(set(DEMO_WORDS) | people,
                                                                  key=lambda s: (-len(s), s))))
    return {
        'demo_re': demo_re,
        'screens_src': screens_src, 'screens_events': s_events,
        'builders': builders, 'helpers': helper_spans(screens_src),
        'screen_consts': const_names(s_events),
        'fixture_events': f_events, 'fixture_paths': fixture_paths,
        'menu_settings_idx': menu_settings_idx,
        'chrome': chrome, 'terms': terms, 'pots': pots, 'idx': build_indexes(),
    }


def fmt_drift(row):
    parts = []
    for d in row['drift']:
        tag = '' if d['kind'] == 'gone' else ' (hidden-only)'
        parts.append('"%s"%s' % (d['en'], tag))
    return '; '.join(parts) or '—'


def sure(row):
    return [d for d in row['vi_drift'] if not d.get('unsure')]


def fmt_vi(row):
    parts = []
    for d in sorted(row['vi_drift'], key=lambda d: (bool(d.get('unsure')), d['kind'], d['en'])):
        if d['kind'] == 'vi-screen-english':
            parts.append('"%s": copy "%s", screen English%s' % (d['en'], d['vi'],
                                                                ' (?)' if d.get('unsure') else ''))
        else:
            parts.append('"%s": copy "%s", screen "%s"%s' % (
                d['en'], d['vi'], ' / '.join(d.get('screen_vi') or []), ' (?)' if d.get('unsure') else ''))
    return '; '.join(parts) or '—'


def md_cell(s):
    return str(s).replace('|', '\\|').replace('\n', ' ')


def render(rows):
    total = len(rows)
    with_drift = [r for r in rows if r['drift'] or sure(r)]
    not_found = [r for r in rows if r['status'] != 'ok']
    unsure_n = sum(len(r['vi_drift']) - len(sure(r)) for r in rows)
    out = ['# VIFIX P1 — replica drift report', '',
           'Replicas: %d · with drift: %d · drifted labels: %d English + %d Vietnamese '
           '(+%d Vietnamese marked (?), not counted) · real screen not found: %d (%s)' % (
               total, len(with_drift), sum(len(r['drift']) for r in rows),
               sum(len(sure(r)) for r in rows), unsure_n, len(not_found),
               ', '.join(r['replica'] for r in not_found) or 'none'),
           '',
           '| Replica | Real template(s) | Checked | Drifted (EN+VI) | Drifted labels (EN) | Vietnamese drift | '
           'Elsewhere in module | Real labels not in copy |',
           '|---|---|---|---|---|---|---|---|']
    order = sorted(rows, key=lambda r: (-(len(r['drift']) + len(sure(r))), r['replica']))
    for r in order:
        tpl = ', '.join(t.split('/')[0] + ':' + os.path.basename(t) for t in r['templates'])
        if r.get('registered_files'):
            tpl += ' + %d registering files' % len(r['registered_files'])
        if r['status'] != 'ok':
            tpl = 'real screen not found (%s)' % tpl
        py = ' (RPC labels: %d)' % len(r['uses_python_labels']) if r.get('uses_python_labels') else ''
        out.append('| %s | %s | %d | %d+%d | %s | %s | %d | %d |' % (
            r['replica'], md_cell(tpl + py), r['labels_checked'], len(r['drift']), len(sure(r)),
            md_cell(fmt_drift(r)), md_cell(fmt_vi(r)), len(r['elsewhere_in_module']),
            len(r['real_missing_from_replica'])))
    out.append('')
    out.append('Legend: "(hidden-only)" = on the real screen only after a click opens a menu, or only '
               'as a hover tooltip, while the copy draws it as a standing label. "(?)" = '
               'Vietnamese verdict not certain (the label sits inside a longer product text, or it is a '
               'Python selection label that the system translates only when it is read as a field); '
               'listed, not counted. "RPC labels" = labels found only in the module\'s Python. '
               '"Elsewhere in module" and "Real labels not in copy" are secondary (see the JSON).')
    return '\n'.join(out) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--json', help='also write the full report as JSON to this path')
    args = ap.parse_args(argv)
    ctx = build_context()
    ids = sorted(ctx['builders'])
    rows = [check_screen(i, ctx) for i in ids + [RAIL]]
    unmapped = sorted(set(ids) - set(MAPPING))
    sys.stdout.write(render(rows))
    if unmapped:
        sys.stdout.write('\nReplicas with no mapping entry: %s\n' % ', '.join(unmapped))
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump({'replicas': rows, 'unmapped': unmapped}, fh, ensure_ascii=False, indent=1,
                      sort_keys=True)
            fh.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
