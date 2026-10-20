# -*- coding: utf-8 -*-
"""NAV P3a — the Hiring hub's two registers: Applicants and Offers.

Until now every candidate lived on ONE role's board and every offer inside
ONE role's Details panel. A recruiter with twenty-seven roles had twenty-seven
places to look. These two reads put them side by side, across every role the
reader may see, without inventing a second set of rules:

  * **Applicants** (`get_applicants`) builds the very same card the role board
    builds — `_candidates(req)` with every later phase's additions and the
    privacy mask (P4) — for a slice of each role's people, chosen here so the
    filters and the 600 cap run across roles. Nothing about a card is
    re-derived in this file.
  * **Offers** (`get_offers`) is `_offer_row` (masked as it always is) plus
    the four facts a register needs that the role panel shows elsewhere: is it
    waiting on MY sign-off, how far the papers are, what the background check
    said, and when they join.

WHO SEES WHAT is unchanged: roles are searched as the reader (record rules),
a stand-in reads the roles of the recruiter they cover (the board's own rule,
`pb_hiring_a3.get_board`), offers are searched as the reader, and money stays
blanked for anybody outside the hiring team.

The one new rule is opt-in and the register's own: a bulk move sent with
`register: True` refuses a stage one of the people's roles does not use,
before anybody moves, because a selection on this screen can mix roles whose
boards have different columns.
"""

import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .board_p1 import BOARD_CANDIDATES
from .hiring_common import as_id

_logger = logging.getLogger(__name__)

#: The Applicants register reads at most this many people across every role,
#: the same ceiling a single role's board has.
APPLICANTS_CAP = BOARD_CANDIDATES

#: The Offers register, like the board's own offer list, reads the newest 200.
OFFERS_CAP = 200

#: "Joining soon": an accepted or signed offer whose joining date is today or
#: within this many days (inclusive).
JOINING_WINDOW_DAYS = 30

#: Where an offer sits in the story, left to right. An offer is at exactly ONE
#: step so the counts add up (the quiet-board rule). "Being prepared" sits with
#: the sign-offs: it is the same desk.
OFFER_STEPS = [
    ('approval', ('draft', 'submitted', 'manager_ok', 'hr_ok')),
    ('candidate', ('sent',)),
    ('signing', ('accepted', 'signed')),
    ('joined', ('joined',)),
    ('closed', ('declined', 'dropped', 'refused')),
]
STEP_OF = {state: key for key, states in OFFER_STEPS for state in states}

#: Stage families as the register's filter words them.
FAMILY_DOMAINS = {
    'play': [('stage_id.pb_family', '=', 'open'),
             ('stage_id.pb_key', 'not in', ('offer', 'post_offer')),
             ('active', '=', True)],
    'offer': [('stage_id.pb_key', 'in', ('offer', 'post_offer')),
              ('active', '=', True)],
    'joined': [('stage_id.pb_family', '=', 'done')],
    'closed': ['|', ('stage_id.pb_family', '=', 'closed'), ('active', '=', False)],
}

#: Card flags a register filter narrows by (applied after the cards are built:
#: they are facts of the card, not of the record).
CARD_FLAG_FILTERS = {
    'waiting_mine': lambda c: 'waiting' in (c.get('flags') or []),
    'late': lambda c: bool((c.get('opinions') or {}).get('late'))
    or 'late' in (c.get('flags') or []),
    'iv_week': lambda c: 'iv' in (c.get('flags') or []),
    'duplicate': lambda c: 'duplicate' in (c.get('flags') or []),
}

OFFER_FLAG_FILTERS = {
    'waiting_mine': lambda r: r.get('waiting_mine'),
    'docs_overdue': lambda r: bool(r.get('docreq') and r['docreq'].get('overdue')),
    'check_flagged': lambda r: bool(r.get('bgv') and r['bgv'].get('state') == 'flagged'),
    'joining_soon': lambda r: r.get('joining_soon'),
    'joined_month': lambda r: r.get('joined_month'),
}


def _flags_of(filters):
    """The flag filters a payload asks for, as a set of keys."""
    raw = (filters or {}).get('flags') or []
    if isinstance(raw, str):
        raw = [raw]
    out = {k for k in raw if k}
    for key in list(CARD_FLAG_FILTERS) + list(OFFER_FLAG_FILTERS):
        if (filters or {}).get(key):
            out.add(key)
    return out


class PbHiringRegistersP9(models.AbstractModel):
    _inherit = 'pb.hiring'

    # =====================================================================
    #  The roles the reader may see
    # =====================================================================
    @api.model
    def _p9_roles(self):
        """Every role on the reader's board, newest first, read as the
        system once the record rules (or the cover clause) have decided."""
        co_ids = self.env.companies.ids or [self.env.company.id]
        Requisition = self.env['pb.hiring.requisition']
        covered = self._safe(lambda: self._cover_scope(), default=[])
        if covered:
            roles = Requisition.sudo().search(
                [('company_id', 'in', co_ids), ('recruiter_id', 'in', covered)],
                order='id desc')
        else:
            roles = Requisition.search([('company_id', 'in', co_ids)],
                                       order='id desc')
        return roles.sudo()

    @api.model
    def _p9_role_rows(self, roles):
        rows = []
        for req in roles:
            rows.append({
                'id': req.id,
                'name': req.title or req.name or '',
                'recruiter_id': req.recruiter_id.id or False,
                'recruiter': req.recruiter_id.name or '',
                'has_job': bool(req.job_id),
                'stage_keys': [k for k in self._safe(
                    lambda req=req: req._pb_board_stages().mapped('pb_key'),
                    default=[]) if k],
                'can_move': bool(self._can_move(req)),
            })
        return rows

    @api.model
    def _p9_recruiters(self, role_rows):
        seen = {}
        for r in role_rows:
            if r['recruiter_id'] and r['recruiter_id'] not in seen:
                seen[r['recruiter_id']] = r['recruiter']
        return sorted([{'id': k, 'name': v} for k, v in seen.items()],
                      key=lambda r: r['name'].lower())

    # =====================================================================
    #  Applicants
    # =====================================================================
    @api.model
    def get_applicants(self, filters=None, cursor=None):
        """Every application the reader may see, across all their roles.

        filters: {role_id?, recruiter_id?, family? ('play'|'offer'|'joined'|
                  'closed'), q?, flags?: ['waiting_mine'|'late'|'iv_week'|
                  'duplicate'] (or each key as a boolean)}
        cursor:  reserved for paging; the register reads the newest
                 APPLICANTS_CAP and says so, exactly like a role's board.

        returns: {allowed, columns: [{key, id, label, name, family, meaning,
                  count, avg_days}], cards, total, capped, roles, recruiters,
                  glance: {in_play, roles, waiting_mine, opinions_late,
                  iv_week, duplicate}, can_move}
        """
        if not self._can_read():
            return {'allowed': False, 'columns': [], 'cards': [], 'total': 0,
                    'capped': False, 'roles': [], 'recruiters': [],
                    'glance': {}, 'can_move': False}
        f = filters or {}
        roles = self._p9_roles()
        role_rows = self._p9_role_rows(roles)
        by_id = {r['id']: r for r in role_rows}
        # One role per job: the newest role that names it (a job reopened
        # under a second request keeps its people on the newer role).
        by_job = {}
        for req in roles:
            if req.job_id and req.job_id.id not in by_job:
                by_job[req.job_id.id] = req
        jobs = dict(by_job)
        if f.get('role_id'):
            rid = as_id(f.get('role_id'))
            jobs = {j: r for j, r in jobs.items() if r.id == rid}
        if f.get('recruiter_id'):
            uid = as_id(f.get('recruiter_id'))
            jobs = {j: r for j, r in jobs.items() if r.recruiter_id.id == uid}

        domain = [('job_id', 'in', list(jobs) or [0])]
        family = f.get('family') or ''
        if family in FAMILY_DOMAINS:
            domain += FAMILY_DOMAINS[family]
        q = (f.get('q') or '').strip()
        if q:
            role_jobs = [j for j, r in jobs.items()
                         if q.lower() in (r.title or '').lower()]
            domain += ['|', '|', '|',
                       ('partner_name', 'ilike', q), ('email_from', 'ilike', q),
                       ('job_id.name', 'ilike', q), ('job_id', 'in', role_jobs or [0])]
        Applicant = self.env['hr.applicant'].sudo().with_context(active_test=False)
        total = Applicant.search_count(domain)
        apps = Applicant.search(domain, order='date_last_stage_update desc, id desc',
                                limit=APPLICANTS_CAP)
        groups = {}
        for app in apps:
            groups.setdefault(app.job_id.id, []).append(app.id)

        cards = []
        for job_id, ids in groups.items():
            req = jobs.get(job_id)
            if not req:
                continue
            role = by_id.get(req.id) or {}
            built = self._safe(
                lambda req=req, ids=ids: self.with_context(
                    pb_hiring_app_ids=ids)._candidates(req), default=[])
            for card in built:
                card.update({
                    'role_id': req.id,
                    'role': role.get('name') or req.title or '',
                    'recruiter_id': role.get('recruiter_id') or False,
                    'recruiter': role.get('recruiter') or '',
                    'can_move': bool(role.get('can_move')),
                })
                cards.append(card)
        # Newest move first, as a role's own board orders its columns.
        cards.sort(key=lambda c: (c.get('days_in_stage') or 0, -(c.get('id') or 0)))

        glance = {
            'in_play': sum(1 for c in cards if c.get('family') == 'open'),
            'roles': len({c['role_id'] for c in cards if c.get('family') == 'open'}),
            'waiting_mine': sum(1 for c in cards if CARD_FLAG_FILTERS['waiting_mine'](c)),
            'opinions_late': sum(1 for c in cards if CARD_FLAG_FILTERS['late'](c)),
            'iv_week': sum(1 for c in cards if CARD_FLAG_FILTERS['iv_week'](c)),
            'duplicate': sum(1 for c in cards if CARD_FLAG_FILTERS['duplicate'](c)),
        }
        columns = self._p9_columns(cards, roles)

        wanted = _flags_of(f) & set(CARD_FLAG_FILTERS)
        if wanted:
            cards = [c for c in cards
                     if all(CARD_FLAG_FILTERS[k](c) for k in wanted)]
        return {
            'allowed': True,
            'columns': columns,
            'cards': cards,
            'total': total,
            'capped': total > len(apps),
            'roles': [r for r in role_rows if r['has_job']],
            'recruiters': self._p9_recruiters(role_rows),
            'glance': glance,
            'can_move': any(r['can_move'] for r in role_rows),
        }

    @api.model
    def _p9_columns(self, cards, roles):
        """One column per stage in journey order: every stage any visible
        role shows, plus any somebody is sitting in. Typical days are the
        people in the column now (the role board's own figure is per role and
        does not add across roles)."""
        Stage = self.env['hr.recruitment.stage'].sudo()
        shown = set()
        for req in roles:
            shown |= set(self._safe(lambda req=req: req._pb_board_stages().ids,
                                    default=[]))
        by_stage = {}
        for c in cards:
            by_stage.setdefault(c.get('stage_id'), []).append(c)
        out = []
        for s in Stage.search([('pb_key', '!=', False)], order='sequence,id'):
            here = by_stage.get(s.id, [])
            if s.id not in shown and not here:
                continue
            days = [c.get('days_in_stage') or 0 for c in here]
            out.append({
                'id': s.id, 'key': s.pb_key, 'name': s.name or '',
                'label': s.name or '', 'family': s.pb_family or 'open',
                'meaning': s.pb_meaning or '', 'count': len(here),
                'visible': True,
                'avg_days': round(sum(days) / len(days), 1) if days else None,
            })
        return out

    # ---------------------------------------------------------- moving
    def _act_journey_stage(self, payload):
        """The register's selection can mix roles; a stage one of them does
        not use is refused before anybody moves."""
        if payload.get('register'):
            self._p9_check_stage_fits(payload)
        return super()._act_journey_stage(payload)

    def _p9_check_stage_fits(self, payload):
        Stage = self.env['hr.recruitment.stage']
        stage = Stage._pb_stage(payload.get('key')) if payload.get('key') \
            else Stage.sudo().browse(as_id(payload.get('stage_id'))).exists()
        if not stage or not stage.pb_key or stage.pb_family == 'closed':
            return True       # closed outcomes are on every role; the move says the rest
        ids = payload.get('applicant_ids') or (
            [payload['applicant_id']] if payload.get('applicant_id') else [])
        apps = self.env['hr.applicant'].sudo().with_context(
            active_test=False).browse([as_id(i) for i in ids if as_id(i)]).exists()
        missing = []
        for app in apps:
            req = app.pb_requisition_id
            if not req and app.job_id:
                req = self.env['pb.hiring.requisition'].sudo().search(
                    [('job_id', '=', app.job_id.id)], order='id desc', limit=1)
            if req and stage not in req._pb_board_stages():
                title = req.title or req.name or ''
                if title not in missing:
                    missing.append(title)
        if missing:
            raise UserError(_(
                "%(stage)s is not a stage on %(roles)s, so nobody was moved. "
                "Move those people on their own.",
                stage=stage.name or '', roles=', '.join(missing)))
        return True

    # =====================================================================
    #  Offers
    # =====================================================================
    @api.model
    def _p9_offer_set(self):
        co_ids = self.env.companies.ids or [self.env.company.id]
        Offer = self.env['pb.hiring.offer']
        domain = [('company_id', 'in', co_ids)]
        offers = Offer.search(domain, order='id desc', limit=OFFERS_CAP)
        total = self._safe(lambda: Offer.search_count(domain), default=len(offers))
        return offers, total

    @api.model
    def _p9_offer_rows(self):
        """Every offer the reader may see (newest OFFERS_CAP), each with the
        register's own facts."""
        offers, total = self._p9_offer_set()
        today = fields.Date.context_today(self)
        month_start = date.today().replace(day=1)
        sudo = offers.sudo()
        bgvs = {}
        for bgv in self.env['pb.hiring.bgv'].sudo().search([
                ('requisition_id', 'in', sudo.mapped('requisition_id').ids),
                ('applicant_id', 'in', sudo.mapped('applicant_id').ids)],
                order='id desc'):
            bgvs.setdefault((bgv.requisition_id.id, bgv.applicant_id.id), bgv)
        rows = []
        for offer in offers:
            row = self._safe(lambda offer=offer: self._p9_offer_row(
                offer, today, month_start, bgvs), default=None)
            if row:
                rows.append(row)
        return rows, total

    @api.model
    def _p9_offer_row(self, offer, today, month_start, bgvs):
        row = self._offer_row(offer)            # masked for non-team (P4)
        so = offer.sudo()
        req = so.requisition_id
        hiring = self._is_hiring_reader(req)
        expected = so.expected_join_date or so.start_date
        days = (expected - today).days if expected else None
        state = so.state
        mine = False
        if state in ('submitted', 'manager_ok'):
            mine = bool(self._safe(lambda: so._chain_my_seat(), default=False))
        docreq = so.docreq_id
        bgv = so.bgv_id or bgvs.get((req.id, so.applicant_id.id))
        # the state words in the reader's language (the role panel's own row
        # carries the English list label); a variable, so no extractor reads
        # the key as a sentence
        label = row.get('state_label') or ''
        row.update({
            'state_label': _(label) if label else '',
            'step': STEP_OF.get(state, 'approval'),
            'waiting_mine': mine,
            'role_title': req.title or '',
            'recruiter_id': req.recruiter_id.id or False,
            'recruiter': req.recruiter_id.name or '',
            'can_recruit': bool(self._can_recruit(req)),
            'show_money': bool(hiring),
            'joining_days': days,
            'joining_soon': bool(state in ('accepted', 'signed') and days is not None
                                 and 0 <= days <= JOINING_WINDOW_DAYS),
            'joined_month': bool(state == 'joined' and so.joined_on
                                 and so.joined_on >= month_start),
            'dropped': state == 'dropped',
            'case_id': so.case_id.id or False,
            'employee_id': so.employee_id.id or False,
            'docreq': ({
                'in': docreq.in_count, 'wanted': docreq.wanted_count,
                'deadline': str(docreq.deadline or ''), 'state': docreq.state or '',
                'overdue': bool(docreq.state == 'expired' or (
                    docreq.deadline and docreq.deadline < today
                    and docreq.state != 'complete')),
            } if docreq and hiring else None),
            'bgv': ({
                'state': bgv.state or 'open', 'flags': bgv.flag_count,
                'pending': bgv.pending_count,
            } if bgv and hiring else None),
        })
        return row

    @api.model
    def _p9_offer_counts(self, rows):
        return {key: sum(1 for r in rows if test(r))
                for key, test in OFFER_FLAG_FILTERS.items()}

    @api.model
    def get_offers(self, filters=None):
        """The Offers register.

        filters: {step?, role_id?, recruiter_id?, q?, flags?: ['waiting_mine'|
                  'docs_overdue'|'check_flagged'|'joining_soon'|'joined_month']}

        The steps and the counts are over every offer the reader may see (the
        newest 200); the rows are the ones the filters keep. Ordered newest
        first, or by joining date (soonest first, undated last) while the
        joining filter is on.
        """
        if not self._can_read():
            return {'allowed': False, 'rows': [], 'steps': [], 'counts': {},
                    'roles': [], 'recruiters': [], 'total': 0, 'capped': False,
                    'show_money': False}
        f = filters or {}
        rows, total = self._p9_offer_rows()
        steps = [{'key': key, 'count': sum(1 for r in rows if r['step'] == key)}
                 for key, _states in OFFER_STEPS]
        counts = self._p9_offer_counts(rows)
        roles, recruiters = {}, {}
        for r in rows:
            if r['requisition_id']:
                roles.setdefault(r['requisition_id'], r['role_title'] or r['role'])
            if r['recruiter_id']:
                recruiters.setdefault(r['recruiter_id'], r['recruiter'])

        keep = rows
        if f.get('step'):
            keep = [r for r in keep if r['step'] == f['step']]
        if f.get('role_id'):
            rid = as_id(f['role_id'])
            keep = [r for r in keep if r['requisition_id'] == rid]
        if f.get('recruiter_id'):
            uid = as_id(f['recruiter_id'])
            keep = [r for r in keep if r['recruiter_id'] == uid]
        q = (f.get('q') or '').strip().lower()
        if q:
            keep = [r for r in keep if q in ' '.join(
                [r['candidate'], r['role'], r['role_title'], r['name'],
                 r['recruiter']]).lower()]
        wanted = _flags_of(f) & set(OFFER_FLAG_FILTERS)
        if wanted:
            keep = [r for r in keep if all(OFFER_FLAG_FILTERS[k](r) for k in wanted)]
        if 'joining_soon' in wanted:
            keep = sorted(keep, key=lambda r: (
                r['joining_days'] is None,
                r['joining_days'] if r['joining_days'] is not None else 0,
                -r['id']))
        return {
            'allowed': True,
            'rows': keep,
            'steps': steps,
            'counts': counts,
            'roles': sorted([{'id': k, 'name': v} for k, v in roles.items()],
                            key=lambda r: r['name'].lower()),
            'recruiters': sorted([{'id': k, 'name': v} for k, v in recruiters.items()],
                                 key=lambda r: r['name'].lower()),
            'total': total,
            'capped': total > len(rows),
            'show_money': bool(self._hiring_group()),
        }

    # =====================================================================
    #  The Overview strip
    # =====================================================================
    @api.model
    def _offer_kpis(self, offer_rows):
        """The two new tiles read the register's own counts, so a tile and
        the filter it opens can never disagree (R80)."""
        kpis = super()._offer_kpis(offer_rows)
        rows, _total = self._safe(lambda: self._p9_offer_rows(), default=([], 0))
        counts = self._p9_offer_counts(rows)
        kpis.update({
            'offers_waiting_mine': counts['waiting_mine'],
            'joining_soon': counts['joining_soon'],
            'joined_month': counts['joined_month'],
        })
        return kpis
