# -*- coding: utf-8 -*-
"""PSCHEME P2a C — "Give everyone their own pay scheme": the one-time fill.

Owner ruling R3: existing people are filled once — the scheme that pays them
today, else from their Country of work — with a review list and an undo.

THE PLAN (`fill_plan`) writes nothing. For every active person of one company
who has no pay scheme of their own yet, it reads who pays them TODAY through
the resolver with the person rung switched off (`SKIP_PERSON`, so the answer
is exactly the team ladder they follow now) and the main question asked
(`MAIN_QUESTION`, so a person on a regular scheme of an end-of-month company
still reads as paid). One `resolve_many` per kind of run for the whole
company — no per-person query — so it stays fast at 5,000 people (test T7).

    group     who                                              default
    ready     paid today by a scheme of their Country of work  ticked: keep it
    country   nobody pays them; their country has ONE scheme  ticked: that one
    check     paid today by a scheme of ANOTHER country        unticked: pick
    choice    nobody pays them and their country has several   no default
              schemes or none; or they have no Country of work
    own       already have a pay scheme of their own           never touched

A mid-month advance is copied only when the person really has one today — an
answer of a real mid-month scheme (ledger A13; a team line "for any kind of
run" answers the advance question with the main scheme and is NOT one) — and
only when it is of the same country as the pay scheme they get.

THE APPLY (`fill_apply`) plans again (the screen's copy is never trusted),
turns the ticked groups and the reader's picks into P1 groups and sends ONE
request through the same route as every Mapping change (`person_set_many`,
source `fill`). Every row starts on the first day of the current month
(C.3). Re-running is safe: whoever got a row is "Already have their own".
`dry=True` plans and counts and writes nothing (the release script's
rehearsal, C.6).

THE LOG (`pb.person.scheme.fill`, cloned from `pb.cow.fill.log`) keeps who
asked, when, the counts and EXACTLY the rows the fill made, with what each
row said when it was made. "Undo this fill" removes those rows for every
person nobody changed since; anybody changed since keeps all of theirs and is
named (C.5). The undo goes through the same route (kind `person_unfill`).
"""

import json
import logging
import time
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

from odoo.addons.pb_hr_payroll_formula.models.schememap_approval import (
    SCHEMEMAP_WRITE,
)

from .pb_scheme_map import ADVANCE_RUNGS, MAIN_QUESTION, SKIP_PERSON

_logger = logging.getLogger(__name__)

GROUPS = ('ready', 'country', 'check', 'choice', 'own')
TICKED_BY_DEFAULT = ('ready', 'country')
MAIN_KINDS = ('regular', 'end_cycle')
MAX_KEPT_NAMED = 40


class PbPersonSchemeFill(models.Model):
    _name = 'pb.person.scheme.fill'
    _description = 'Pay scheme fill — who, when, how many, which rows'
    _order = 'id desc'

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 index=True, readonly=True)
    user_id = fields.Many2one('res.users', string='Asked by', readonly=True)
    done_by_id = fields.Many2one('res.users', string='Carried out by',
                                 readonly=True, default=lambda s: s.env.user)
    reference = fields.Char(string='Request', readonly=True)
    people_count = fields.Integer(string='People given a pay scheme', readonly=True)
    row_count = fields.Integer(string='Rows written', readonly=True)
    counts_json = fields.Text(string='By group (JSON)', readonly=True)
    #: [[row_id, employee_id, config_id, date_from], ...] — the rows exactly as
    #: the fill made them, so the undo can tell an untouched row from a
    #: changed one even after the row itself was edited or removed.
    rows_json = fields.Text(string='Rows made (JSON)', readonly=True)
    state = fields.Selection([('done', 'Filled'), ('undone', 'Undone')],
                             default='done', required=True, readonly=True)
    undone_by_id = fields.Many2one('res.users', string='Undone by', readonly=True)
    undone_at = fields.Datetime(string='Undone on', readonly=True)
    removed_count = fields.Integer(string='Rows taken off', readonly=True)
    kept_json = fields.Text(string='People kept (JSON)', readonly=True)

    def rows(self):
        self.ensure_one()
        try:
            return json.loads(self.rows_json or '[]')
        except ValueError:
            return []

    def display_words(self):
        self.ensure_one()
        return _("The fill of %(date)s by %(who)s: %(count)s people",
                 date=format_date(self.env, fields.Datetime.context_timestamp(
                     self, self.create_date).date(), date_format='d MMM y')
                 if self.create_date else '',
                 who=(self.user_id or self.done_by_id).name or '',
                 count=self.people_count)


class PbSchemeBoardFill(models.AbstractModel):
    _inherit = 'pb.scheme.board'

    # ============================================================= the plan
    @api.model
    def fill_plan(self, company_id=None, employee_ids=None):
        """The review list (see the module docstring). Writes nothing."""
        if not self._can_read():
            raise AccessError(_("You cannot see who pays this company's people."))
        company_id = self._pick_company(company_id)
        plan = self._fill_plan(company_id, employee_ids)
        company = self.env['res.company'].sudo().browse(company_id)
        plan.update({
            'lane': self._person_lane(company),
            'blocked': self._person_blocked(company),
            'can_propose': self._can_propose_person(),
            'latest': self._fill_latest(company_id),
            'cow_fill': self._cow_fill_available(),
        })
        return plan

    @api.model
    def _cow_fill_available(self):
        """"Fill empty Country of Work" is offered where it exists and the
        reader may run it (HR managers, `pb_employee_form_tidy`)."""
        if 'pb.cow.fill.wizard' not in self.env:
            return False
        return bool(self._safe(lambda: self.env.user.has_group('hr.group_hr_manager'),
                               default=False))

    @api.model
    def _fill_plan(self, company_id, only_ids=None):
        started = time.time()
        Map = self.env['pb.scheme.map'].sudo()
        Config = self.env['hr.formula.config'].sudo().with_context(active_test=False)
        roster = Map._departments_for(company_ids=[company_id])
        ids = sorted(roster)
        if only_ids:
            wanted = {int(e) for e in only_ids if e}
            ids = [i for i in ids if i in wanted]
        Row = self.env['pb.person.scheme'].sudo()
        with_rows = set()
        if ids:
            for (employee,) in Row._read_group(
                    [('employee_id', 'in', ids), ('active', '=', True)],
                    ['employee_id']):
                with_rows.add(employee.id)
        free = [i for i in ids if i not in with_rows]
        main_cycle = self.env['hr.employee']._pb_main_cycle(company_id)
        Ladder = Map.with_context(**{SKIP_PERSON: True})
        main = Ladder.with_context(**{MAIN_QUESTION: True}).resolve_many(
            free, main_cycle) if free else {}
        second = Ladder.resolve_many(free, 'mid_cycle') if free else {}

        people = {}
        if free:
            for rec in self.env['hr.employee'].sudo().search_read(
                    [('id', 'in', free)], ['name', 'payroll_country']):
                people[rec['id']] = rec
        # every scheme the plan can name, read once
        country_codes = sorted({p['payroll_country'] for p in people.values()
                                if p.get('payroll_country')})
        by_country = {}
        for code in country_codes:
            by_country[code] = Map._country_schemes(company_id, code).filtered(
                lambda c: c.cycle_type in MAIN_KINDS)
        every_main = Config.search([
            ('state', '=', 'active'), ('cycle_type', 'in', MAIN_KINDS),
            '|', ('company_id', '=', False), ('company_id', '=', company_id)],
            order='name, id')
        scheme_ids = set(every_main.ids)
        for answer in list(main.values()) + list(second.values()):
            if answer.get('config_id'):
                scheme_ids.add(answer['config_id'])
        for schemes in by_country.values():
            scheme_ids |= set(schemes.ids)
        configs = {c.id: c for c in Config.browse(sorted(scheme_ids))}

        rows, counts = [], defaultdict(int)
        counts['own'] = len(with_rows)
        for employee_id in free:
            person = people.get(employee_id) or {}
            country = person.get('payroll_country') or ''
            answer = main.get(employee_id) or {}
            today = configs.get(answer.get('config_id') or 0)
            real_main = bool(today and today.state == 'active'
                             and today.cycle_type in MAIN_KINDS)
            adv_answer = second.get(employee_id) or {}
            adv = configs.get(adv_answer.get('config_id') or 0)
            advance = adv if (adv and adv.cycle_type == 'mid_cycle'
                              and adv.state == 'active'
                              and adv_answer.get('rung') in ADVANCE_RUNGS) else None
            row = {'id': employee_id, 'name': person.get('name') or '',
                   'team_id': (roster.get(employee_id) or (0, 0))[0],
                   'country': country,
                   'today_id': today.id if real_main else 0,
                   'advance_id': advance.id if advance else 0,
                   'target_id': 0, 'options': [], 'reason': '', 'fix': ''}
            schemes = by_country.get(country)
            if not country:
                row['group'] = 'choice'
                row['reason'] = 'no_country'
                row['fix'] = 'cow'
                row['options'] = ([today.id] if real_main else []) + [
                    c.id for c in every_main if not real_main or c != today]
            elif real_main and (not today.country_code or today.country_code == country):
                row['group'] = 'ready'
                row['target_id'] = today.id
                row['options'] = [today.id]
            elif real_main:
                row['group'] = 'check'
                row['reason'] = 'other_country'
                row['options'] = [today.id] + [c.id for c in schemes or []]
                if schemes and len(schemes) == 1:
                    row['country_pick'] = schemes.id
                elif not schemes:
                    row['fix'] = 'mapping'      # their country has no scheme yet
            elif schemes and len(schemes) == 1:
                row['group'] = 'country'
                row['target_id'] = schemes.id
                row['options'] = [schemes.id]
            elif schemes:
                row['group'] = 'choice'
                row['reason'] = 'several'
                row['options'] = schemes.ids
            else:
                row['group'] = 'choice'
                row['reason'] = 'no_scheme'
                row['fix'] = 'mapping'
                row['options'] = every_main.ids
            counts[row['group']] += 1
            rows.append(row)

        labels = dict(self.env['hr.formula.config']._fields['country_code']
                      ._description_selection(self.env))
        teams = Map._department_names({r['team_id'] for r in rows if r['team_id']})
        first = fields.Date.context_today(self).replace(day=1)
        return {
            'company_id': company_id,
            'company': self.env['res.company'].sudo().browse(company_id).name or '',
            'people': len(ids),
            'without': len(free),
            'counts': {g: counts.get(g, 0) for g in GROUPS},
            'rows': rows,
            'schemes': {str(c.id): {
                'id': c.id, 'name': c.name or '', 'country': c.country_code or '',
                'country_name': labels.get(c.country_code or '') or '',
                'kind_words': Map.cycle_words(c.cycle_type),
                'currency': c.currency_id.name or '',
                'advance': c.cycle_type == 'mid_cycle',
            } for c in configs.values()},
            'countries': {code: labels.get(code) or code for code in country_codes},
            'teams': {str(k): v for k, v in teams.items()},
            'date': fields.Date.to_string(first),
            'date_words': self._day_words(first),
            'ms': int((time.time() - started) * 1000),
        }

    # ============================================================ the apply
    @api.model
    def _fill_groups(self, plan, tick=TICKED_BY_DEFAULT, picks=None, skip=None):
        """The P1 groups a plan plus the reader's choices become, and the
        counts. A pick must be one of that person's own options."""
        picks = {int(k): int(v or 0) for k, v in (picks or {}).items() if k}
        skip = {int(e) for e in (skip or []) if e}
        tick = set(tick or ())
        schemes = plan['schemes']
        day = plan['date']
        buckets = defaultdict(list)
        used = defaultdict(int)
        left = 0
        for row in plan['rows']:
            if row['id'] in skip:
                left += 1
                continue
            target = 0
            if row['id'] in picks and picks[row['id']] in row['options']:
                target = picks[row['id']]
            elif row['group'] in tick and row['target_id']:
                target = row['target_id']
            if not target:
                left += 1
                continue
            advance = 0
            if row['advance_id']:
                a_country = (schemes.get(str(row['advance_id'])) or {}).get('country')
                t_country = (schemes.get(str(target)) or {}).get('country')
                if not a_country or not t_country or a_country == t_country:
                    advance = row['advance_id']
            buckets[(target, advance)].append(row['id'])
            used[row['group']] += 1
        groups = [{'employee_ids': ids, 'config_id': config,
                   'advance_config_id': advance or False, 'date_from': day}
                  for (config, advance), ids in sorted(buckets.items())]
        return groups, dict(used), left

    @api.model
    def fill_apply(self, company_id=None, tick=TICKED_BY_DEFAULT, picks=None,
                   skip=None, dry=False, employee_ids=None):
        """Give the ticked people their pay scheme (see the module docstring).

        `dry=True` writes nothing and answers the counts — the call the
        release script makes first (C.6)."""
        if not self._can_propose_person():
            raise AccessError(_(
                "Changing a person's pay scheme is for HR and payroll. Ask one "
                "of them to make the change."))
        company_id = self._pick_company(company_id)
        plan = self._fill_plan(company_id, employee_ids)
        groups, used, left = self._fill_groups(plan, tick, picks, skip)
        people = sum(len(g['employee_ids']) for g in groups)
        summary = {
            'dry': bool(dry), 'company_id': company_id, 'people': people,
            'left': left, 'by_group': used, 'plan_counts': plan['counts'],
            'schemes': [{
                'scheme': plan['schemes'][str(g['config_id'])]['name'],
                'advance': plan['schemes'].get(str(g['advance_config_id'] or 0), {}).get('name', ''),
                'people': len(g['employee_ids'])} for g in groups],
            'date': plan['date'],
        }
        if dry or not groups:
            if not groups and not dry:
                raise UserError(_("Nobody is ticked, so nobody is given a pay "
                                  "scheme. Tick a group or pick a pay scheme "
                                  "for someone first."))
            return summary
        title = _("Give %(count)s people their own pay scheme from %(date)s",
                  count=people, date=plan['date_words'])
        answer = self.person_set_many(
            groups, company_id, source='fill', title=title,
            extra={'fill': {'counts': used, 'plan': plan['counts']}})
        summary.update(answer)
        return summary

    # ============================================================== the log
    @api.model
    def _fill_log(self, rows, cleaned, extra):
        if not rows:
            return None
        company = rows[:1].employee_id.company_id
        fill = extra.get('fill') or {}
        asked = self.env['res.users'].sudo().browse(
            int(extra.get('asked_by') or self.env.uid)).exists()
        return self.env['pb.person.scheme.fill'].sudo().create({
            'company_id': company.id,
            'user_id': asked.id or self.env.uid,
            'done_by_id': self.env.uid,
            'reference': extra.get('reference') or '',
            'people_count': len(rows.mapped('employee_id')),
            'row_count': len(rows),
            'counts_json': json.dumps(fill.get('counts') or {}),
            'rows_json': json.dumps([[r.id, r.employee_id.id, r.config_id.id,
                                      fields.Date.to_string(r.date_from)]
                                     for r in rows]),
        })

    @api.model
    def _fill_latest(self, company_id):
        """The company's latest fill, in screen words, with what "Undo this
        fill" would do now."""
        fill = self.env['pb.person.scheme.fill'].sudo().search(
            [('company_id', '=', int(company_id or 0))], order='id desc', limit=1)
        if not fill:
            return None
        when = fields.Datetime.context_timestamp(fill, fill.create_date).date() \
            if fill.create_date else None
        out = {
            'id': fill.id, 'state': fill.state,
            'date_words': self._day_words(when),
            'who': (fill.user_id or fill.done_by_id).name or '',
            'people': fill.people_count, 'rows': fill.row_count,
            'reference': fill.reference or '',
        }
        if fill.state == 'done':
            out['undo'] = self._fill_undo_plan(fill)
        else:
            out['undone_words'] = self._day_words(
                fields.Datetime.context_timestamp(fill, fill.undone_at).date()
                if fill.undone_at else None)
            out['removed'] = fill.removed_count
        return out

    # ============================================================== the undo
    @api.model
    def _fill_undo_plan(self, fill):
        """`{remove: [row ids], people, kept: [names], kept_count}` — a person
        is given back to their team only when EVERY active row of theirs is
        one this fill made, exactly as it made it; anybody changed since keeps
        everything of theirs."""
        Row = self.env['pb.person.scheme'].sudo().with_context(active_test=False)
        made = fill.rows()
        by_person = defaultdict(list)
        for row_id, employee_id, config_id, date_from in made:
            by_person[employee_id].append((row_id, config_id, date_from))
        live = Row.search([('employee_id', 'in', list(by_person))])
        live_by_person = defaultdict(list)
        for row in live:
            live_by_person[row.employee_id.id].append(row)
        remove, kept = [], []
        for employee_id, theirs in by_person.items():
            original = {row_id: (config_id, date_from) for row_id, config_id, date_from in theirs}
            rows = live_by_person.get(employee_id) or []
            active = [r for r in rows if r.active]
            untouched = [r for r in active if r.id in original
                         and original[r.id] == (r.config_id.id, fields.Date.to_string(r.date_from))
                         and not r.date_to]
            if active and len(untouched) == len(active):
                remove.extend(r.id for r in untouched)
            elif active:
                kept.append(employee_id)
        names = [e.name or '' for e in self.env['hr.employee'].sudo().with_context(
            active_test=False).browse(kept[:MAX_KEPT_NAMED]).exists()]
        return {'remove': remove,
                'people': len({employee_id for employee_id, theirs in by_person.items()
                               if any(r[0] in remove for r in theirs)}),
                'kept': names, 'kept_count': len(kept)}

    @api.model
    def fill_undo(self, fill_id=None, company_id=None):
        """"Undo this fill" — the company's latest fill only, through the same
        route as every Mapping change (kind `person_unfill`)."""
        if not self._can_propose_person():
            raise AccessError(_(
                "Changing a person's pay scheme is for HR and payroll. Ask one "
                "of them to make the change."))
        company_id = self._pick_company(company_id)
        Fill = self.env['pb.person.scheme.fill'].sudo()
        latest = Fill.search([('company_id', '=', company_id)], order='id desc', limit=1)
        if not latest or (fill_id and latest.id != int(fill_id)):
            raise UserError(_("Only the latest fill can be undone, and this is "
                              "not it any more. Reload the screen."))
        if latest.state != 'done':
            raise UserError(_("This fill was already undone."))
        company = latest.company_id
        if self._map_held():
            lane = self._person_lane(company)
            if lane in ('fast', 'none') and not self._can_carry_out_person():
                raise UserError(self._no_carry_out_sentence())
            if lane != 'none':
                proposal = self.env['pb.schememap.proposal'].with_company(company).propose(
                    'person_unfill',
                    _("Undo the pay scheme fill for %s people", latest.people_count),
                    payload={'fill_id': latest.id, 'company_id': company.id},
                    facts={'employees_moved': {'value': latest.people_count, 'unit': ''},
                           'schemes': {'value': 0, 'unit': ''}},
                    target=latest, company=company)
                answer = self._person_answer_of(proposal)
                answer.update((proposal.result() or {}))
                return answer
        result = self.with_context(**{SCHEMEMAP_WRITE: True}).fill_undo_write(latest.id)
        return dict(result, ok=True, applied=True, saved=True, pending=False,
                    message=_("Saved."))

    @api.model
    def fill_undo_write(self, fill_id, asked_by=None):
        """The undo itself. Only from the approved route or a reader who may
        carry it out (`fill_undo`)."""
        if not self.env.context.get(SCHEMEMAP_WRITE) and not self.env.su \
                and self._map_held():
            raise AccessError(_("A pay scheme change goes through approval."))
        fill = self.env['pb.person.scheme.fill'].sudo().browse(int(fill_id or 0)).exists()
        if not fill:
            raise UserError(_("That fill is not there any more."))
        if fill.state != 'done':
            return {'removed': 0, 'kept': 0}
        plan = self._fill_undo_plan(fill)
        rows = self.env['pb.person.scheme'].sudo().browse(plan['remove']).exists()
        removed = len(rows)
        rows.unlink()
        fill.write({'state': 'undone', 'undone_by_id': self.env.uid,
                    'undone_at': fields.Datetime.now(), 'removed_count': removed,
                    'kept_json': json.dumps(plan['kept'])})
        self.env.flush_all()
        return {'removed': removed, 'people': plan['people'],
                'kept': plan['kept_count'], 'kept_names': plan['kept']}
