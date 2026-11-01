# -*- coding: utf-8 -*-
"""`pb.rnr` — the Praise lens's only server surface.

THE QUESTION THIS BOARD ANSWERS: who has been noticed lately, who is waiting on
somebody, and what did we do about it. So the four numbers across the top are
the four places a piece of praise can be — written this month, waiting on a
manager, waiting on HR, and paid for this quarter — and a row is one story with
its state on it.

The roll-up is the hero. Picking a quarter's winners out of a ranked table of
who colleagues actually named, with the money consequence spelled out in a
sentence before anything is written, is the thing this module exists for.

Every employee attribute is read AS THE SYSTEM (R56): reading one field of an
`hr.employee` prefetches forty and about forty of those sit behind payroll
groups a recognition reader has no reason to hold. The security boundary is the
search that found the record, and `_can_read()` above it.
"""

import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .rnr_common import (
    CYCLE_STATE_LABEL, GROUP_MANAGER, GROUP_USER, NOMINATION_STATE_LABEL,
    OUTCOME_LABEL, P_ANNIV_MAIL, P_DIGEST_MAIL, P_DIGEST_TEST, P_MANAGER_MAIL,
    P_THANKS_MAIL, excerpt, flag, fold, initials, param,
)

_logger = logging.getLogger(__name__)

BOARD_LIMIT = 300
HISTORY_LIMIT = 12


def _refusal():
    return {
        'allowed': False, 'can_write': False, 'can_review': False,
        'rows': [], 'kpis': {}, 'values': [], 'cycles': [], 'states': [],
        'outcomes': [], 'celebrations': [], 'celebration_total': 0,
        'total': 0, 'capped': False,
        'currency': '', 'switches': {},
        'why': _("Recognition is looked after by the people who run it. This "
                 "screen is not part of the general HR permissions — somebody "
                 "has to add you to it by name."),
    }


#: Stories per page on the filtered list ("Show N more" brings the next).
PAGE_SIZE = 60
#: Sections whose values are people (or posters) a recognition reader may not
#: be able to read by name without HR rights: counted as the reader, LABELLED
#: as the system (R56), exactly as `_row` reads the names on the list.
SUDO_LABELS = ('value', 'nominee', 'nominator', 'department', 'cycle')
#: The four steps of the strip, as filters on `state` (a story is at exactly
#: one step: "Decided" holds both what was agreed and what was turned down).
STEP_STATES = {
    'draft': ['draft'],
    'submitted': ['submitted'],
    'manager': ['manager'],
    'decided': ['done', 'refused'],
}


class PbRnr(models.AbstractModel):
    _name = 'pb.rnr'
    _description = 'Payobook recognition cockpit data'
    # The shared filter panel (pb_filter_kit, FILTER wave 4). The nomination
    # search is never sudoed: every count is counted under the reader's own
    # record rules, like the list.
    _inherit = ['pb.filter.mixin']

    # ------------------------------------------------------------- the gates
    @api.model
    def _safe(self, fn, default=0):
        """Every independent probe gets its OWN try/except — never a shared
        one, or the first failure takes four numbers down with it."""
        try:
            return fn()
        except Exception as e:              # noqa: BLE001
            _logger.debug('recognition metric failed: %s', e)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        return bool(self.env.su or user._is_admin()
                    or user.has_group(GROUP_USER)
                    or user.has_group(GROUP_MANAGER))

    @api.model
    def _can_review(self):
        return bool(self.env.su or self.env.user._is_admin()
                    or self.env.user.has_group(GROUP_MANAGER))

    @api.model
    def _require_read(self):
        if not self._can_read():
            raise AccessError(_refusal()['why'])
        return True

    @api.model
    def _require_review(self):
        if not self._can_review():
            raise AccessError(_(
                "Deciding a piece of praise — and any money with it — is done "
                "by the people who run recognition."))
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def get_board(self):
        if not self._can_read():
            return _refusal()
        Nom = self.env['pb.rnr.nomination']
        recs = Nom.search([
            '|', ('company_id', '=', False),
            ('company_id', 'in', self.env.companies.ids),
        ], order='id desc', limit=BOARD_LIMIT + 1)
        capped = len(recs) > BOARD_LIMIT
        recs = recs[:BOARD_LIMIT]
        rows = [self._row(rec) for rec in recs]
        today = date.today()
        this_month = today.replace(day=1).isoformat()[:7]
        quarter_start = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
        return {
            'allowed': True,
            'can_write': True,
            'can_review': self._can_review(),
            'rows': rows,
            'total': len(rows),
            'capped': capped,
            'currency': self.env.company.currency_id.symbol or '',
            'values': self.values_list(),
            'cycles': self._cycles(),
            'states': [{'key': k, 'label': v}
                       for k, v in NOMINATION_STATE_LABEL.items()],
            'outcomes': [{'key': k, 'label': v}
                         for k, v in OUTCOME_LABEL.items()],
            'celebrations': self._safe(
                lambda: self.env['pb.rnr.celebration'].upcoming_celebrations(
                    days=14), []),
            # The TRUE number, not the length of a capped strip (see
            # `pb.rnr.celebration.count_upcoming`).
            'celebration_total': self._safe(
                lambda: self.env['pb.rnr.celebration'].count_upcoming(
                    days=14), 0),
            'switches': self._switches(),
            'kpis': {
                'this_month': len([r for r in rows
                                   if (r['written'] or '')[:7] == this_month]),
                'with_manager': len([r for r in rows
                                     if r['state'] == 'submitted']),
                'with_hr': len([r for r in rows if r['state'] == 'manager']),
                'awarded_qtd': len([
                    r for r in rows
                    if r['outcome'] == 'awarded'
                    and r['decided'] and r['decided'][:10] >= quarter_start.isoformat()]),
                'awarded_amount': sum(
                    r['amount'] for r in rows
                    if r['outcome'] == 'awarded'
                    and r['decided'] and r['decided'][:10] >= quarter_start.isoformat()),
            },
            'why': '',
        }

    # ------------------------------------------------------- the filter panel
    # The board used to load the newest 300 stories and filter them in the
    # browser; the panel now counts on the server over every story this
    # person may read and the list comes one page at a time. `get_board`
    # stays as it was for anything else that reads it (R4).

    def _pbf_model(self):
        return 'pb.rnr.nomination'

    def _pbf_screen(self):
        return 'praise'

    def _pbf_base_domain(self):
        return ['|', ('company_id', '=', False),
                ('company_id', 'in', self.env.companies.ids)]

    def _pbf_search_fields(self):
        return ['nominee_id.name', 'nominator_id.name', 'story']

    def _pbf_layout_extra(self):
        return {'currency': self.env.company.currency_id.symbol or ''}

    def _pbf_sorts(self):
        return [
            {'key': 'newest', 'label': _('Newest first'), 'order': 'id desc'},
            {'key': 'oldest', 'label': _('Oldest first'), 'order': 'id asc'},
            {'key': 'decided', 'label': _('Most recently decided'),
             'order': 'decided_at desc nulls last, id desc'},
            {'key': 'amount', 'label': _('Biggest award first'),
             'order': 'award_amount desc nulls last, id desc'},
        ]

    @api.model
    def _quarter_start(self):
        today = fields.Date.context_today(self)
        return date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)

    def _pbf_spec(self):
        return [
            # ---- pinned: where it is, which value, who it is about
            {'key': 'step', 'label': _('Where it is'), 'icon': 'listChecks',
             'group': 'other', 'type': 'choice', 'pinned': True,
             'options': [
                 {'value': 'draft', 'label': _('Being written'), 'tone': 'slate',
                  'domain': [('state', '=', 'draft')]},
                 {'value': 'submitted', 'label': _('With their manager'), 'tone': 'amber',
                  'domain': [('state', '=', 'submitted')]},
                 {'value': 'manager', 'label': _('With HR'), 'tone': 'amber',
                  'domain': [('state', '=', 'manager')]},
                 {'value': 'done', 'label': _('Decided'), 'tone': 'green',
                  'domain': [('state', '=', 'done')]},
                 {'value': 'refused', 'label': _('Not this time'), 'tone': 'rose',
                  'domain': [('state', '=', 'refused')]},
             ]},
            {'key': 'value', 'label': _('Value'), 'icon': 'shieldCheck',
             'group': 'other', 'type': 'many2one', 'path': 'value_id', 'pinned': True},
            {'key': 'nominee', 'label': _('Who it is about'), 'icon': 'user',
             'group': 'people', 'type': 'many2one', 'path': 'nominee_id', 'pinned': True},
            # ---- more filters
            {'key': 'outcome', 'label': _('What was decided'), 'icon': 'award',
             'group': 'other', 'type': 'selection', 'path': 'outcome',
             'none_label': _('Not decided yet')},
            {'key': 'nominator', 'label': _('Who wrote it'), 'icon': 'userCheck',
             'group': 'people', 'type': 'many2one', 'path': 'nominator_id'},
            {'key': 'department', 'label': _('Their department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'nominee_id.department_id',
             'none_label': _('No department')},
            {'key': 'cycle', 'label': _('Quarter'), 'icon': 'calendar',
             'group': 'dates', 'type': 'many2one', 'path': 'cycle_id',
             'none_label': _('No quarter')},
            {'key': 'written', 'label': _('Written'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'submitted_at',
             'presets': 'past', 'none_label': _('Not sent yet')},
            {'key': 'decided', 'label': _('Decided'), 'icon': 'calendarClock',
             'group': 'dates', 'type': 'date', 'path': 'decided_at',
             'presets': 'past', 'none_label': _('Not decided yet')},
            {'key': 'winner', 'label': _('Quarter winner'), 'icon': 'award',
             'group': 'other', 'type': 'choice',
             'options': [
                 {'value': 'yes', 'label': _('Chosen for the quarter'), 'tone': 'green',
                  'domain': [('is_winner', '=', True)]},
                 {'value': 'no', 'label': _('Not chosen'), 'tone': 'slate',
                  'domain': [('is_winner', '=', False)]},
             ]},
            {'key': 'public', 'label': _('Who can see it'), 'icon': 'eye',
             'group': 'other', 'type': 'choice',
             'options': [
                 {'value': 'yes', 'label': _('Shared with the company'), 'tone': 'blue',
                  'domain': [('public', '=', True)]},
                 {'value': 'no', 'label': _('Kept private'), 'tone': 'slate',
                  'domain': [('public', '=', False)]},
             ]},
            {'key': 'amount', 'label': _('Award'), 'icon': 'banknote',
             'group': 'pay', 'type': 'number', 'path': 'award_amount', 'unit': 'money'},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All praise'), 'icon': 'award', 'filters': {}},
            {'key': 'manager', 'label': _('Waiting on a manager'),
             'filters': {'step': ['submitted']}},
            {'key': 'hr', 'label': _('Waiting on HR'),
             'filters': {'step': ['manager']}},
            {'key': 'refused', 'label': _('Not this time'),
             'filters': {'step': ['refused']}},
            {'key': 'money', 'label': _('Given money this quarter'),
             'filters': {'outcome': ['awarded'],
                         'decided': {'from': fields.Date.to_string(self._quarter_start())}}},
            {'key': 'winners', 'label': _('Quarter winners'),
             'filters': {'winner': ['yes']}},
        ]

    @api.model
    def _pbf_list_values(self, s, domain, selected=None):
        """People and posters: counted as the reader, named as the system."""
        if s.get('key') not in SUDO_LABELS or s.get('type') != 'many2one':
            return super()._pbf_list_values(s, domain, selected)
        none_label = s.get('none_label') or _('Not set')
        rows = []
        for value, count in self._pbf_records()._read_group(domain, [s['path']], ['__count']):
            rows.append({'v': value.id if value else False,
                         'label': (value.sudo().display_name or none_label) if value else none_label,
                         'n': count})
        rows.sort(key=lambda r: (r['v'] is False, -r['n'], (r['label'] or '').lower()))
        more = len(rows) > 300
        rows = rows[:300]
        have = {r['v'] for r in rows}
        missing = [v for v in (selected or []) if v not in have]
        if missing:
            rows.extend(self._pbf_label_values(s, missing))
        return rows, more

    @api.model
    def _pbf_label_values(self, s, values):
        if s.get('key') in SUDO_LABELS:
            # labels only; nothing is counted here
            return super(PbRnr, self.sudo())._pbf_label_values(s, values)
        return super()._pbf_label_values(s, values)

    @api.model
    def pbf_layout(self):
        if not self._can_read():
            return {'refused': _refusal()['why']}
        return super().pbf_layout()

    @api.model
    def pbf_counts(self, filters=None, search=None, keys=None, **kw):
        # **kw rides every kit argument through (kit 1.3.0 added `views`).
        self._require_read()
        return super().pbf_counts(filters=filters, search=search, keys=keys, **kw)

    @api.model
    def pbf_find_values(self, key, query, filters=None, search=None):
        self._require_read()
        return super().pbf_find_values(key, query, filters=filters, search=search)

    @api.model
    def get_head(self):
        """Everything on the board except the list: the gates, the numbers
        line (counted over every story this person may read, whatever is
        filtered), the values, the quarters and the switches."""
        if not self._can_read():
            return _refusal()
        Nom = self.env['pb.rnr.nomination']
        base = self._pbf_base_domain()
        today = fields.Date.context_today(self)
        month = fields.Date.to_string(today.replace(day=1))
        quarter = fields.Date.to_string(self._quarter_start())

        def n(extra):
            return self._safe(lambda: Nom.search_count(base + extra), 0)

        awarded = base + [('outcome', '=', 'awarded'), ('decided_at', '>=', quarter)]
        return {
            'allowed': True,
            'can_write': True,
            'can_review': self._can_review(),
            'currency': self.env.company.currency_id.symbol or '',
            'values': self.values_list(),
            'cycles': self._cycles(),
            'states': [{'key': k, 'label': v}
                       for k, v in NOMINATION_STATE_LABEL.items()],
            'outcomes': [{'key': k, 'label': v}
                         for k, v in OUTCOME_LABEL.items()],
            'celebrations': self._safe(
                lambda: self.env['pb.rnr.celebration'].upcoming_celebrations(
                    days=14), []),
            'celebration_total': self._safe(
                lambda: self.env['pb.rnr.celebration'].count_upcoming(
                    days=14), 0),
            'switches': self._switches(),
            'quarter_start': quarter,
            'kpis': {
                'all': n([]),
                'this_month': n([('submitted_at', '>=', month)]),
                'with_manager': n([('state', '=', 'submitted')]),
                'with_hr': n([('state', '=', 'manager')]),
                'refused': n([('state', '=', 'refused')]),
                'awarded_qtd': self._safe(lambda: Nom.search_count(awarded), 0),
            },
            'why': '',
        }

    @api.model
    def get_praise_page(self, filters=None, search=None, sort=None, offset=0,
                        limit=PAGE_SIZE):
        """One page of stories for the panel's state, and the strip's four
        step counts said about the same filters (every filter but the step
        one, so a step never zeroes its neighbours)."""
        self._require_read()
        Nom = self.env['pb.rnr.nomination']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        recs = Nom.search(domain, order=self.pbf_order(sort) or 'id desc',
                          offset=offset, limit=limit)
        rows = []
        for rec in recs:
            try:
                rows.append(self._row(rec))
            except Exception as ex:  # noqa: BLE001 — one bad row never blanks the list
                _logger.debug("Praise row failed: %s", ex)
        out = {'rows': rows, 'total': Nom.search_count(domain), 'offset': offset}
        if not offset:
            by_state = {}
            try:
                for state, count in Nom._read_group(
                        self.pbf_domain(filters, search, skip='step'), ['state'], ['__count']):
                    by_state[state] = count
            except Exception as ex:  # noqa: BLE001
                _logger.info("Praise step counts failed: %s", ex)
            out['steps'] = {k: sum(by_state.get(s, 0) for s in states)
                            for k, states in STEP_STATES.items()}
            out['refused'] = by_state.get('refused', 0)
        return out

    @api.model
    def _switches(self):
        """Which way every send is set, said on the screen.

        A switch that is off and does not SAY so is reported as broken (R54), so
        the lens prints all five rather than making somebody guess why their
        test email never arrived.
        """
        return {
            'digest': flag(self.env, P_DIGEST_MAIL),
            'digest_test': (param(self.env, P_DIGEST_TEST) or '').strip(),
            'celebrations': flag(self.env, P_ANNIV_MAIL),
            'manager_week': flag(self.env, P_MANAGER_MAIL),
            'thanks': flag(self.env, P_THANKS_MAIL),
        }

    @api.model
    def _row(self, rec):
        Nom = self.env['pb.rnr.nomination']
        nominee = Nom._person(rec.nominee_id)
        nominator = Nom._person(rec.nominator_id)
        val = rec.value_id.sudo()
        return {
            'id': rec.id,
            'nominee': nominee.name or '',
            'nominee_id': nominee.id,
            'initials': initials(nominee.name or ''),
            'avatar': ('/web/image/hr.employee/%s/avatar_128' % nominee.id
                       if nominee else ''),
            'department': (nominee.department_id.name
                           if nominee and nominee.department_id else ''),
            'nominator': nominator.name or '',
            'value': val.name or '',
            'value_id': val.id,
            'color': val.color or 'primary',
            'icon': val.icon or 'award',
            'story': rec.story or '',
            'excerpt': excerpt(rec.story, 220),
            'state': rec.state or 'draft',
            'state_label': NOMINATION_STATE_LABEL.get(rec.state, ''),
            'outcome': rec.outcome or '',
            'outcome_label': OUTCOME_LABEL.get(rec.outcome, ''),
            'amount': rec.award_amount or 0.0,
            'currency': rec.currency_id.symbol or '',
            'public': bool(rec.public),
            'winner': bool(rec.is_winner),
            'cycle': rec.cycle_id.name if rec.cycle_id else '',
            'incentive_id': rec.incentive_id.id if rec.incentive_id else 0,
            'written': (fields.Datetime.to_string(rec.submitted_at)
                        or fields.Datetime.to_string(rec.create_date) or ''),
            'decided': fields.Datetime.to_string(rec.decided_at) or '',
            'note': rec.decision_note or '',
        }

    @api.model
    def values_list(self):
        """The values somebody may pick from. Read for everybody who reaches a
        nominate form, including the portal — a value is a poster, not a
        secret."""
        recs = self.env['pb.company.value'].sudo().search([
            ('active', '=', True),
            '|', ('company_id', '=', False),
            ('company_id', 'in', self.env.companies.ids),
        ], order='sequence, id')
        return [{'id': v.id, 'name': v.name or '', 'motto': v.motto or '',
                 'description': v.description or '',
                 'icon': v.icon or 'award', 'color': v.color or 'primary'}
                for v in recs]

    @api.model
    def _cycles(self):
        recs = self.env['pb.rnr.cycle'].sudo().search([
            '|', ('company_id', '=', False),
            ('company_id', 'in', self.env.companies.ids),
        ], order='date_from desc, id desc', limit=12)
        return [{'id': c.id, 'name': c.name or '',
                 'state': c.state, 'state_label': CYCLE_STATE_LABEL.get(c.state, ''),
                 'from': fields.Date.to_string(c.date_from) or '',
                 'to': fields.Date.to_string(c.date_to) or '',
                 'winners': len(c.top_ids)} for c in recs]

    # ------------------------------------------------------------ the writes
    @api.model
    def nominate(self, vals):
        """Write a piece of praise. The same call the portal makes.

        DELIBERATELY UNGATED beyond being signed in. Recognition that only the
        recognition team may start does not happen, because they were not in the
        room; the whole design is that a colleague writes it and two other
        people agree it. What the tiers guard is READING the board and DECIDING
        — not saying thank you.
        """
        return self._create_nomination(vals, self._me())

    @api.model
    def _me(self):
        """The acting person's own employee record, from the SESSION."""
        Emp = self.env['hr.employee'].sudo()
        emp = Emp.search([('user_id', '=', self.env.user.id),
                          ('company_id', '=', self.env.company.id)], limit=1)
        return emp or Emp.search([('user_id', '=', self.env.user.id)], limit=1)

    @api.model
    def _create_nomination(self, vals, nominator, submit=True):
        """The one place a nomination is born. Shared with the portal.

        The friendly refusals happen HERE, before the database's own constraint
        gets a chance to speak, because a Postgres message is not an answer.
        """
        vals = vals or {}
        nominee_id = int(vals.get('nominee_id') or 0)
        value_id = int(vals.get('value_id') or 0)
        story = (vals.get('story') or '').strip()
        if not nominee_id:
            raise UserError(_("Pick the colleague you want to thank."))
        if not value_id:
            raise UserError(_(
                "Pick the value this is an example of — it is what turns a "
                "thank-you into something the whole company can learn from."))
        if not story:
            raise UserError(_(
                "Write what actually happened. One real example is worth three "
                "adjectives, and it is the part everybody else will read."))
        if not nominator:
            raise UserError(_(
                "We could not work out which employee record is yours, so "
                "there is nobody to put on the praise. Ask HR to link your "
                "login to your employee record."))
        if nominee_id == nominator.id:
            raise UserError(_(
                "Praise goes to somebody else. Pick the colleague you want to "
                "say thank you to."))
        nominee = self.env['hr.employee'].sudo().browse(nominee_id).exists()
        if not nominee:
            raise UserError(_("That colleague could not be found."))
        # THE COMPANY TEST IS AGAINST THE SESSION, not against the writer's own
        # employee record. Reaching outside the companies you are signed in to
        # is the thing that must not happen; whether an administrator's own
        # `hr.employee` happens to sit in the empty company 1 (R16) is not a
        # fact about who they may thank.
        if nominee.company_id and self.env.companies.ids \
                and nominee.company_id.id not in self.env.companies.ids:
            raise UserError(_(
                "You can only thank a colleague in your own company."))
        rec = self.env['pb.rnr.nomination'].sudo().create({
            'nominee_id': nominee.id,
            'nominator_id': nominator.id,
            'value_id': value_id,
            'story': story,
            'public': bool(vals.get('public', True)),
            'company_id': (nominee.company_id or self.env.company).id,
        })
        if submit:
            rec.action_submit()
        return rec.id

    @api.model
    def employee_options(self, term=''):
        """Colleagues to pick from — ACTIVE, in the caller's own company, and
        never themselves.

        THE MATCH IS ACCENT-FOLDED AND THE SEARCH IS NOT `ilike`, and that is a
        fact about this database rather than a preference: Postgres has no
        `unaccent` extension here, so `ilike '%bui%'` does not find "Bùi" — and
        four and a half thousand of the five thousand people on this tenant have
        an accent in their name. Typing without diacritics is how a Vietnamese
        keyboard is used at speed, so a picker that only matches the accented
        spelling is a picker that finds nobody (R28, from the other direction).

        `search_read` of TWO COLUMNS rather than a `search` of records: reading
        one field of an `hr.employee` prefetches forty and about forty of those
        sit behind payroll groups (R56), so the whole-company scan is done over
        the two strings this needs and nothing is browsed at all.
        """
        Emp = self.env['hr.employee'].sudo()
        me = self._me()
        # THE COMPANIES THE SESSION IS IN, not the caller's own employee record.
        # An HR administrator's `hr.employee` sits in company 1 — the empty
        # shell the initial install left (R16) — so scoping the picker to it
        # offers an administrator nobody at all, which is exactly what happened
        # the first time this was tried. The cross-company rule is still
        # enforced, at the moment of writing, where it belongs
        # (`_create_nomination` compares nominee to nominator).
        domain = [('active', '=', True),
                  ('company_id', 'in', self.env.companies.ids)]
        if me:
            domain.append(('id', '!=', me.id))
        rows = Emp.search_read(domain, ['name', 'barcode', 'department_id'],
                               order='name')
        needle = fold(term or '')
        out = []
        for row in rows:
            if needle and needle not in fold(row.get('name') or '') \
                    and needle not in fold(row.get('barcode') or ''):
                continue
            dept = row.get('department_id')
            out.append({
                'id': row['id'], 'name': row.get('name') or '',
                'code': row.get('barcode') or '',
                'department': dept[1] if dept else '',
                'avatar': '/web/image/hr.employee/%s/avatar_128' % row['id'],
            })
            if len(out) >= 25:
                break
        return out

    # ------------------------------------------------------------- the moves
    @api.model
    def manager_agree(self, nomination_id, note=False):
        self._require_read()
        rec = self.env['pb.rnr.nomination'].browse(int(nomination_id))
        return rec.action_manager_agree(note=note or False)

    @api.model
    def recognise(self, nomination_id, amount=0.0, note=False):
        self._require_review()
        rec = self.env['pb.rnr.nomination'].browse(int(nomination_id))
        return rec.action_recognise(amount=amount or 0.0, note=note or False)

    @api.model
    def decline(self, nomination_id, note=False):
        self._require_read()
        rec = self.env['pb.rnr.nomination'].browse(int(nomination_id))
        return rec.action_decline(note=note or False)

    @api.model
    def set_public(self, nomination_id, public):
        """HR can take a story off the wall. It can never put one on that the
        writer asked to keep private — that switch belongs to them."""
        self._require_review()
        rec = self.env['pb.rnr.nomination'].browse(int(nomination_id))
        if public and not rec.public:
            raise UserError(_(
                "The colleague who wrote this asked for it to stay private. "
                "Ask them if they would like it on the wall."))
        rec.public = bool(public)
        return True

    @api.model
    def nominee_history(self, employee_id):
        """What else this person has been praised for. The review dialog shows
        it, because a decision made without it is a decision made blind."""
        self._require_read()
        Nom = self.env['pb.rnr.nomination']
        recs = Nom.sudo().search([
            ('nominee_id', '=', int(employee_id or 0)),
            ('state', '=', 'done'),
            ('outcome', 'in', ('recognised', 'awarded')),
        ], order='decided_at desc, id desc', limit=HISTORY_LIMIT)
        return [{
            'id': rec.id,
            'value': rec.value_id.sudo().name or '',
            'color': rec.value_id.sudo().color or 'primary',
            'excerpt': excerpt(rec.story, 140),
            'when': fields.Datetime.to_string(rec.decided_at) or '',
            'outcome': rec.outcome or '',
            'amount': rec.award_amount or 0.0,
        } for rec in recs]

    # ------------------------------------------------------------ the quarter
    @api.model
    def ensure_current_cycle(self):
        """The quarter we are in — found, or made.

        A screen whose main action is "roll up the quarter" must never open on
        "there are no quarters". The window is the calendar quarter, which is
        what everybody means by Q3 anyway.
        """
        self._require_read()
        today = fields.Date.context_today(self)
        q = (today.month - 1) // 3
        start = date(today.year, q * 3 + 1, 1)
        end_month = q * 3 + 3
        end = (date(today.year + 1, 1, 1) if end_month == 12
               else date(today.year, end_month + 1, 1))
        end = fields.Date.subtract(end, days=1)
        Cycle = self.env['pb.rnr.cycle']
        found = Cycle.sudo().search([('date_from', '=', start),
                                     ('date_to', '=', end)], limit=1)
        if not found:
            found = Cycle.sudo().create({
                'name': 'Q%s %s' % (q + 1, today.year),
                'date_from': start, 'date_to': end, 'state': 'open',
                'company_id': self.env.company.id,
            })
        return found.id

    @api.model
    def cycle_rollup(self, cycle_id=None):
        """The ranked table behind "who won this quarter"."""
        self._require_read()
        cid = int(cycle_id or 0) or self.ensure_current_cycle()
        cycle = self.env['pb.rnr.cycle'].sudo().browse(cid).exists()
        if not cycle:
            return {'ok': False, 'rows': [],
                    'problem': _("That quarter no longer exists.")}
        rows = cycle.roll_up()
        return {
            'ok': True,
            'problem': '' if rows else _(
                "Nobody has been recognised in this quarter yet. Once praise "
                "starts being agreed it is ranked here, and the winners are "
                "picked from the table rather than from memory."),
            'cycle': {'id': cycle.id, 'name': cycle.name or '',
                      'state': cycle.state,
                      'state_label': CYCLE_STATE_LABEL.get(cycle.state, ''),
                      'from': fields.Date.to_string(cycle.date_from) or '',
                      'to': fields.Date.to_string(cycle.date_to) or ''},
            'rows': rows,
            'currency': self.env.company.currency_id.symbol or '',
        }

    @api.model
    def pick_winners(self, cycle_id, picks):
        self._require_review()
        cycle = self.env['pb.rnr.cycle'].sudo().browse(
            int(cycle_id or 0)).exists()
        if not cycle:
            raise UserError(_("That quarter no longer exists."))
        return cycle.pick_winners(picks or [])

    @api.model
    def close_cycle(self, cycle_id):
        self._require_review()
        cycle = self.env['pb.rnr.cycle'].sudo().browse(
            int(cycle_id or 0)).exists()
        if not cycle:
            raise UserError(_("That quarter no longer exists."))
        cycle.action_close()
        return True

    # -------------------------------------------------------- the mood board
    @api.model
    def digest_preview(self, month=None):
        """The email, on screen, before anybody presses anything.

        The HTML is built server-side with every interpolated value escaped by
        QWeb itself, and the lens wraps it once with `markup()` — the narrow
        hatch R51 describes and the only place this module opens it.
        """
        self._require_read()
        Digest = self.env['pb.rnr.digest']
        payload = Digest.build(month=month or None)
        return {
            'html': Digest.render(payload=payload),
            'month': payload['month_label'],
            'stories': len(payload['stories']),
            'joiners': len(payload['joiners']),
            'celebrations': len(payload['celebrations']),
            'switches': self._switches(),
        }

    @api.model
    def digest_send(self, month=None, force=False):
        """Send it. What actually happens depends on the two switches, and the
        answer says which one decided."""
        self._require_review()
        return self.env['pb.rnr.digest'].send_digest(
            month=month or None, force=bool(force))

    @api.model
    def run_celebrations(self):
        """"Run it now" — exactly what the night does, no more and no less
        (R53)."""
        self._require_review()
        today = self.env['pb.rnr.celebration'].run_celebrations_today()
        week = self.env['pb.rnr.celebration'].run_manager_week()
        return {'today': today, 'week': week}
