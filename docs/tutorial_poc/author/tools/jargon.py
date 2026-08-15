#!/usr/bin/env python3
"""The jargon gate and the readability report (LEARNOS Phase 2).

    python3 docs/tutorial_poc/author/tools/jargon.py            # report + exit code
    python3 docs/tutorial_poc/author/tools/jargon.py --warnings # also list every 17-28 word sentence
    python3 docs/tutorial_poc/author/tools/jargon.py --terms    # what the hovercard will match

`gen_learn_data.py` imports `lint()` and refuses to write when it fails, so
`--check` covers this too. Running the file directly is the authoring loop:
rewrite a section, run it, see what is still too long.

WHY THIS EXISTS
---------------
The product promise is that somebody who has never run payroll can learn it
from the app. That promise is made or broken one sentence at a time, and prose
drifts back towards the register its author already speaks. Three gates:

  glossary   A technical term a beginner cannot be assumed to know. It must
             have a GLOSSARY entry, and the entry must MATCH the spelling used
             in the prose, because the same table is what the hovercard wraps.
             A term with a definition nobody can reach is a term with no
             definition.
  banned     Words that are never the clearest choice available. Failing is the
             point: a warning about "utilize" is a warning everybody scrolls
             past.
  allow      An explicit exception, with the reason written down. Product
             names, legal terms of art, and the handful of words whose plain
             synonym would be less accurate rather than more.

Plus the sentence-length rule: over 28 words (English) fails, 17-28 warns.
Vietnamese is measured and reported but NOT gated on length — Vietnamese words
are shorter and mostly monosyllabic, so an English word count is the wrong
ruler for it. The VI register is held by review, not by this tool, and the
ledger says so.

WHAT IS MEASURED
----------------
Every learner-facing prose leaf in the authoring source: chrome, glossary,
stations, lessons, missions, scenarios, screens, intents, columns and the morph
captions. Not: match phrases (typed, not read), fixture values, keys, anchors.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
AUTHOR = os.path.dirname(HERE)

# The word count at which an English sentence stops being one idea.
HARD_WORDS = 28
WARN_WORDS = 17

# ============================================================================
# THE CURATED LIST
# ============================================================================
# Seeded from the content itself (every word of length >= 4 used four times or
# more, read by hand) and then decided one term at a time. The KEY is the
# lowercase phrase as it is written in English prose; the value is
# (state, detail).
#
#   ('glossary', '<glossary key>')  the entry that must exist AND must match
#                                   this spelling, so the hovercard can wrap it
#   ('banned',   '<what to write instead>')
#   ('allow',    '<why this one is fine unexplained>')
#
# Longest match wins at render time, so "insurance base" and "base" can both be
# listed without the shorter one stealing the longer one's text.
JARGON = {
    # -- statutory Vietnam -------------------------------------------------
    'bhxh': ('glossary', 'bhxh'),
    'social insurance': ('glossary', 'bhxh'),
    'bhyt': ('glossary', 'bhyt'),
    'health insurance': ('glossary', 'bhyt'),
    'bhtn': ('glossary', 'bhtn'),
    'unemployment insurance': ('glossary', 'bhtn'),
    'thuế tncn': ('glossary', 'pit'),
    'personal income tax': ('glossary', 'pit'),
    'pit': ('glossary', 'pit'),
    'taxable income': ('glossary', 'taxableIncome'),
    'family deduction': ('glossary', 'familyDeduction'),
    'dependant': ('glossary', 'familyDeduction'),
    'insurance base': ('glossary', 'insuranceBase'),
    'registered base': ('glossary', 'insuranceBase'),
    'insurance ceiling': ('glossary', 'ceiling'),
    'ceiling': ('glossary', 'ceiling'),
    'contribution': ('glossary', 'contribution'),
    'statutory': ('glossary', 'statutory'),
    'decree': ('glossary', 'decree'),
    'insurance policy': ('glossary', 'policy'),
    'effective date': ('glossary', 'effectiveDate'),

    # -- the pay run and its parts ----------------------------------------
    'pay run': ('glossary', 'payrun'),
    'payslip': ('glossary', 'payslip'),
    'gross': ('glossary', 'gross'),
    'net': ('glossary', 'net'),
    'draft': ('glossary', 'draft'),
    'period': ('glossary', 'period'),
    'cycle': ('glossary', 'cycle'),
    'division': ('glossary', 'division'),
    'proration': ('glossary', 'proration'),
    'prorated': ('glossary', 'proration'),
    'retro': ('glossary', 'retro'),
    'full and final': ('glossary', 'fullFinal'),
    'leaver': ('glossary', 'leaver'),
    'joiner': ('glossary', 'joiner'),
    'eligible': ('glossary', 'eligible'),
    'recompute': ('glossary', 'recompute'),
    'bank file': ('glossary', 'bankFile'),
    'journal entry': ('glossary', 'journalEntry'),

    # -- approval ----------------------------------------------------------
    'gate': ('glossary', 'gate'),
    'tier': ('glossary', 'tier'),
    'approval chain': ('glossary', 'approvalChain'),
    'payroll officer': ('glossary', 'payrollOfficer'),
    'rejection': ('glossary', 'rejection'),
    'flag': ('glossary', 'flag'),
    'need review': ('glossary', 'flag'),

    # -- setup -------------------------------------------------------------
    'formula configuration': ('glossary', 'formulaConfig'),
    'configuration code': ('glossary', 'configCode'),
    'component': ('glossary', 'component'),
    'salary structure': ('glossary', 'salaryStructure'),
    'allowance': ('glossary', 'allowance'),
    'deduction': ('glossary', 'deduction'),
    'earning': ('glossary', 'earning'),
    'connector': ('glossary', 'connector'),
    'sync': ('glossary', 'sync'),

    # -- import ------------------------------------------------------------
    'import batch': ('glossary', 'importBatch'),
    'commit': ('glossary', 'commitImport'),
    'staging': ('glossary', 'staging'),
    'confidence score': ('glossary', 'confidenceScore'),
    'mapping': ('glossary', 'mapping'),
    'attendance': ('glossary', 'attendance'),
    'overtime': ('glossary', 'overtime'),

    # -- people ------------------------------------------------------------
    'contract': ('glossary', 'contract'),
    'headcount': ('glossary', 'headcount'),
    'wage bill': ('glossary', 'wageBill'),
    'payroll-ready': ('glossary', 'payrollReady'),
    # NOT bare 'group': "a group of employees" is a DIVISION, and a card
    # defining permissions over that phrase is the exact failure the alias
    # gate exists for. The plural is always the permission sense here.
    'groups': ('glossary', 'group'),

    # -- analytics ---------------------------------------------------------
    'roll-up': ('glossary', 'rollUp'),
    'snapshot': ('glossary', 'snapshot'),
    'variance': ('glossary', 'variance'),
    'waterfall': ('glossary', 'waterfall'),
    'drill': ('glossary', 'drill'),
    'cost per head': ('glossary', 'costPerHead'),
    'kpi': ('glossary', 'kpi'),
    'filing': ('glossary', 'filing'),
    'reconcile': ('glossary', 'reconcile'),

    # -- banned ------------------------------------------------------------
    # None of these is ever the clearest word available on a payroll screen.
    'remuneration': ('banned', 'write "pay"'),
    'utilize': ('banned', 'write "use"'),
    'utilise': ('banned', 'write "use"'),
    'aforementioned': ('banned', 'name the thing again, or write "that"'),
    'commence': ('banned', 'write "start"'),
    'terminate': ('banned', 'write "end", or "leaves the company" about a person'),
    'facilitate': ('banned', 'write "let" or "help"'),
    'leverage': ('banned', 'write "use"'),
    'ascertain': ('banned', 'write "find out" or "check"'),
    'endeavour': ('banned', 'write "try"'),
    'thereof': ('banned', 'write "of it"'),
    'herein': ('banned', 'write "here"'),
    'pursuant to': ('banned', 'write "under" or name the decree'),
    'in respect of': ('banned', 'write "for" or "about"'),
    'prior to': ('banned', 'write "before"'),
    'subsequent to': ('banned', 'write "after"'),
    'in order to': ('banned', 'write "to"'),
    'requisite': ('banned', 'write "needed"'),
    'salient': ('banned', 'write "important", or cut the word'),
    'granular': ('banned', 'say what detail, e.g. "employee by employee"'),
    'holistic': ('banned', 'say what it covers'),
    'robust': ('banned', 'say what it survives'),
    'seamless': ('banned', 'say what does not have to be done by hand'),

    # -- allowed, with the reason ------------------------------------------
    'payobook': ('allow', 'the product name'),
    'excel': ('allow', 'a household name, and the shape of the formula language'),
    'odoo': ('allow', 'the platform name, met on legacy screens'),
    'explorer': ('allow', 'a screen name pb_sidebar ships untranslated'),
    'vietnam': ('allow', 'a country'),
    'employee': ('allow', 'an ordinary word, and the one the product uses'),
    'salary': ('allow', 'an ordinary word'),
    'wage': ('allow', 'an ordinary word; the technical sense is "wage bill"'),
    'approval': ('allow', 'an ordinary word; the technical parts are gate and tier'),
    'compute': ('allow', 'the button says Compute, so the learner must meet the word'),
    'company': ('allow', 'an ordinary word'),
    'timesheet': ('allow', 'an ordinary word, and defined inline where it matters'),
    'audit': ('allow', 'an ordinary word in a payroll office'),
    'anomaly': ('allow', 'lesson chrome, explained by the card it heads'),
    'capstone': ('allow', 'learning chrome, explained where it is offered'),
}


# ============================================================================
# THE ALIAS DIRECTION OF THE GATE  (added in the Phase 2 review round)
# ============================================================================
# The first version of this file only checked term -> entry: "every jargon term
# I demand has a definition". That is half a gate. The other half is
# alias -> text: "every phrase the hovercard matches lands on the thing the
# entry defines". It does not, by default, and the review found six English
# and six Vietnamese aliases that wrapped the wrong words —
# `run` inside "the wizard runs", `kỳ` inside "bất kỳ", `cấp` inside
# "cấp quản lý". A card that defines a pay run over the word "runs" in
# "a formula that runs" teaches a beginner something false, in the surface
# built to stop exactly that.
#
# TWO RULES, and the second is the one that catches a regression.

# RULE 1: a single-word phrase in the match table is FORBIDDEN unless it is
# here, with a reason. Single words are where the damage is: a two-word phrase
# is almost always the term itself, and a one-word phrase is a bet that the
# word is never used in its ordinary sense anywhere in 1,500 leaves.
#
# The test is applied to the TERM as well as to the aliases. A single-word
# `term` is exactly as dangerous as a single-word alias, and exempting it
# because of where it is declared would be exempting the common case.
BARE_ALIASES = {
    # -- Vietnamese. Deliberately short: Vietnamese is written in syllables,
    # so almost every "word" here is a fragment of a longer compound, and a
    # bare syllable is a wrap in the wrong place waiting to happen.
    'bhxh': 'an abbreviation, never a fragment of another Vietnamese word',
    'bhyt': 'an abbreviation, never a fragment of another Vietnamese word',
    'bhtn': 'an abbreviation, never a fragment of another Vietnamese word',

    # -- English abbreviations and coined terms: no ordinary-English sense.
    'pit': 'an abbreviation; the boundary rule keeps it out of "pity"',
    'kpi': 'an abbreviation',
    'kpis': 'an abbreviation',
    'ot': 'an abbreviation used on timesheets',

    # -- English payroll nouns with no everyday collision in this corpus.
    'payslip': 'a payroll noun; no other sense exists',
    'payslips': 'plural of the above',
    'slip': 'used only of a payslip in this corpus',
    'slips': 'plural of the above',
    'gross': 'a payroll noun here; the adjective sense is never used',
    'net': 'a payroll noun; the boundary rule keeps it out of "network"',
    'proration': 'a payroll noun',
    'prorate': 'a payroll verb',
    'prorated': 'a payroll participle',
    'retro': 'a payroll noun in this corpus, never the style adjective',
    'backdated': 'used only of a retro line',
    'joiner': 'a payroll noun',
    'joiners': 'plural of the above',
    'leaver': 'a payroll noun',
    'leavers': 'plural of the above',
    'settlement': 'used only of a full-and-final settlement here',
    'headcount': 'a payroll noun',
    'overtime': 'a payroll noun',
    'attendance': 'a payroll noun',
    'contribution': 'a payroll noun',
    'contributions': 'plural of the above',
    'statutory': 'a payroll adjective; there is no ordinary sense in this corpus',
    'decree': 'a legal noun',
    'decrees': 'plural of the above',
    'circular': 'the legal document; the adjective sense is never used here',
    'ceiling': 'the contribution cap; the architectural sense is never used',
    'ceilings': 'plural of the above',
    'dependant': 'a tax noun',
    'dependants': 'plural of the above',
    'relief': 'a tax noun in this corpus',
    'taxable': 'a tax adjective',
    'deduction': 'a payroll noun',
    'deductions': 'plural of the above',
    'earning': 'a payslip line kind',
    'earnings': 'plural of the above',
    'allowance': 'a payslip line kind',
    'allowances': 'plural of the above',

    # -- product objects. Each is a thing on a Payobook screen.
    'payrun': 'the object name, hyphen-free spelling',
    'division': 'the product object',
    'divisions': 'plural of the above',
    'period': 'the product field; "pay period" is listed too and wins',
    'periods': 'plural of the above',
    'cycle': 'the product field (mid/end)',
    'draft': 'the product state',
    'drafts': 'plural of the above',
    'eligible': 'the product word on the wizard summary',
    'eligibility': 'the same word as a noun',
    'recompute': 'the product action',
    'recomputed': 'participle of the above',
    'recomputing': 'gerund of the above',
    'recalculate': 'the synonym a learner reaches for',
    'commit': 'the import button label',
    'commits': 'inflection of the above',
    'committed': 'inflection of the above',
    'committing': 'inflection of the above',
    'uncommitted': 'inflection of the above',
    'staging': 'the import holding area',
    'staged': 'participle of the above',
    'confidence': 'short for the confidence score, only used that way here',
    'score': 'only ever the confidence score in this corpus',
    'mapping': 'the import step',
    'mapped': 'participle of the above',
    'mappings': 'plural of the above',
    'component': 'the formula object',
    'components': 'plural of the above',
    'configuration': 'the formula object',
    'configurations': 'plural of the above',
    'config': 'the short spelling used on screen',
    'configs': 'plural of the above',
    'rulebook': 'the plain-language name this content gives a configuration',
    'connector': 'the integrations object',
    'connectors': 'plural of the above',
    'integration': 'the same object under its screen name',
    'integrations': 'the sidebar label',
    'sync': 'the integrations action',
    'syncs': 'inflection of the above',
    'synced': 'inflection of the above',
    'syncing': 'inflection of the above',
    'contract': 'the payroll object; there is no contract-law sense here',
    'contracts': 'plural of the above',
    'gate': 'the approval object this content names throughout',
    'gates': 'plural of the above',
    'tier': 'the approval level this content names throughout',
    'tiers': 'plural of the above',
    'pipeline': 'the approval chain under its board name',
    'officer': 'short for the Payroll Officer gate',
    'reject': 'the button label',
    'rejected': 'the product state',
    'rejecting': 'inflection of the above',
    'rejection': 'the act',
    'flag': 'the review marker',
    'flags': 'plural of the above',
    'flagged': 'participle of the above',
    'groups': 'plural of the above',
    'journals': 'the accounting output, always plural on screen',
    'filing': 'the compliance object',
    'filings': 'plural of the above',
    'reconcile': 'the statutory-screen verb',
    'reconciles': 'inflection of the above',
    'reconciled': 'inflection of the above',
    'reconciliation': 'the noun',
    'snapshot': 'the analytics object',
    'snapshots': 'plural of the above',
    'variance': 'the analytics noun',
    'variances': 'plural of the above',
    'waterfall': 'the chart name',
    'waterfalls': 'plural of the above',
    'drill': 'the analytics action',
    'drills': 'inflection of the above',
    'drilling': 'inflection of the above',
    'rollup': 'the stored total, hyphen-free spelling',
    'tile': 'the dashboard object',
    'tiles': 'plural of the above',
    'policies': 'plural of insurance policy',
}

# RULE 2: the reverse direction, run over the real corpus with the real
# matcher. A phrase may be perfectly innocent as a phrase and still land
# inside a longer Vietnamese compound — `kỳ` inside `bất kỳ` is the case that
# started this. Every wrap that falls strictly inside one of these compounds
# is a failure, whatever the table says it matched.
#
# Seeded from the review's findings and from the compounds the removed aliases
# were fragments of, so re-adding any of them fails the build rather than
# shipping a card on the wrong word.
VI_COMPOUNDS = (
    'bất kỳ', 'đang chờ', 'chờ đợi', 'kỳ vọng', 'kỳ lương', 'chu kỳ',
    'phiếu lương', 'cổng phê duyệt', 'cấp quản lý', 'cấp duyệt', 'cấp cao',
    'thuế TNCN', 'thuế thu nhập cá nhân', 'đợt lương', 'nhóm quyền',
    'quyền phê duyệt', 'bản nháp', 'vùng chờ',
)


# VI terms that are only legitimate inside specific compounds. Keys and
# compounds are casefolded before matching.
VI_RESTRICTED = {
    # tier-sense uses must be 'cấp' (Phase-2 ruling); these are the loop/
    # lifecycle/duration/tour senses that legitimately keep the word.
    'vòng': ('vòng lặp', 'vòng đời', 'trong vòng', 'một vòng'),
}


# ============================================================================
# reading the content
# ============================================================================
TAG_RE = re.compile(r'<[^>]+>')
TOKEN_RE = re.compile(r'\{\{[^}]*\}\}')
ENTITY = (('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'), ('&quot;', '"'),
          ('&nbsp;', ' '), ('&#39;', "'"))


def plain(s):
    """Prose as a reader meets it: no tags, no entities, tokens as one word."""
    s = TAG_RE.sub('', s or '')
    for a, b in ENTITY:
        s = s.replace(a, b)
    return TOKEN_RE.sub('X', s)


# An abbreviation followed by a full stop is not the end of a sentence. Only
# the ones this content actually writes — a general list would be guessing.
ABBREV = ('e.g', 'i.e', 'etc', 'Mr', 'Ms', 'vs', 'No')
SPLIT_RE = re.compile(r'(?<=[.!?])[\s ]+')


def sentences(s):
    out = []
    for part in SPLIT_RE.split(plain(s)):
        part = part.strip()
        if not part:
            continue
        if out and out[-1].rstrip('.').split()[-1:] and \
                out[-1].rstrip('.').split()[-1] in ABBREV:
            out[-1] = out[-1] + ' ' + part
        else:
            out.append(part)
    return out


WORD_RE = re.compile(r"[0-9A-Za-zÀ-ỹ₫%][0-9A-Za-zÀ-ỹ₫%.,:/'’&-]*")


def wordcount(s):
    return len(WORD_RE.findall(s))


def _pair(v):
    return isinstance(v, dict) and set(v) == {'en', 'vi'}


def leaves(data):
    """(section, where, en, vi) for every learner-facing prose leaf.

    Deliberately NOT derived from the generated tree: the point of the report
    is to name the place in the AUTHORING SOURCE an author has to go and edit,
    and the generated tree has already flattened several of those apart.
    """
    rows = []

    def add(section, where, v):
        if _pair(v) and (v.get('en') or '').strip():
            rows.append((section, where, v['en'], v.get('vi') or ''))

    # chrome — a flat map of plain strings, one tree per language
    def chrome(en_tree, vi_tree, pfx=''):
        for k, v in en_tree.items():
            w = (vi_tree or {}).get(k)
            if isinstance(v, dict):
                chrome(v, w if isinstance(w, dict) else {}, pfx + k + '.')
            elif isinstance(v, str) and v.strip():
                rows.append(('chrome', pfx + k, v, w if isinstance(w, str) else ''))
    chrome(data['i18n']['en'], data['i18n']['vi'])

    for key, g in data['glossary'].items():
        add('glossary', '%s.term' % key, g['term'])
        add('glossary', '%s.def' % key, g['def'])

    for line, ln in data['stations'].items():
        for st in ln['stations']:
            w = '%s/%s' % (line, st['id'])
            add('stations', w + '.title', st['title'])
            add('stations', w + '.desc', st['desc'])
            o = st.get('outline') or {}
            for f in ('what', 'why', 'when', 'prereq'):
                add('stations', '%s.%s' % (w, f), o.get(f))
            for i, m in enumerate(o.get('mistakes') or []):
                add('stations', '%s.mistake%d' % (w, i), m)

    for lk, L in data['lessons'].items():
        add('lessons', '%s.title' % lk, L['title'])
        add('lessons', '%s.goal' % lk, L.get('goal'))
        for i, s in enumerate(L['steps']):
            for f in ('kicker', 'title', 'body', 'tip', 'consequence'):
                add('lessons', '%s.s%d.%s' % (lk, i, f), s.get(f))
        q = L.get('quiz') or {}
        if q:
            add('lessons', '%s.quiz' % lk, q['question'])
            for j, opt in enumerate(q['options']):
                add('lessons', '%s.quiz.o%d' % (lk, j), opt['text'])
                add('lessons', '%s.quiz.o%d.why' % (lk, j), opt['explanation'])

    for mk, m in data['morphs'].items():
        for side in ('before', 'after'):
            for f in ('h', 'd', 'delta'):
                add('morphs', '%s.%s.%s' % (mk, side, f), (m[side] or {}).get(f))

    for m in data['missions']:
        w = m['id']
        add('missions', w + '.title', m['title'])
        add('missions', w + '.desc', m['desc'])
        add('missions', w + '.outlineNote', m.get('outlineNote'))
        for f, v in (m.get('consequence') or {}).items():
            add('missions', '%s.consequence.%s' % (w, f), v)
        for f, v in (m.get('anomaly') or {}).items():
            add('missions', '%s.anomaly.%s' % (w, f), v)
        d = m.get('debrief') or {}
        for i, v in enumerate(d.get('did') or []):
            add('missions', '%s.did%d' % (w, i), v)
        for i, v in enumerate(d.get('checklist') or []):
            add('missions', '%s.check%d' % (w, i), v)
    for mk, steps in data['missionSteps'].items():
        for st in steps:
            w = '%s.%s' % (mk, st['id'])
            for f in ('instruction', 'detail', 'hint'):
                add('missions', '%s.%s' % (w, f), st.get(f))
            for o in st.get('options') or []:
                add('missions', '%s.opt.%s' % (w, o['id']), o['label'])
            for k, v in (st.get('recovery') or {}).items():
                add('missions', '%s.recovery.%s' % (w, k), v)

    for key, s in data['screenCtx'].items():
        add('screens', key + '.blurb', s['blurb'])
        add('screens', key + '.next', s['next'])
        add('screens', key + '.liveFallback', s.get('liveFallback'))

    for sc in data['scenarios']:
        add('scenarios', sc['key'] + '.name', sc['name'])
        add('scenarios', sc['key'] + '.tagline', sc.get('tagline'))
        for st in sc.get('steps') or []:
            say = st.get('say') or {}
            for f in ('kicker', 'title', 'body', 'tip'):
                add('scenarios', '%s.%s.%s' % (sc['key'], st['key'], f), say.get(f))

    for it in data['qa']:
        w = it['id']
        add('intents', w + '.label', it['label'])
        add('intents', w + '.simpler', it.get('simpler'))
        blocks = []
        if it.get('roleVariants'):
            for cap, bs in it['roleVariants'].items():
                blocks += [('%s.' % cap, b) for b in bs]
        else:
            blocks += [('', b) for b in (it.get('blocks') or [])]
        for i, (cap, b) in enumerate(blocks):
            if b['k'] == 'steps':
                for j, s in enumerate(b['v'] or []):
                    add('intents', '%s.%sb%d.s%d' % (w, cap, i, j), s['t'])
            else:
                add('intents', '%s.%sb%d' % (w, cap, i), b.get('v'))
            add('intents', '%s.%sb%d.fallback' % (w, cap, i), b.get('liveFallback'))

    for screen, cols in data['columns'].items():
        for key, label, body in cols:
            add('columns', '%s/%s.label' % (screen, key), label)
            add('columns', '%s/%s.body' % (screen, key), body)

    # ---- practice-data.js, LABELS ONLY -------------------------------------
    # A READ-ONLY GATE. These are the strings the practice replica prints on
    # screen — the state chips, the sub-screen names, the sidebar labels — and
    # a learner reads them exactly as they read a lesson body. They were
    # outside the lint until the Phase 2 review pointed out that "learner-
    # facing" does not stop at the file boundary.
    #
    # VALUES ARE NEVER TOUCHED and are not collected here: every figure in that
    # file is derived, and the ledger is emphatic that a hand-edited fixture
    # figure is how a KPI stops agreeing with the list beneath it. Only the
    # `B(en, vi)` LABEL pairs are measured.
    for chain, states in (data.get('statusLabels') or {}).items():
        for state, label in states.items():
            add('fixture', 'statusLabels.%s.%s' % (chain, state), label)
    for key, sub in (data.get('subScreens') or {}).items():
        for field, value in sub.items():
            add('fixture', 'subScreens.%s.%s' % (key, field), value)
    for i, section in enumerate(data.get('menu') or []):
        add('fixture', 'menu[%d].label' % i, section.get('label'))
        for j, item in enumerate(section.get('items') or []):
            add('fixture', 'menu[%d].item[%d]' % (i, j),
                item.get('label') if isinstance(item, dict) else item)

    return rows


# ============================================================================
# the hovercard's match table — built from the GLOSSARY, per language
# ============================================================================
def match_table(glossary):
    """{lang: [(phrase_lower, key)]}, longest phrase first.

    ONE table, two consumers: this lint checks that every `glossary` jargon
    term is in it, and `engine/glossary.js` wraps exactly these phrases. A term
    the lint demands and the hovercard cannot match is a definition nobody
    reaches, which is the failure this whole gate exists to prevent — so the
    two are not allowed to be two lists.
    """
    out = {'en': [], 'vi': []}
    for key, entry in glossary.items():
        aliases = entry.get('aliases') or {}
        match_term = entry.get('matchTerm') or {}
        for lang in ('en', 'vi'):
            # Mirrors the generator: a DISPLAY term may be excluded from the
            # match table for one language without being excluded from the card.
            phrases = ([(entry['term'] or {}).get(lang) or '']
                       if match_term.get(lang, True) else [])
            phrases += list(aliases.get(lang) or [])
            for p in phrases:
                p = (p or '').strip().lower()
                if p:
                    out[lang].append((p, key))
    for lang in out:
        # Longest first, then alphabetical, so the table is stable and a
        # longer phrase always wins over a shorter one inside it.
        out[lang] = sorted(set(out[lang]), key=lambda t: (-len(t[0]), t[0]))
    return out


# ============================================================================
# the gate
# ============================================================================
def _phrase_re(term):
    """Whole-phrase, case-insensitive, hyphen- and space-tolerant.

    `\\b` is wrong at both ends for this vocabulary: `payroll-ready` starts and
    ends on word characters but `-` is not one, and `net` must not fire inside
    `network`. Lookarounds on the letter/digit class do what a boundary was
    meant to.
    """
    body = re.escape(term).replace(r'\ ', r'[\s -]+')
    return re.compile(r'(?<![0-9A-Za-zÀ-ỹ])' + body + r'(?![0-9A-Za-zÀ-ỹ])',
                      re.IGNORECASE)


_COMPILED = {t: _phrase_re(t) for t in JARGON}


GLOSS_SCAN = r"""
import { RT } from "./runtime.mjs";
import { glossify, setGlossary } from "./glossary.mjs";
import fs from "fs";
const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
setGlossary(input.glossary);
const hits = [];
for (const row of input.rows) {
    RT.lang = row.lang;
    const out = glossify(row.text, row.lang);
    const re = /<span class="lrn-gloss" data-gloss="([a-zA-Z]+)"[^>]*>([^<]*)<\/span>/g;
    let m;
    while ((m = re.exec(out)) !== null) {
        hits.push({ section: row.section, where: row.where, lang: row.lang,
                    key: m[1], text: m[2], out });
    }
}
process.stdout.write(JSON.stringify(hits));
"""


def gloss_scan(data):
    """Run the REAL `glossify` over the whole corpus and return every wrap.

    Not a Python reimplementation of the matcher, deliberately. The ledger's
    standing rule is that a mirror must be able to fail for the reason the
    real thing fails, and a second copy of a longest-match-with-skip-regions
    walk would drift from the shipped one the first time either was touched.
    So the shipped `glossify` is what runs: the two engine files are copied to
    `.mjs` and imported by Node, exactly as replay_tests.py does it.

    Returns [] (and says so) if Node is unavailable, rather than passing
    silently — a gate that quietly does nothing is the failure mode this whole
    round was about.
    """
    # THREE dirnames from AUTHOR, not four: author -> tutorial_poc -> docs ->
    # repo. Same off-by-one the generator's own comment records; caught here by
    # the gate failing loudly rather than by it finding nothing.
    engine = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(AUTHOR))),
        'pb_learn', 'static', 'src', 'engine')
    assert os.path.isdir(engine), 'engine not found at %s' % engine
    rows = []
    for section, where, en, vi in leaves(data):
        rows.append({'section': section, 'where': where, 'lang': 'en', 'text': en})
        if vi:
            rows.append({'section': section, 'where': where, 'lang': 'vi', 'text': vi})
    tmp = tempfile.mkdtemp(prefix='pb-gloss-')
    try:
        for name in ('runtime.js', 'glossary.js'):
            src = open(os.path.join(engine, name), encoding='utf-8').read()
            src = re.sub(r'(from\s+")(\./[A-Za-z0-9_./-]+?)(")',
                         lambda m: m.group(1) + m.group(2) + '.mjs' + m.group(3), src)
            open(os.path.join(tmp, name[:-3] + '.mjs'), 'w', encoding='utf-8').write(src)
        scan = os.path.join(tmp, 'scan.mjs')
        open(scan, 'w', encoding='utf-8').write(GLOSS_SCAN)
        payload = os.path.join(tmp, 'input.json')
        with open(payload, 'w', encoding='utf-8') as fh:
            json.dump({'glossary': [
                {'key': k,
                 'term': v['term'],
                 'definition': v['def'],
                 'match': {lang: sorted(
                     {(p or '').strip().lower()
                      for p in ([(v['term'] or {}).get(lang) or '']
                                + list((v.get('aliases') or {}).get(lang) or []))
                      if (p or '').strip()}, key=lambda p: (-len(p), p))
                     for lang in ('en', 'vi')}}
                for k, v in data['glossary'].items()], 'rows': rows}, fh)
        out = subprocess.run(['node', scan, payload], capture_output=True, text=True)
        if out.returncode:
            raise RuntimeError(out.stderr.strip()[:400])
        return json.loads(out.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _compound_spans(text, compound):
    """Character spans of every occurrence of `compound` in `text`."""
    pat = re.compile(r'(?<![0-9A-Za-zÀ-ỹ])' + re.escape(compound).replace(r'\ ', r'\s+')
                     + r'(?![0-9A-Za-zÀ-ỹ])', re.IGNORECASE)
    return [(m.start(), m.end()) for m in pat.finditer(text)]


def lint(data, warnings=False):
    """(failures, warns, readability, stats).

    failures  list of str — the build stops
    warns     list of str — printed, never fatal
    readability {section: {'leaves','sentences','avg_en','avg_vi','long','warn'}}
    """
    glossary = data['glossary']
    table = match_table(glossary)
    en_phrases = {p for p, _k in table['en']}

    failures, warns = [], []

    # ---- 1. the list agrees with the glossary --------------------------
    for term, (state, detail) in sorted(JARGON.items()):
        if state != 'glossary':
            continue
        if detail not in glossary:
            failures.append(
                'JARGON "%s" wants glossary entry %r, which does not exist. '
                'Either write the entry or move the term to allow/banned.'
                % (term, detail))
        elif term.lower() not in en_phrases:
            failures.append(
                'JARGON "%s" maps to glossary %r, but no term or alias on that '
                'entry spells it that way — so the hovercard would never wrap '
                'it. Add it to aliases.en.' % (term, detail))

    # every glossary entry must be reachable in Vietnamese too
    for key, entry in sorted(glossary.items()):
        for lang in ('en', 'vi'):
            if not ((entry['term'] or {}).get(lang) or '').strip():
                failures.append('glossary %s has no %s term' % (key, lang))

    # ---- 1b. no BARE alias unless it is allowlisted with a reason ------
    # The alias direction of the gate. See BARE_ALIASES for why single words
    # are the ones that need a decision.
    for lang in ('en', 'vi'):
        for phrase, key in table[lang]:
            if len(phrase.split()) != 1 or '-' in phrase:
                continue
            if phrase not in BARE_ALIASES:
                failures.append(
                    'glossary %s [%s]: %r is a SINGLE-WORD match phrase and is '
                    'not in BARE_ALIASES. A bare word wraps every ordinary use '
                    'of it in 1,500 leaves. Either use a longer phrase, or add '
                    'it to BARE_ALIASES with the reason it has no other sense.'
                    % (key, lang, phrase))

    # ---- 1c. THE REVERSE DIRECTION: where the wraps actually land ------
    # Run the shipped matcher over the shipped corpus and look at the result,
    # rather than reasoning about the table. Two ways to fail: a wrap strictly
    # inside a known Vietnamese compound, and a wrap on a phrase the bare-alias
    # rule already forbade (belt and braces — if 1b is ever relaxed by
    # accident, this still catches the damage).
    try:
        hits = gloss_scan(data)
    except Exception as exc:                                  # noqa: BLE001
        failures.append(
            'gloss scan could not run (%s). This gate is the only thing that '
            'checks WHERE a card lands; a build that cannot run it is not a '
            'build that passed it.' % exc)
        hits = []
    by_leaf = {}
    for section, where, en, vi in leaves(data):
        by_leaf[(section, where, 'en')] = plain(en)
        by_leaf[(section, where, 'vi')] = plain(vi)
    seen_bad = set()
    for h in hits:
        if h['lang'] != 'vi':
            continue
        text = by_leaf.get((h['section'], h['where'], 'vi')) or ''
        wrapped = h['text']
        for compound in VI_COMPOUNDS:
            if wrapped.strip().lower() == compound.lower():
                continue            # the wrap IS the compound: correct
            for start, end in _compound_spans(text, compound):
                inner = text[start:end]
                if wrapped in inner and wrapped.lower() != inner.lower():
                    sig = (h['key'], wrapped, compound)
                    if sig in seen_bad:
                        continue
                    seen_bad.add(sig)
                    failures.append(
                        '%s %s [vi]: the hovercard wraps %r (entry %s) INSIDE '
                        'the compound %r. The card would define the wrong '
                        'thing. Drop the alias, or lengthen it.'
                        % (h['section'], h['where'], wrapped, h['key'], compound))

    # ---- 2. banned words, and glossary terms with no entry -------------
    rows = leaves(data)
    for section, where, en, vi in rows:
        text_en = plain(en)
        for term, (state, detail) in JARGON.items():
            if state != 'banned':
                continue
            if _COMPILED[term].search(text_en):
                failures.append('%s %s: banned word "%s" — %s'
                                % (section, where, term, detail))
        if vi:
            text_vi = plain(vi)
            for term, (state, detail) in JARGON.items():
                if state == 'banned' and _COMPILED[term].search(text_vi):
                    failures.append('%s %s [vi]: banned word "%s" — %s'
                                    % (section, where, term, detail))
            # ---- 2b. VI restricted terms: allowed only inside listed
            # compounds. Born from the vong->cap sweep, where one blind
            # replace produced nonsense and one tier-sense survivor shipped
            # (Phase-2 re-review NEW-1/NEW-2): a claimed clean sweep is not
            # one until a gate says so.
            low = text_vi.casefold()
            for term, allowed in VI_RESTRICTED.items():
                start = 0
                while True:
                    i = low.find(term, start)
                    if i < 0:
                        break
                    ok = any(
                        low[max(0, i - len(comp)):i + len(comp) + len(term)]
                        .find(comp) >= 0
                        for comp in allowed)
                    if not ok:
                        failures.append(
                            '%s %s [vi]: "%s" outside its allowed compounds '
                            '(%s)' % (section, where, term, ', '.join(allowed)))
                        break
                    start = i + len(term)

    # ---- 3. sentence length --------------------------------------------
    readability = {}
    for section, where, en, vi in rows:
        r = readability.setdefault(section, {
            'leaves': 0, 'sent_en': 0, 'words_en': 0, 'sent_vi': 0,
            'words_vi': 0, 'long': 0, 'warn': 0, 'max': 0})
        r['leaves'] += 1
        for s in sentences(en):
            n = wordcount(s)
            r['sent_en'] += 1
            r['words_en'] += n
            r['max'] = max(r['max'], n)
            if n > HARD_WORDS:
                r['long'] += 1
                failures.append(
                    '%s %s: %d-word sentence (limit %d) — "%s…"'
                    % (section, where, n, HARD_WORDS, s[:70]))
            elif n >= WARN_WORDS:
                r['warn'] += 1
                if warnings:
                    warns.append('%s %s: %d words — "%s…"'
                                 % (section, where, n, s[:70]))
        for s in sentences(vi):
            r['sent_vi'] += 1
            r['words_vi'] += wordcount(s)

    for r in readability.values():
        r['avg_en'] = r['words_en'] / max(r['sent_en'], 1)
        r['avg_vi'] = r['words_vi'] / max(r['sent_vi'], 1)

    stats = {
        'wraps': len(hits),
        'bare_ok': len(BARE_ALIASES),
        'terms': len(JARGON),
        'glossary_terms': sum(1 for v in JARGON.values() if v[0] == 'glossary'),
        'banned': sum(1 for v in JARGON.values() if v[0] == 'banned'),
        'allow': sum(1 for v in JARGON.values() if v[0] == 'allow'),
        'entries': len(glossary),
        'matchable_en': len(table['en']),
        'matchable_vi': len(table['vi']),
        'leaves': len(rows),
    }
    return failures, warns, readability, stats


def print_readability(readability, out=print):
    out('')
    out('  readability — average words per sentence (EN authored, VI authored)')
    out('  %-11s %7s %8s %8s %7s %7s %6s'
        % ('section', 'leaves', 'avg EN', 'avg VI', '>%d' % HARD_WORDS,
           '%d-%d' % (WARN_WORDS, HARD_WORDS), 'max'))
    tw, ts, tv, tvs = 0, 0, 0, 0
    for section in sorted(readability):
        r = readability[section]
        tw += r['words_en']
        ts += r['sent_en']
        tv += r['words_vi']
        tvs += r['sent_vi']
        out('  %-11s %7d %8.1f %8.1f %7d %7d %6d'
            % (section, r['leaves'], r['avg_en'], r['avg_vi'], r['long'],
               r['warn'], r['max']))
    out('  %-11s %7s %8.1f %8.1f' % ('ALL', '', tw / max(ts, 1), tv / max(tvs, 1)))


def dump():
    out = subprocess.run(['node', os.path.join(HERE, 'dump_content.js')],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--warnings', action='store_true',
                    help='list every 17-28 word sentence, not just the count')
    ap.add_argument('--terms', action='store_true',
                    help='print the phrase table the hovercard will match')
    args = ap.parse_args()

    data = dump()
    if args.terms:
        table = match_table(data['glossary'])
        for lang in ('en', 'vi'):
            print('== %s: %d phrases' % (lang, len(table[lang])))
            for phrase, key in table[lang]:
                print('   %-42s %s' % (phrase, key))
        return 0

    failures, warns, readability, stats = lint(data, warnings=args.warnings)
    print('jargon lint — %d curated terms (%d glossary, %d banned, %d allowed) '
          'over %d prose leaves'
          % (stats['terms'], stats['glossary_terms'], stats['banned'],
             stats['allow'], stats['leaves']))
    print('  glossary: %d entries · %d matchable phrases EN · %d VI'
          % (stats['entries'], stats['matchable_en'], stats['matchable_vi']))
    print_readability(readability)
    if warns:
        print('')
        print('  %d sentence(s) in the %d-%d word warning band:'
              % (len(warns), WARN_WORDS, HARD_WORDS))
        for w in warns:
            print('    %s' % w)
    if failures:
        print('')
        print('JARGON LINT: %d failure(s).' % len(failures))
        for f in failures:
            print('  %s' % f)
        return 8
    print('')
    print('✓ jargon lint clean.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
