# -*- coding: utf-8 -*-
"""THE GATE — PA-R1, no back door.

An Action is allowed for a person only when BOTH halves say yes:

  1. the Access-home half — the Action's screen (a `pb.sidebar.item`) is
     'on' for the person in `pb.sidebar.item.visibility_for(user)`, which is
     the one rule the left menu AND the Access home's person passport are
     drawn from (lent roles arrive as groups, so they are honoured there);
  2. the method half — the Action's own right (group / ACL), judged with
     `with_user(user)` so a test's superuser env cannot say yes for somebody
     else (ledger PA12).

Neither alone. A screen that is locked or hidden refuses even when the ACL
would allow the method; a right without the screen refuses too.
"""
import logging
import re
import unicodedata

from odoo.tools.translate import LazyTranslate

from .i18n import T

from .registry import TIER_SWITCH

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)


# ======================================================================
# FIX-1b — OWNER RULING 2026-10-13: PayAI never reaches Settings › Access
# and delegations ("do not allow Settings->Access and delegations to be
# accessible or controled by PayAI at all. This is to safeguard anyone
# changing roles through backdoor.")
#
# THE ONE DENY-LIST. Every place a door is registered (`rpc_register_doors`),
# read (`runner.Ctx`), resolved (`resolve_door`, `OpenScreen`), offered on a
# card (`scrub_card`, applied where every card leaves the server) or decided
# (`access_request`, the Red Actions and Remind) asks THIS module. Matched on
# identifiers only — a ⌘K row id, an action tag, an action xmlid, a lens /
# focus key, a Learn station or walkthrough key, a model name — never on a
# label, which is translated and can be renamed.
#
# Built from the code (2026-10-13):
#   * biz_access/static/src/js/access_palette.js — the Access home's five ⌘K
#     rows (the home, "Hand my access to somebody", Access history, Roles,
#     The left menu), its client tag and its three window actions;
#   * pb_approval_config/static/src/js/palette.js — "People & backups", the
#     Approval Matrix tab where approval hand-overs (`biz.approval.delegation`
#     via `set_delegation` / `end_delegation`) and responsibility holders are
#     set;
#   * pb_settings settings_hub.js — the "access" and "nav" categories (the
#     Access home's cards) and the native user / menu-entry lists the cog
#     carries (`PLATFORM_ONLY_ACTIONS`);
#   * pb_learn learn_palette.js — the Access lesson and walkthrough rows
#     (`learn.station.access`, `learn.scenario.sc_access`) and their focus;
#   * biz_access models — roles, role abilities, role holders, role changes,
#     access hand-overs, access requests (decided through the approvals
#     engine under the 'roles' process: approving one GIVES a role).
# ======================================================================
#: ⌘K row ids (`pb_hub_palette` keys).
ACCESS_DOORS = frozenset((
    'va_access', 'va_delegate', 'va_history', 'va_roles', 'va_screens',
    'approval_people',
    'learn.station.access', 'learn.scenario.sc_access',
))
#: Client action tags.
ACCESS_TAGS = frozenset(('pb_access_board',))
#: Action xmlids.
ACCESS_XMLIDS = frozenset((
    'biz_access.action_pb_access_board',
    'biz_access.action_pb_access_delegation',
    'biz_access.action_pb_role_profile',
    'base.action_res_users',
    'base.action_res_groups',
    'pb_sidebar.action_pb_sidebar_item',
    'pb_sidebar.action_pb_sidebar_section',
))
#: (screen tag or xmlid, lens / focus) — a tab of another screen that is the
#: Access home's business.
ACCESS_LENSES = frozenset((
    ('pb_approval_matrix', 'people'),
    ('pb_approval_config.action_pb_approval_matrix', 'people'),
    ('pb_settings_hub', 'access'),
    ('pb_settings.action_pb_settings_hub', 'access'),
    ('pb_settings_hub', 'nav'),
    ('pb_settings.action_pb_settings_hub', 'nav'),
))
#: Learn station / walkthrough keys (a Learn row's focus is
#: "station:<key>" or "scenario:<key>:<mode>").
ACCESS_LEARN = frozenset(('access', 'sc_access'))
#: FIX-1b (second pass): the Access station's lessons (pb_learn
#: learn_content.json, station "access": lessons ["L23"]) — a focus of
#: "lesson:<key>", and the `open_lesson` the question path's "Show me" may
#: carry (pb_payroll_ai_insights `_KNOWN_LESSONS`: "L23: Access and handing
#: it over while away").
ACCESS_LESSONS = frozenset(('L23',))
#: Models PayAI never writes, directly or through a method it calls.
ACCESS_MODELS = frozenset((
    'pb.access', 'pb.access.request', 'pb.access.delegation', 'pb.access.approval',
    'pb.role.profile', 'pb.role.ability', 'pb.role.assignment', 'pb.role.change',
    'biz.access.export', 'biz.approval.delegation',
    'res.groups', 'res.users', 'pb.sidebar.item', 'pb.sidebar.section',
))
#: Approval processes whose decision changes access (biz_access
#: `ROLES_PROCESS_KEY`).
ACCESS_PROCESS_KEYS = frozenset(('roles',))
#: The keys a door target may name a lens or a focus under (`openHub`'s own,
#: and the hub protocol's context keys).
_TARGET_MARKS = ('lens', 'focus')
_CONTEXT_MARKS = ('pb_lens', 'pb_focus', 'lens', 'focus')


def target_denied(target):
    """True when a navigation target ({tag, xmlid, lens, focus, context}) is
    the Access home or one of its lenses / tabs / lessons."""
    if not isinstance(target, dict):
        return False
    tag = str(target.get('tag') or '')
    xmlid = str(target.get('xmlid') or '')
    if tag in ACCESS_TAGS or xmlid in ACCESS_XMLIDS:
        return True
    context = target.get('context') if isinstance(target.get('context'), dict) else {}
    marks = {str(target.get(k) or '') for k in _TARGET_MARKS}
    marks |= {str(context.get(k) or '') for k in _CONTEXT_MARKS}
    marks.discard('')
    for screen in (tag, xmlid):
        if screen and any((screen, mark) in ACCESS_LENSES for mark in marks):
            return True
    for mark in marks:
        if learn_focus_denied(mark):
            return True
    return False


def learn_focus_denied(mark):
    """True for a Learn focus into the Access lesson or walkthrough:
    "station:access", "scenario:sc_access:<mode>", "lesson:L23"."""
    parts = str(mark or '').split(':')
    if len(parts) < 2:
        return False
    if parts[0] in ('station', 'scenario'):
        return parts[1] in ACCESS_LEARN
    return parts[0] == 'lesson' and parts[1] in ACCESS_LESSONS


def learn_action_denied(action):
    """FIX-1b (second pass) — True for the question path's "Show me"
    button (`{'type': 'open_walkthrough', 'walkthrough': …}` or
    `{'type': 'open_lesson', 'lesson': …}`, pb_payroll_ai_insights
    `_sanitize_action`) when it would open the Access walkthrough (which
    walks the live Access home) or the Access lesson."""
    if not isinstance(action, dict):
        return False
    kind = action.get('type')
    if kind == 'open_walkthrough':
        return str(action.get('walkthrough') or '') in ACCESS_LEARN
    if kind in ('open_lesson', 'start_tour'):
        return str(action.get('lesson') or '') in ACCESS_LESSONS
    return False


def door_denied(row):
    """True for a ⌘K row (or a bare row id) PayAI must never open or offer."""
    if isinstance(row, dict):
        rid = str(row.get('id') or '')
        return rid in ACCESS_DOORS or target_denied(row.get('target'))
    return str(row or '') in ACCESS_DOORS


def action_denied(act):
    """True for a card button whose destination is denied."""
    if not isinstance(act, dict):
        return False
    if act.get('door_id') and door_denied(str(act['door_id'])):
        return True
    if target_denied(act.get('hub')):
        return True
    if act.get('id') == 'learn' and (str(act.get('scenario') or '') in ACCESS_LEARN
                                     or str(act.get('lesson') or '') in ACCESS_LESSONS):
        return True
    return learn_action_denied(act)


def scrub_card(card):
    """Drop every button and chip that would open a denied screen. Applied
    where a card leaves the server (the runner's `_finish` and `envelope`,
    the callbacks, the history), so no Action can offer one by mistake.
    Accepts a card, or a dict carrying one under 'card'. Returns it."""
    if not isinstance(card, dict):
        return card
    if isinstance(card.get('card'), dict):
        scrub_card(card['card'])
    if isinstance(card.get('actions'), list):
        card['actions'] = [a for a in card['actions'] if not action_denied(a)]
    if isinstance(card.get('chips'), list):
        card['chips'] = [c for c in card['chips'] if not (
            isinstance(c, dict) and (door_denied(str(c.get('value') or ''))
                                     or target_denied(c.get('hub'))))]
    return card


def access_request(env, request, process_key=None):
    """True when deciding (or chasing) this approval request would change
    somebody's access: it is about a biz_access record, or runs under the
    roles process. Unreadable → True (refuse rather than guess)."""
    if process_key and process_key in ACCESS_PROCESS_KEYS:
        return True
    try:
        if not request:
            return False
        # What the request is ABOUT (its model and process), read whatever the
        # reader's own rights: the ids come from the person's own inbox, and
        # this only ever narrows what PayAI does (read-only, never a write).
        row = request.sudo().exists()
        if not row:
            return False
        if (row.res_model or '') in ACCESS_MODELS:
            return True
        return (row.process_id.key or '') in ACCESS_PROCESS_KEYS
    except Exception:                                   # noqa: BLE001
        _logger.info("PayAI gate: request %s unreadable; treated as access", request,
                     exc_info=True)
        return True


#: Words that name access, roles, permissions or delegations — in a screen
#: name the model hands `open_screen`, or a sentence. Folded (no marks).
#: Shared with `actions_stubs.NeverAccess` (FIX-1b second pass: the words
#: were too broad and caught Hiring, trips, leavers and building passes).
#:
#: "access", but not a building pass or a team called Access ("approve the
#: access card request", "show the run for the access team").
ACCESS_WORD_EN = (r"access(?:es)?\b(?!\s+(?:cards?|badges?|teams?|pass(?:es)?|codes?|"
                  r"doors?|keys?|roads?|points?|gates?|fobs?)\b)")
#: A hand-over OF ACCESS — not a leaver's hand-over of work or of a laptop
#: ("approve the exit hand-over for Lan", "the handover checklist").
HANDOVER_EN = (r"(?<!exit\s)(?<!exit-)(?<!leaver\s)(?<!leaver's\s)(?<!leavers\s)"
               r"(?<!offboarding\s)(?<!work\s)(?<!shift\s)"
               r"hand[\s-]?overs?\b(?!\s+(?:items?|checklists?|lists?|tasks?|notes?|forms?|"
               r"meetings?|of\s+(?:the\s+|his\s+|her\s+|their\s+)?(?:laptops?|equipment|"
               r"assets?|keys?|devices?|work|files?|documents?|duties|tasks?|shifts?))\b)")
#: FIX-1b third pass: the usual slips of the keyboard ("give lan acess",
#: "open acess", "change Lan's rol", "permision", "previlege", "delagation").
ACCESS_TYPOS_EN = (r"(?:acess|acces|accses|acsess|axess|accesss|acccess)\b|"
                   r"(?:permision|permisson|premission|permssion|permition)s?\b|"
                   r"(?:previl|privel|privil(?!eg))\w*\b|"
                   r"(?:delagat|deligat|delegaton)\w*\b|"
                   r"(?:rolse|rloes|roels|rols)\b|(?<=\bmy\s)rol\b|(?<='s\s)rol\b")
#: The nouns of the Access home's business, folded English — every noun but
#: "role" (`ACCESS_NOUNS_EN` adds it; a LOOK reads only "roles", FIX-1b third
#: pass: "show my role", "open the Sales Manager role" are a job, not access).
_ACCESS_NOUNS_BODY = (
    ACCESS_WORD_EN + r"|permissions?\b|privileges?\b|"
    r"delegat(?:e|es|ed|ing|ion|ions)\b|rights\b|" + ACCESS_TYPOS_EN + r"|"
    r"(?:lend|lent|lending)\s+(?:\S+\s+){0,2}?approvals?\b|" + HANDOVER_EN + r"|"
    r"handing\s+over\b|hand\s+(?:over\s+)?my\b|people\s+(?:&|and)\s+backups?\b|"
    r"security\s+groups?\b|user\s+groups?\b|left\s+menu\b|"
    r"approval\s+matrix\s+people\b|people\s+tab\s+of\s+(?:the\s+)?approval|"
    # FIX-1b fourth pass: the Access home's own lens and tool names
    # (biz_access access_board.js LENS_REGISTRY "Screens", the People lens's
    # "passport", the header's "See it as somebody else", pb_settings'
    # "Navigation" card) and the plain "user management". A passport on its
    # own is an employee's identity document (pb_employee_vault, Hiring's
    # documents), so only the Access home's own "people / access passport".
    r"user\s+management\b|manage\s+users\b|users?\s+admin(?:istration)?\b|"
    r"(?:people|access|user)\s+passports?\b|passports?\s+(?:lens|tab|view)\b|"
    r"screens\s+(?:lens|tab|view)\b|navigation\s+(?:lens|tab|card|settings)\b|"
    r"see\s+it\s+as\s+(?:somebody|someone|another)\b|"
    r"who\s+can\s+open\s+(?:each|every|which|what)\s+screens?\b")
ACCESS_NOUNS_EN = r"\b(?:" + _ACCESS_NOUNS_BODY + r"|roles?\b)"
#: What a LOOK ("open …", "show …") reads as the Access home: "roles" in the
#: plural, or "role" named as a screen ("the role list", "user roles").
ACCESS_NOUNS_LOOK_EN = (
    r"\b(?:" + _ACCESS_NOUNS_BODY + r"|roles\b|"
    r"(?:user|users'?|access|security|app|system)\s+roles?\b|"
    r"roles?\s+(?:screen|page|tab|list|settings|management|matrix|and\s+\S+)\b)")
#: "role" is a job opening in Hiring: a sentence about hiring — or one that
#: opens "a role" (the Hiring lesson is "Open a role and ask for its
#: request") — is not about access.
HIRING_EN = (r"\b(?:hiring|jobs?|vacanc(?:y|ies)|candidates?|recruit\w*|"
             r"role'?s?\s+(?:boards?|requests?|openings?|vacanc(?:y|ies))|"
             r"open(?:s|ed|ing)?\s+(?:up\s+)?(?:a|an|one|another|the\s+new)\s+"
             r"(?:new\s+)?(?:\S+\s+){0,3}?roles?|"
             # FIX-1b third pass: "show open roles" — "open" as a word for
             # the roles, not the order (never the sentence's first word).
             r"(?<=\s)(?:open|vacant|unfilled|new)\s+roles)\b")
_ACCESS_WORDS_EN = re.compile(ACCESS_NOUNS_EN)
#: The Vietnamese nouns, folded. FIX-1b third pass: "menu bên trái" (the
#: left menu — its screens are locked per person in the Access home).
ACCESS_NOUNS_VI = (
    r"\b(?:phan\s+quyen|quyen\s+truy\s+cap|truy\s+cap|vai\s+tro|uy\s+quyen|"
    r"(?:ban\s+)?giao\s+quyen|nhom\s+quyen|quyen\s+han|cap\s+quyen|thu\s+hoi\s+quyen|"
    r"quyen\s+quan\s+tri|cho\s+muon\s+quyen|menu\s+ben\s+trai|thanh\s+ben|"
    r"nhom\s+nguoi\s+dung)\b")
_ACCESS_WORDS_VI = re.compile(ACCESS_NOUNS_VI)
_HIRING_WORDS = re.compile(
    HIRING_EN + r"|\b(?:tuyen\s+dung|ung\s+vien)\b"
    # A screen named "a role" / "a new role" is the Hiring opening.
    r"|^(?:an?|one)\s+(?:new\s+)?roles?\b")


def _fold(text):
    raw = unicodedata.normalize('NFKD', text or '')
    raw = ''.join(c for c in raw if not unicodedata.combining(c))
    return raw.lower().replace('đ', 'd')


# ---------------------------------------------- FIX-1b third pass: look-alikes
#: An access noun that names something else: a pay item or a team ("admin
#: allowance", "role allowance", "access allowance", "the admin fee", "the
#: admin team"), a right in law ("leave rights"), a permission for work
#: ("permission to work overtime"), a part in a run or a project ("Lan's
#: role in the June run"). English, case ignored.
_PAY_OR_TEAM_EN = (
    r"allowances?|fees?|bonus(?:es)?|pay|payments?|teams?|departments?|dept|staff|office|"
    r"costs?|expenses?|charges?|cards?|budgets?|lev(?:y|ies)|stipends?|premiums?|rates?|"
    r"grades?|bands?|titles?|descriptions?|work|tasks?|duties|assistants?|officers?|"
    r"clerks?|days?|hours?|support|units?|divisions?|salary|salaries|components?|"
    r"deductions?|supplements?|loading|money|amounts?|items?|lines?|codes?")
_NOT_ACCESS_EN = (
    re.compile(r"\b(?P<w>admin(?:istrat(?:or|ion))?s?|roles?|access|permissions?|rights?|"
               r"privileges?)(?=\s+(?:" + _PAY_OR_TEAM_EN + r")\b)", re.I),
    re.compile(r"\b(?:leave|holiday|vacation|annual|employees?'?|employment|maternity|"
               r"paternity|parental|statutory|legal|labou?r|workers?'?|insurance|benefits?|"
               r"pension|sick|overtime|human|union|voting|property)\s+(?P<w>rights?)\b", re.I),
    re.compile(r"\b(?P<w>permissions?)(?=\s+(?:to|for)\s+(?!(?:approv\w*|see|view|access|"
               r"edit|open|run|manage|sign|reject|decide|change|delete|export|import|create|"
               r"act|send|payroll|use\s+(?:the\s+)?(?:app|system|payroll|screen)|"
               r"the\s+(?:\S+\s+){0,2}?(?:screens?|menus?|apps?|pages?|modules?|tabs?))\b))",
               re.I),
    re.compile(r"\b(?P<w>roles?)(?=\s+(?:in|on|at|within)\s+(?:the\s+|a\s+|an\s+|this\s+|"
               r"that\s+|his\s+|her\s+|their\s+|our\s+)?(?!(?:payroll|app|system|access|"
               r"approvals?|settings|payobook)\b)\S)", re.I),
)
#: A job's role, written as a title: "the Sales Manager role" (Hiring) —
#: not a possessive ("Lan's role") and not an app's own role ("the Payroll
#: Manager role" is the Access home's). Case KEPT.
_JOB_ROLE_EN = re.compile(r"(?<![\w'’])((?:[A-Z][\w&-]*\s+){1,4})(?P<w>[Rr]oles?)\b")
_JOB_TITLES = frozenset((
    'manager', 'managers', 'officer', 'engineer', 'developer', 'analyst', 'assistant',
    'director', 'lead', 'executive', 'specialist', 'coordinator', 'clerk', 'accountant',
    'designer', 'consultant', 'supervisor', 'intern', 'cashier', 'driver', 'technician',
    'representative', 'rep', 'associate', 'head', 'chief', 'operator', 'agent', 'advisor',
    'adviser', 'administrator', 'receptionist', 'controller', 'auditor', 'tester',
    'architect', 'scientist', 'nurse', 'teacher', 'trainer', 'worker', 'secretary'))
_APP_AREAS = frozenset(('payroll', 'hr', 'approval', 'approvals', 'access', 'user', 'users',
                        'security', 'admin', 'administrator', 'system', 'app', 'finance',
                        'settings', 'payobook', 'people', 'super'))
#: Vietnamese look-alikes, on the FOLDED words (one character per
#: character, so the spans line up with the marked text): "quyền lợi"
#: (benefits), "quyền nghỉ phép" (leave entitlement), "quyển sổ" (a
#: volume), "vai trò công việc" / "vai trò … trong dự án" (a part in a
#: job), "phụ cấp vai trò" (an allowance).
_NOT_ACCESS_VI = (
    re.compile(r"\b(?P<w>quyen)\s+(?:loi|nghi|so\s+huu|cong\s+dan|rieng\s+tu|tac\s+gia|"
               r"thai\s+san|con\s+nguoi|lao\s+dong|uu\s+tien|mua|bau|so|sach|vo|tap|lich)\b"),
    re.compile(r"\b(?P<w>vai\s+tro)(?=\s+(?:cong\s+viec|chuyen\s+mon|chuc\s+danh|du\s+an)\b|"
               r"(?:\s+\S+){0,4}?\s+(?:trong|tai)\s+(?:du\s+an|nhom|cong\s+ty|phong|team|doi|"
               r"bo\s+phan|cong\s+viec|bang\s+luong|dot\s+luong|ky\s+luong|dot\s+tuyen)\b)"),
    re.compile(r"\b(?:phu\s+cap|tien|thuong|khoan)\s+(?:\S+\s+){0,2}?(?P<w>vai\s+tro|quan\s+tri)\b"),
)


def _blank(text, spans):
    out = list(text)
    for a, b in spans:
        out[a:b] = 'x' * (b - a)
    return ''.join(out)


def mask_not_access(text):
    """The words with every access noun that names something ELSE blanked
    out ("x" for each letter, so the text keeps its length and a phrase
    matched on it still lines up). FIX-1b third pass: the never card took
    "Give Lan an admin allowance of 500,000", "show Lan's leave rights",
    "xem quyền lợi bảo hiểm của Lan", "bàn giao quyển sổ lương".
    Shared by `actions_stubs.NeverAccess.phrase_ok` and `names_access`."""
    text = text or ''
    spans = []
    for rx in _NOT_ACCESS_EN:
        spans += [m.span('w') for m in rx.finditer(text)]
    for m in _JOB_ROLE_EN.finditer(text):
        words = m.group(1).split()
        if m.start(1) == 0 and len(words) == 1:
            continue                                    # "Roles" / "Open roles"
        if any(w.lower().strip('&-') in _APP_AREAS for w in words):
            continue
        if words[-1].lower() not in _JOB_TITLES:
            continue                                    # "Lan role", "Change Lan role"
        spans.append(m.span('w'))
    # "quyển" (a volume) is never "quyền" (access), whatever follows it.
    spans += [m.span() for m in re.finditer(r'quyển', text, re.I)]
    from .resolve import fold_keep
    folded = fold_keep(text)
    if len(folded) == len(text):
        for rx in _NOT_ACCESS_VI:
            spans += [m.span('w') for m in rx.finditer(folded)]
    return _blank(text, spans) if spans else text


#: FIX-1b fourth pass: a screen name the model may hand `open_screen` that,
#: as a WHOLE name, is one of the Access home's lenses or cards (biz_access
#: access_board.js "Screens" / "People" passports, access_palette.js and
#: pb_settings settings_hub.js "Navigation", the native "Users" list). Only
#: whole: "People" alone is the People hub, "the payslips screen" a screen.
_ACCESS_SCREEN_NAMES = re.compile(
    r"^(?:the\s+)?(?:screens|users?|user\s+list|app\s+users|system\s+users|navigation|"
    r"passports|people\s+passports?|see\s+it\s+as(?:\s+somebody\s+else)?|view\s+as)"
    r"(?:\s+(?:screen|page|tab|lens|list|card|menu|settings))?$")


def names_access(text):
    """True when the words name the Access home's business (roles, access,
    permissions, delegations, hand-overs of access, the left menu), or are
    the whole name of one of its lenses ("Screens", "Users", "Navigation")."""
    text = mask_not_access(text)
    folded = ' '.join(_fold(text).split())
    if not folded or _HIRING_WORDS.search(folded):
        return False
    if _ACCESS_SCREEN_NAMES.match(folded.strip(' .?!')):
        return True
    return bool(_ACCESS_WORDS_EN.search(folded) or _ACCESS_WORDS_VI.search(folded))


def tier_on(env, tier, company=None):
    """Is this tier switched on for the company?

    `company` — the company the Action works IN (P3:sec-1: a Red request is
    judged on the request's own company, not on the company in the top bar,
    because the inbox lists every company the person has ticked). None means
    the current company (`env.company`), as before.
    """
    field = TIER_SWITCH.get(tier)
    if not field:
        return False
    company = company if company is not None else env.company
    if not company or field not in company._fields:
        return False
    try:
        return bool(company[field])
    except Exception:                                   # noqa: BLE001
        # A company the person cannot read is never one PayAI may act in.
        _logger.info("PayAI gate: switch of %s unreadable; refusing", company, exc_info=True)
        return False


def tier_on_somewhere(env, user, tier):
    """Is this tier switched on in ANY company the person works in?

    For an Action whose switch is read off the record it decides
    (`switch_per_record`: Red, P3:sec-1). Before the request is found, the
    gate cannot know its company — the Approvals inbox lists the requests of
    every company the person works in (`_my_company_ids`), whatever the top
    bar says — so the gate only asks "could it be on for any of them"; the
    request's own company is asked as soon as the request is read, on the
    plan and again at Do it. Never the top-bar company alone: a request in a
    company whose switch is ON is not refused because the top bar shows one
    whose switch is OFF."""
    companies = user.sudo().company_ids or user.sudo().company_id
    return any(tier_on(env, tier, company) for company in companies)


def screen_item(env, action):
    """The Action's screen: the first ACTIVE sidebar item it names, or None."""
    for xmlid in action.screen_keys:
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec and rec._name == 'pb.sidebar.item' and rec.sudo().active:
            return rec
    return None


def screen_state(env, user, action):
    """'on' | 'locked' | 'hidden' | 'none' (the Action declares no screen).

    An Action that declares screens but none of them is on this database is
    'hidden': the screen does not exist here, so nobody can stand on it.

    FIX-1b (P3:sec-4) — everything the Access home can really lock is read,
    from the one rule the left menu is drawn from (`visibility_for`, which
    counts lent roles and roles written on the entry):
      * the entry itself (its permissions or roles — locked or hidden);
      * the block of the left menu it sits in (a locked section locks every
        entry in it) and, for a sub-entry, the entry above it;
      * the tab INSIDE the screen the Action works on (`surface_key` /
        `surface_groups`: the Approvals inbox is a tab of Home), judged by
        the Access home's own `surface_access` — the answer it shows on a
        person's passport.
    """
    if not action.screen_keys:
        return 'none'
    item = screen_item(env, action)
    if item is None:
        return 'hidden'
    vis = env['pb.sidebar.item'].visibility_for(user)
    items = vis.get('items') or {}
    state = items.get(item.id, 'hidden')
    if state != 'on':
        return state
    row = item.sudo()
    if row.parent_id:
        # The drawn menu opens a sub-entry only under an entry it shows
        # unlocked (pb_sidebar.xml draws children only when the entry above
        # is not padlocked, and lists none under a hidden one).
        state = items.get(row.parent_id.id, 'hidden')
        if state != 'on':
            return state
    state = (vis.get('sections') or {}).get(row.section_id.id, 'hidden')
    if state != 'on':
        return state
    return 'on' if surface_ok(env, user, action) else 'hidden'


def surface_ok(env, user, action):
    """Is the tab the Action works on open to this person? True when the
    Action names no tab, or the tab names no permission.

    The tab's permissions live in the screen's own code (the Approvals tab's
    `APPROVAL_GATE` in pb_home_hub), so the Action restates them and a test
    holds the two equal. Asked of the Access home when it is installed —
    the person asking about themselves, as the passport does — else of the
    person's own permissions, ANY one is enough, as the tab itself asks."""
    groups = tuple(getattr(action, 'surface_groups', None) or ())
    if not groups:
        return True
    key = getattr(action, 'surface_key', None) or action.key
    if 'pb.access' in env:
        try:
            answer = env['pb.access'].with_user(user).surface_access(
                [{'key': key, 'groups': list(groups)}], user.id)
            return bool((answer or {}).get(key, {}).get('allowed'))
        except Exception:                               # noqa: BLE001
            _logger.info("PayAI gate: tab %s unreadable for %s; refusing", key, user,
                         exc_info=True)
            return False
    return any(user.has_group(xmlid) for xmlid in groups)


def method_ok(env, user, action):
    try:
        return bool(action.method_gate(env, user))
    except Exception:                                   # noqa: BLE001
        _logger.info("PayAI gate: method check for %s raised; refusing",
                     action.key, exc_info=True)
        return False


def allowed(env, user, action):
    """(ok, reason) — reason in 'tier_off' | 'no_right' | 'screen_off' | ''.

    Order of the reasons is the order of usefulness to the person reading the
    refusal: a switched-off tier is the company's decision, a missing right is
    the most actionable, a locked screen is the Access home's.
    """
    if action.tier == 'never':
        return False, 'never'
    if getattr(action, 'switch_per_record', False):
        # P3:sec-1 — judged on the request's own company once it is read
        # (`actions_red._Red._read`, and `remind`); here only "on anywhere
        # this person works", never the top-bar company alone.
        switched = tier_on_somewhere(env, user, action.tier)
    else:
        switched = tier_on(env, action.tier)
    if not switched:
        return False, 'tier_off'
    if not user._is_internal():
        return False, 'no_right'
    m_ok = method_ok(env, user, action)
    s_state = screen_state(env, user, action)
    s_ok = s_state in ('on', 'none')
    if not m_ok:
        return False, 'no_right'
    if not s_ok:
        return False, 'screen_off'
    return True, ''


def prefilter(env, user, action):
    """The gate without the tier switch: may this person EVER do it here?

    Used to decide what to offer the model and what to list under "What can
    you do?". The tier switch is still checked at run time by `allowed`.
    """
    if action.tier == 'never':
        return False, 'never'
    if not tier_on(env, 'look'):
        return False, 'tier_off'
    if not user._is_internal():
        return False, 'no_right'
    if not method_ok(env, user, action):
        return False, 'no_right'
    if screen_state(env, user, action) not in ('on', 'none'):
        return False, 'screen_off'
    return True, ''


def refusal_text(action, reason):
    """The plain sentence for a refusal. Never a code word."""
    if reason == 'tier_off':
        return T(_lt(
            "PayAI can look, but is not allowed to do this here yet. An "
            "administrator can switch it on under Settings › PayAI can act."))
    # FIX-1b — the Access home is named in words only: no door to it is ever
    # offered (owner ruling 2026-10-13).
    if reason == 'screen_off':
        return T(_lt(
            "That screen is not switched on for you, so I cannot do this for "
            "you. Ask your administrator to change this under Settings › "
            "Access and delegations."))
    if reason == 'never':
        if getattr(action, 'never_text', None):
            return T(action.never_text)
        return T(_lt("I do not do this, even when asked clearly. You can do "
                       "it yourself on the screen if you have the right."))
    subject = T(action.right_subject or action.title)
    right = T(action.right_label or action.title)
    return T(_lt(
        "%(subject)s is for payroll staff. Your sign-in does not have the "
        "%(right)s right. Ask your administrator to change this under "
        "Settings › Access and delegations.")) % {'subject': subject, 'right': right}
