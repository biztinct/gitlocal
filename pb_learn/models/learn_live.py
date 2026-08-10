# -*- coding: utf-8 -*-
"""The two live surfaces, in one file so there is one thing to audit.

WHAT LIVES HERE
---------------
  LIVE_PREDICATES   the capstone mission's step checks. Each answers ONE
                    question about the demo world — has the run been computed,
                    has it been submitted, whose gate is it at — and answers it
                    by looking, never by doing.
  LIVE_VALUES       the six keys content may interpolate as {{live:key}}.

WHY THEY SHARE A FILE
---------------------
Both are the same promise in two shapes: pb_learn may READ the product and may
not touch it. One file means one `absent` contract check
(``live-surfaces-are-read-only``) covers both, and it is the check that would
fail the moment somebody adds a convenience that mutates. Every lookup below is
a search, a browse or a stored field read.

THE GATE IS NOT OPTIONAL AND IT IS NOT IN THE BROWSER
-----------------------------------------------------
Live missions exist ONLY for the demo world. The frontend hides the mission for
everybody else, and that is decoration: ``_live_gate`` re-asks the question on
the server for every predicate call, and a caller who is not in
``pb_demo.group_payobook_demo``, or whose company is not the demo company, is
refused with a note that says why rather than with a silent False.

The demo company is identified by NAME. There is no ``is_demo`` on res.company
(pb_demo/models/demo_catalog.py:25 is the single declaration of that name), so
this is the honest test rather than the tidy one.
"""
from odoo import api, fields, models

DEMO_GROUP = 'pb_demo.group_payobook_demo'
DEMO_COMPANY_NAME = 'Payobook Vietnam JSC'

# The one open month in the demo world (pb_demo/models/demo_history.py:22-26:
# April and May are done and locked, June is left draft for exactly this).
JUNE_START = '2026-06-01'
JUNE_END = '2026-06-30'

# ---------------------------------------------------------------- the notes
# EVERY SENTENCE A LEARNER READS FROM THIS FILE IS A RECORD, not a literal.
#
# It used to be a `_B(en, vi)` dict literal per message, which was bilingual and
# still wrong: a Python dict is invisible to the .po tooling, so a translator
# never sees it, a reviewer cannot diff it against the rest of the module, and
# the one surface where the Coach speaks from CODE rather than from content
# drifts away from the twelve hundred strings that do not. The strings now live
# in `learn.string` under `live.*`, are generated from
# docs/tutorial_poc/author/data.js like everything else, and reach vi_VN.po by
# the same path.
#
# What stays in Python is COMPOSITION and nothing else: `%(count)s payslips
# computed for %(division)s` is interpolated here, into a template written
# there. A sentence is content; deciding which sentence, and with which
# numbers, is code.
def _note(env, key, **params):
    """One `live.*` chrome string, in BOTH languages, interpolated.

    Read twice under two language contexts because the whole module carries
    both and lets the reader choose — the same reason learn.string exists at
    all (see its docstring). A missing key degrades to the key itself rather
    than to an empty bubble: a learner who sees `live.noRun` can report it,
    and a learner who sees nothing cannot.
    """
    out = {}
    for lang, tag in (('en_US', 'en'), ('vi_VN', 'vi')):
        # sudo on OUR OWN content table, never on a product model. Every read
        # of the product in this file is done as the user (see _my_june_run);
        # a UI string failing on an access rule would take the whole bundle
        # down for a message that is not a secret.
        rec = env['learn.string'].sudo().with_context(lang=lang).search(
            [('key', '=', 'live.%s' % key)], limit=1)
        text = rec.value if rec else 'live.%s' % key
        if params:
            try:
                text = text % params
            except (KeyError, ValueError, TypeError):
                # A template whose placeholders were edited away must not take
                # the runner down with it.
                pass
        out[tag] = text
    return out


# ---------------------------------------------------------------- the gate
def _live_gate(env):
    """None when this session may run a live mission, else the refusal."""
    user = env.user
    try:
        in_group = user.has_group(DEMO_GROUP)
    except Exception:                                        # noqa: BLE001
        in_group = False
    if not in_group:
        return {'ok': False, 'note': _note(env, 'notDemo')}
    # The ACTIVE company only, not the union of everything the user may switch
    # to. The refusal says "your session is somewhere else", and a union would
    # make that sentence false for a user who merely HAS the demo company in
    # their list while working in another — the predicate would then pass while
    # the screen in front of them belonged to a different company entirely.
    if env.company.name != DEMO_COMPANY_NAME:
        return {'ok': False, 'note': _note(env, 'notDemo')}
    return None


# --------------------------------------------------------------- lookups
def _my_division(env):
    """The division this demo user owns. READ ONLY — it does not assign one.

    Assignment belongs to pb_demo: at signup, and lazily when the user opens
    Run Payroll (demo_payrun.get_defaults). Doing it here instead would put a
    field update inside the predicate path and cost this file the one property
    that makes it safe to call from a poll loop. A user with no assignment gets
    the `live.noDivision` note, which is exactly the instruction that causes one.
    """
    user = env.user
    if not hasattr(user, 'pb_demo_division'):
        # pb_demo is not installed on this database. Nothing to look at, and
        # saying so beats a traceback.
        return ''
    return user.pb_demo_division or ''


def _my_june_run(env):
    """The run THIS user created for their own division in June 2026.

    Three scopes, and the third one is the load-bearing one:

      is_demo + June dates   the one open month in the demo world.
      pb_division            their assignment. Computed and STORED by
                             pb_payruns from the first payslip's formula
                             config (hr_payslip_run.py:106-125), so it is only
                             populated once the run HAS slips — which is why
                             `june_run_computed` counts slips as well.
      create_uid == me       THE CAPSTONE'S HONESTY. The demo generator seeds
                             an open June run for every division before anybody
                             signs up. Without this clause a prospect would
                             open the mission and watch step one tick itself
                             green off somebody else's record — the mission
                             would congratulate them for work they had not
                             done, which is worse than not shipping it.

    No sudo: the demo user's record rules already grant read across the demo
    world (pb_demo/security/pb_demo_security.xml:23-32), and the gate has
    already established that this IS a demo user. Reading as themselves means
    the predicate can never see further than the screen they are looking at.
    """
    division = _my_division(env)
    if not division:
        return env['hr.payslip.run'].browse()
    return env['hr.payslip.run'].search([
        ('is_demo', '=', True),
        ('date_start', '>=', JUNE_START),
        ('date_end', '<=', JUNE_END),
        ('pb_division', '=', division),
        ('create_uid', '=', env.uid),
    ], order='id desc', limit=1)


_STATE_KEY = {
    'draft': 'stateDraft', 'level0': 'stateLevel0', 'level1': 'stateLevel1',
    'level2': 'stateLevel2', 'done': 'stateDone',
}


def _state_note(env, run):
    key = _STATE_KEY.get(run.state)
    if not key:
        # An unmapped state is a product change, and echoing the raw key is the
        # honest thing to do: it names what to go and look at.
        raw = run.state or '—'
        return {'en': raw, 'vi': raw}
    return _note(env, key)


def _at_least(run, states):
    return bool(run) and run.state in states


# ----------------------------------------------------------- predicates
# Every one of these LOOKS. None of them acts, and none of them may: the mission
# instructs the learner to press the product's own buttons, and then verifies
# what the product did. That separation is the whole reason a live mission is
# safe to ship.
def _p_june_run_computed(env):
    run = _my_june_run(env)
    if not run:
        return {'ok': False, 'note': _note(env, 'noRun')}
    count = env['hr.payslip'].search_count([('payslip_run_id', '=', run.id)])
    if not count:
        return {'ok': False, 'note': _note(env, 'noSlips')}
    # pb_division_label is a plain Char computed from the division KEY
    # (hr_payslip_run.py:106-125) — English words either way, and not
    # translatable, so it interpolates identically into both templates. Noted
    # rather than worked around: inventing a translation here would be inventing
    # a product string.
    return {'ok': True, 'note': _note(
        env, 'computed', count=count,
        division=run.pb_division_label or run.name)}


def _p_june_run_submitted(env):
    run = _my_june_run(env)
    if not run:
        return {'ok': False, 'note': _note(env, 'noRun')}
    if not _at_least(run, ('level0', 'level1', 'level2', 'done')):
        return {'ok': False, 'note': _note(env, 'stillDraft')}
    return {'ok': True, 'note': _state_note(env, run)}


def _p_june_run_officer_done(env):
    run = _my_june_run(env)
    if not run:
        return {'ok': False, 'note': _note(env, 'noRun')}
    if not _at_least(run, ('level1', 'level2', 'done')):
        return {'ok': False, 'note': _note(env, 'notPastOfficer')}
    return {'ok': True, 'note': _state_note(env, run)}


def _p_june_run_done(env):
    run = _my_june_run(env)
    if not run:
        return {'ok': False, 'note': _note(env, 'noRun')}
    if run.state != 'done':
        return {'ok': False, 'note': _state_note(env, run)}
    return {'ok': True, 'note': _note(env, 'allGatesDone')}


LIVE_PREDICATES = {
    'june_run_computed': _p_june_run_computed,
    'june_run_submitted': _p_june_run_submitted,
    'june_run_officer_done': _p_june_run_officer_done,
    'june_run_done': _p_june_run_done,
}


# --------------------------------------------------------- live values
def _v_division_name(env):
    user = env.user
    return user._pb_demo_division_label() if hasattr(user, 'pb_demo_division') else None


def _v_june_run_state(env):
    run = _my_june_run(env)
    if not run:
        return None
    lang = (env.context.get('lang') or env.user.lang or 'en_US')
    note = _state_note(env, run)
    return note['vi'] if lang.startswith('vi') else note['en']


def _v_active_policy_rates(env):
    """The employee / employer split on the policy actually in force — the same
    latest-effective-active rule the statutory cockpit applies."""
    if 'vietnam.insurance.policy' not in env:
        return None
    # ('active', '=', True) EXPLICITLY, exactly as pb_statutory.py:57 writes
    # it. The ORM's active_test would usually do it, but a caller with
    # active_test=False in context would otherwise get a different policy here
    # than the cockpit shows — and the whole value of this answer is that it
    # says what the screen says.
    policy = env['vietnam.insurance.policy'].search(
        [('company_id', 'in', env.companies.ids or [env.company.id]),
         ('active', '=', True)], order='effective_date desc', limit=1)
    if not policy:
        return None
    # A rate is a DECIMAL, and Vietnamese writes decimals with a comma. '%g'
    # gave a Vietnamese reader "17.5%" inside a Vietnamese sentence — the same
    # class of leak as printing money without grouping for the reader's
    # language, one separator further in.
    lang = (env.context.get('lang') or env.user.lang or 'en_US')
    def rate(v):
        # Normalise -0.0 and stray float dust before formatting: '%g' on a
        # value that rounds to zero can otherwise print "-0".
        text = '%g' % (round(v or 0.0, 4) + 0.0)
        if text == '-0':
            text = '0'
        return text.replace('.', ',') if lang.startswith('vi') else text

    def pair(a, b):
        return '%s%% / %s%%' % (rate(a), rate(b))
    return 'BHXH %s · BHYT %s · BHTN %s' % (
        pair(policy.si_employee_rate, policy.si_employer_rate),
        pair(policy.hi_employee_rate, policy.hi_employer_rate),
        pair(policy.ui_employee_rate, policy.ui_employer_rate))


# THREE KEYS ARE DELIBERATELY ABSENT. june_net_total, flagged_count and
# pit_relief were written, implemented and consumed by nothing — a whitelist
# entry no sentence uses is a read path with no reader, and flagged_count in
# particular reached into another cockpit's SQL aggregate to define a word this
# module does not otherwise own. They come back when content needs them, with
# the content in the same commit.
LIVE_VALUES = {
    'june_run_state': _v_june_run_state,
    'active_policy_rates': _v_active_policy_rates,
    'division_name': _v_division_name,
}

# `{{live:key}}`. Deliberately the same shape as the tenant slots, and
# deliberately a different namespace: a slot is a fact a company types in once,
# and a live value is read from the database on every render.
TOKEN = 'live:'


class LearnLive(models.AbstractModel):
    """Read-only window onto the running system.

    Abstract on purpose: there is nothing to store. It exists so the frontend
    and the answer path have ONE door to values that come from the product, and
    so that door can be audited in one place.
    """
    _name = 'learn.live'
    _description = 'Learn live values and capstone predicates'

    # -- notes ------------------------------------------------------------
    @api.model
    def note(self, key, **params):
        """A `live.*` chrome string in both languages. The one door other
        models use, so there is exactly one place these sentences come from."""
        return _note(self.env, key, **params)

    # -- the gate ---------------------------------------------------------
    @api.model
    def gate_open(self):
        """True when this session may run a live capstone at all.

        The frontend asks once, to decide what to DRAW. It is not a
        permission: `check` re-asks on every call, so a browser that lied to
        itself gets a mission whose steps never complete — not a live action it
        should not have had.
        """
        return _live_gate(self.env) is None

    # -- predicates -------------------------------------------------------
    @api.model
    def check(self, key):
        """Run one capstone predicate. Always gated, never trusting the caller."""
        refused = _live_gate(self.env)
        if refused:
            return refused
        predicate = LIVE_PREDICATES.get(key)
        if not predicate:
            # An unknown check is a content bug, and it must not read as a pass.
            return {'ok': False, 'note': _note(self.env, 'noSuchCheck', key=key)}
        if not _my_division(self.env):
            return {'ok': False, 'note': _note(self.env, 'noDivision')}
        return predicate(self.env)

    # -- values -----------------------------------------------------------
    @api.model
    def values(self, keys):
        """{key: rendered string} for the keys that resolve.

        GATED IN FULL, exactly like the predicates. Live values are a demo-world
        affordance in Phase B: outside it every key is omitted, `render` falls
        back to the authored sentence, and a real tenant reads the static text
        it has always read. That is the DESIGNED behaviour, not a degradation —
        the two live sites both ship a fallback that says the same thing without
        the live figure.

        Absent keys are OMITTED rather than blanked, so a caller can tell 'no
        answer' from 'the answer is empty'.
        """
        if _live_gate(self.env) is not None:
            return {}
        out = {}
        for key in keys or []:
            fn = LIVE_VALUES.get(key)
            if not fn:
                continue
            try:
                value = fn(self.env)
            except Exception:                                # noqa: BLE001
                # A live value that raises must degrade to the authored
                # sentence, never to a broken answer.
                value = None
            if value not in (None, ''):
                out[key] = value
        return out

    # -- rendering --------------------------------------------------------
    @api.model
    def render(self, text, fallback=''):
        """Substitute {{live:key}} in `text`, or return `fallback` whole.

        ALL OR NOTHING, and that is the point. A half-resolved sentence reads
        as a fact with a hole in it — "your run is at" — which is worse than the
        static sentence the author already wrote. So either every key in the
        text resolves and the text is rendered, or the authored fallback is
        shown instead and nothing live is claimed at all.
        """
        if not text or ('{{%s' % TOKEN) not in text:
            return text
        keys = self._tokens(text)
        resolved = self.values(keys)
        if any(k not in resolved for k in keys):
            return fallback or ''
        for key in keys:
            text = text.replace('{{%s%s}}' % (TOKEN, key), resolved[key])
        return text

    @api.model
    def _tokens(self, text):
        import re
        return re.findall(r'\{\{%s([a-z_]+)\}\}' % TOKEN, text or '')
