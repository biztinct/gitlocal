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

# Bilingual because everything a learner reads in this module is. A note that
# arrived in one language only would be the single string in the system that
# stops following the EN/VI toggle.
def _B(en, vi):
    return {'en': en, 'vi': vi}


_NOT_DEMO = _B(
    "Live missions need the demo world. This one runs against real records in "
    "the Payobook demo company, and your session is somewhere else.",
    "Nhiệm vụ trực tiếp cần môi trường demo. Nhiệm vụ này chạy trên dữ liệu thật "
    "của công ty demo Payobook, còn phiên của bạn đang ở nơi khác.")

_NO_DIVISION = _B(
    "No division has been assigned to you yet. Open Run Payroll once and one "
    "will be — each demo account drives its own division's June run.",
    "Bạn chưa được gán bộ phận nào. Hãy mở Chạy bảng lương một lần là sẽ có — "
    "mỗi tài khoản demo tự chạy đợt lương tháng 6 của bộ phận mình.")

_NO_RUN = _B(
    "No June run for your division yet. Open Run Payroll and compute it — the "
    "wizard already has your division and the period selected.",
    "Chưa có đợt lương tháng 6 cho bộ phận của bạn. Hãy mở Chạy bảng lương và "
    "tính — trình hướng dẫn đã chọn sẵn bộ phận và kỳ lương của bạn.")


# ---------------------------------------------------------------- the gate
def _live_gate(env):
    """None when this session may run a live mission, else the refusal."""
    user = env.user
    try:
        in_group = user.has_group(DEMO_GROUP)
    except Exception:                                        # noqa: BLE001
        in_group = False
    if not in_group:
        return {'ok': False, 'note': _NOT_DEMO}
    # The ACTIVE company only, not the union of everything the user may switch
    # to. The refusal says "your session is somewhere else", and a union would
    # make that sentence false for a user who merely HAS the demo company in
    # their list while working in another — the predicate would then pass while
    # the screen in front of them belonged to a different company entirely.
    if env.company.name != DEMO_COMPANY_NAME:
        return {'ok': False, 'note': _NOT_DEMO}
    return None


# --------------------------------------------------------------- lookups
def _my_division(env):
    """The division this demo user owns. READ ONLY — it does not assign one.

    Assignment belongs to pb_demo: at signup, and lazily when the user opens
    Run Payroll (demo_payrun.get_defaults). Doing it here instead would put a
    field update inside the predicate path and cost this file the one property
    that makes it safe to call from a poll loop. A user with no assignment gets
    `_NO_DIVISION`, whose note is exactly the instruction that causes one.
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


def _state_note(run):
    labels = {
        'draft': _B("Draft", "Nháp"),
        'level0': _B("Payroll Officer pending", "Chờ Chuyên viên tính lương"),
        'level1': _B("HR review", "HR soát xét"),
        'level2': _B("Finance approval", "Tài chính phê duyệt"),
        'done': _B("Done", "Hoàn tất"),
    }
    return labels.get(run.state, _B(run.state or '—', run.state or '—'))


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
        return {'ok': False, 'note': _NO_RUN}
    count = env['hr.payslip'].search_count([('payslip_run_id', '=', run.id)])
    if not count:
        return {'ok': False, 'note': _B(
            "The run exists but has no payslips yet. Press Compute in the wizard.",
            "Đợt lương đã có nhưng chưa có phiếu nào. Hãy bấm Tính trong trình hướng dẫn.")}
    return {'ok': True, 'note': _B(
        "%s payslips computed for %s." % (count, run.pb_division_label or run.name),
        "Đã tính %s phiếu lương cho %s." % (count, run.pb_division_label or run.name))}


def _p_june_run_submitted(env):
    run = _my_june_run(env)
    if not run:
        return {'ok': False, 'note': _NO_RUN}
    if not _at_least(run, ('level0', 'level1', 'level2', 'done')):
        return {'ok': False, 'note': _B(
            "Still in draft. Submit the run for approval from the Pay Runs board.",
            "Vẫn ở trạng thái Nháp. Hãy trình đợt lương lên phê duyệt từ bảng Đợt tính lương.")}
    return {'ok': True, 'note': _state_note(run)}


def _p_june_run_officer_done(env):
    run = _my_june_run(env)
    if not run:
        return {'ok': False, 'note': _NO_RUN}
    if not _at_least(run, ('level1', 'level2', 'done')):
        return {'ok': False, 'note': _B(
            "Not past the Payroll Officer gate yet.",
            "Chưa qua cổng Chuyên viên tính lương.")}
    return {'ok': True, 'note': _state_note(run)}


def _p_june_run_done(env):
    run = _my_june_run(env)
    if not run:
        return {'ok': False, 'note': _NO_RUN}
    if run.state != 'done':
        return {'ok': False, 'note': _state_note(run)}
    return {'ok': True, 'note': _B(
        "Done — every gate has said yes.", "Hoàn tất — mọi cổng đã đồng ý.")}


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
    note = _state_note(run)
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
    def pair(a, b):
        return '%s%% / %s%%' % (('%g' % a), ('%g' % b))
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
            return {'ok': False, 'note': _B(
                "There is no check called '%s'." % key,
                "Không có phép kiểm tra nào tên '%s'." % key)}
        if not _my_division(self.env):
            return {'ok': False, 'note': _NO_DIVISION}
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
