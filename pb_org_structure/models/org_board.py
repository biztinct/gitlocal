# -*- coding: utf-8 -*-
"""`pb.org.structure` — the server half of People › Jobs.

Four parts on one screen: Jobs (the filter panel over `hr.job`), Levels,
Cost centres and Hiring pause. Every method checks its own gate first
(`org_common`) and then reads or writes under sudo — an HR officer may hold
no read on `hr.contract` (CD3) and the Head of hiring none on `hr.department`
writes.

Nothing here writes a payslip, a wage or a pay line. The one contract field
written is the cost-centre TEXT, only through a dated move, and finished
payslips keep theirs (`cost_centre.py`).
"""
import re
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

from . import org_common as oc
from .cost_centre import _norm

PAGE_SIZE = 60
#: How far ahead a cost-centre change may be dated.
MAX_DAYS_AHEAD = 366
#: People one move may cover at once.
MAX_PEOPLE = 2000


def _as_id(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class PbOrgStructure(models.AbstractModel):
    _name = 'pb.org.structure'
    _inherit = ['pb.filter.mixin']
    _description = 'People › Jobs (levels, cost centres, hiring pause)'

    # ================================================================ gates
    @api.model
    def _co_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    @api.model
    def _teams(self):
        """This reader's teams, in the order of their full name ("Sales /
        North" under "Sales"); `complete_name` is not stored on this build."""
        teams = self.env['hr.department'].sudo().search(
            [('company_id', 'in', self._co_ids())])
        return teams.sorted(lambda d: (d.display_name or '').casefold())

    @api.model
    def _companies(self):
        return self.env['res.company'].sudo().browse(self._co_ids())

    # ========================================================= the header
    @api.model
    def get_head(self):
        """The numbers line and the pickers, counted over this reader's
        companies."""
        if not oc.can_read(self.env):
            return {'allowed': False}
        co = self._co_ids()
        Job = self.env['hr.job'].sudo()
        Level = self.env['pb.job.level'].sudo()
        CC = self.env['pb.cost.centre'].sudo()
        Move = self.env['pb.cost.centre.move'].sudo()
        Dept = self.env['hr.department'].sudo()
        job_dom = [('company_id', 'in', co)]
        unlisted = self._unlisted_texts()
        paused_roles = Job.search_count(job_dom + [('pb_hiring_paused', '=', True)])
        return {
            'allowed': True,
            'can_manage': oc.can_manage(self.env),
            'can_pause': oc.can_pause(self.env),
            'kpis': {
                'jobs': Job.search_count(job_dom),
                'no_level': Job.search_count(job_dom + [('pb_level_id', '=', False)]),
                'levels': Level.search_count(self._level_domain()),
                'cost_centres': CC.search_count([('company_id', 'in', co)]),
                'unlisted': sum(u['contracts'] for u in unlisted),
                'scheduled': Move.search_count([('company_id', 'in', co),
                                                ('state', '=', 'scheduled')]),
                'paused_roles': paused_roles,
                'paused_teams': Dept.search_count([('company_id', 'in', co),
                                                   ('pb_hiring_pause', '=', True)]),
                'paused_companies': len(self._companies().filtered('pb_hiring_pause')),
            },
            'levels': self._level_rows(),
            'companies': [{'id': c.id, 'name': c.name} for c in self._companies()],
            'today': str(fields.Date.context_today(self)),
            'has_pay_bands': 'pb.pay.band.job' in self.env,
        }

    # ========================================================== jobs panel
    def _pbf_model(self):
        return 'hr.job'

    def _pbf_screen(self):
        return 'org_jobs'

    def _pbf_base_domain(self):
        return [('company_id', 'in', self._co_ids())]

    def _pbf_search_fields(self):
        return ['name', 'department_id.name', 'pb_level_id.name']

    def _pbf_sorts(self):
        return [
            {'key': 'name', 'label': _('Job, A to Z'), 'order': 'name asc, id asc'},
            {'key': 'level', 'label': _('Level, lowest first'),
             'order': 'pb_level_id asc, name asc'},
            {'key': 'team', 'label': _('Team'), 'order': 'department_id asc, name asc'},
            {'key': 'open', 'label': _('Most people to hire first'),
             'order': 'no_of_recruitment desc, name asc'},
        ]

    def _pbf_spec(self):
        return [
            {'key': 'level', 'label': _('Level'), 'icon': 'layers', 'group': 'work',
             'type': 'many2one', 'path': 'pb_level_id', 'pinned': True,
             'none_label': _('No level yet')},
            {'key': 'team', 'label': _('Team'), 'icon': 'network', 'group': 'work',
             'type': 'many2one', 'path': 'department_id', 'pinned': True,
             'none_label': _('No team')},
            {'key': 'hiring', 'label': _('Hiring'), 'icon': 'pause', 'group': 'other',
             'type': 'choice', 'pinned': True, 'requires': ['pb_hiring_paused'],
             'options': [
                 {'value': 'paused', 'label': _('Paused'), 'tone': 'amber',
                  'domain': [('pb_hiring_paused', '=', True)]},
                 {'value': 'open', 'label': _('Not paused'), 'tone': 'slate',
                  'domain': [('pb_hiring_paused', '=', False)]},
             ]},
            {'key': 'to_hire', 'label': _('People to hire'), 'icon': 'userPlus',
             'group': 'people', 'type': 'choice', 'requires': ['no_of_recruitment'],
             'options': [
                 {'value': 'yes', 'label': _('Somebody to hire'), 'tone': 'blue',
                  'domain': [('no_of_recruitment', '>', 0)]},
                 {'value': 'no', 'label': _('Nobody to hire'), 'tone': 'slate',
                  'domain': [('no_of_recruitment', '=', 0)]},
             ]},
            {'key': 'company', 'label': _('Company'), 'icon': 'landmark', 'group': 'work',
             'type': 'many2one', 'path': 'company_id'},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All jobs'), 'icon': 'briefcase', 'filters': {}},
            {'key': 'nolevel', 'label': _('No level yet'), 'filters': {'level': [False]}},
            {'key': 'paused', 'label': _('Hiring paused'), 'filters': {'hiring': ['paused']}},
            {'key': 'hiring', 'label': _('Somebody to hire'), 'filters': {'to_hire': ['yes']}},
        ]

    @api.model
    def pbf_layout(self):
        if not oc.can_read(self.env):
            return {'refused': _("Jobs are looked after by the HR team.")}
        return super().pbf_layout()

    @api.model
    def _band_of(self, jobs):
        """{job_id: {'band': name, 'family': name}} from Pay, when installed."""
        if 'pb.pay.band.job' not in self.env or not jobs:
            return {}
        out = {}
        try:
            rows = self.env['pb.pay.band.job'].sudo().search(
                [('job_id', 'in', jobs.ids)])
            for row in rows:
                band = row.band_id
                out.setdefault(row.job_id.id, {
                    'band': band.name or '',
                    'family': band.family_id.name if 'family_id' in band._fields
                    and band.family_id else '',
                })
        except Exception:  # noqa: BLE001 - a probe never breaks the list
            return {}
        return out

    @api.model
    def _job_row(self, job, bands):
        band = bands.get(job.id) or {}
        return {
            'id': job.id,
            'name': job.name or '',
            'level': job.pb_level_id.name or '',
            'level_id': job.pb_level_id.id or 0,
            'team': job.department_id.display_name or '',
            'company': job.company_id.name or '',
            'people': job.no_of_employee or 0,
            'to_hire': job.no_of_recruitment or 0,
            'band': band.get('band', ''),
            'family': band.get('family', ''),
            'paused': bool(job.pb_hiring_paused),
            'paused_reason': job.pb_hiring_pause_sentence() if job.pb_hiring_paused else '',
        }

    @api.model
    def get_job_page(self, filters=None, search=None, sort=None, offset=0,
                     limit=PAGE_SIZE):
        if not oc.can_read(self.env):
            return {'rows': [], 'total': 0, 'refused': _(
                "Jobs are looked after by the HR team.")}
        me = self.sudo()
        offset = max(0, _as_id(offset))
        limit = max(1, min(_as_id(limit) or PAGE_SIZE, 200))
        domain = me.pbf_domain(filters or {}, search)
        Job = self.env['hr.job'].sudo()
        jobs = Job.search(domain, order=me.pbf_order(sort) or 'name, id',
                          offset=offset, limit=limit)
        bands = self._band_of(jobs)
        return {'rows': [self._job_row(j, bands) for j in jobs],
                'total': Job.search_count(domain)}

    # ============================================================ one job
    @api.model
    def _job(self, job_id):
        job = self.env['hr.job'].sudo().browse(_as_id(job_id)).exists()
        if not job or job.company_id.id not in self._co_ids():
            raise UserError(_("That job is no longer there."))
        return job

    @api.model
    def get_job(self, job_id):
        oc.require_read(self.env)
        job = self._job(job_id)
        bands = self._band_of(job)
        row = self._job_row(job, bands)
        reqs = self.env['pb.hiring.requisition'].sudo().search(
            [('job_id', '=', job.id), ('state', 'in', ('setup', 'open'))])
        row.update({
            'description': html2plaintext(job.description or '').strip()
            if job.description else '',
            'pause_self': bool(job.pb_hiring_pause_self),
            'pause_reason_self': job.pb_hiring_pause_reason_self or '',
            'requests': [{'id': r.id, 'name': r.display_name,
                          'state': dict(r._fields['state'].selection).get(r.state, '')}
                         for r in reqs],
            'levels': self._level_rows(job.company_id),
            'can_manage': oc.can_manage(self.env),
            'can_pause': oc.can_pause(self.env),
        })
        return row

    @api.model
    def save_job(self, job_id, vals):
        oc.require_manage(self.env)
        job = self._job(job_id)
        vals = vals or {}
        write = {}
        if 'level_id' in vals:
            level = self.env['pb.job.level'].sudo().browse(
                _as_id(vals['level_id'])).exists()
            if level and level.company_id and level.company_id != job.company_id:
                raise UserError(_("Choose a level of this job's company."))
            write['pb_level_id'] = level.id or False
        if 'description' in vals:
            text = (vals.get('description') or '').strip()
            write['description'] = Markup('').join(
                Markup('<p>%s</p>') % part for part in re.split(r'\n\s*\n', text)
                if part.strip()) if text else False
        if write:
            job.write(write)
        return self.get_job(job.id)

    # ============================================================== levels
    @api.model
    def _level_domain(self, company=None):
        co = company.ids if company else self._co_ids()
        return ['|', ('company_id', '=', False), ('company_id', 'in', co)]

    @api.model
    def _level_rows(self, company=None):
        levels = self.env['pb.job.level'].sudo().search(self._level_domain(company))
        return [{'id': lv.id, 'name': lv.name or '', 'description': lv.description or '',
                 'company': lv.company_id.name or '', 'company_id': lv.company_id.id or 0,
                 'jobs': lv.job_count, 'sequence': lv.sequence} for lv in levels]

    @api.model
    def save_level(self, vals):
        oc.require_manage(self.env)
        vals = vals or {}
        name = (vals.get('name') or '').strip()
        if not name:
            raise UserError(_("Give the level a name."))
        company = _as_id(vals.get('company_id'))
        if company and company not in self._co_ids():
            raise UserError(_("Choose one of your companies."))
        Level = self.env['pb.job.level'].sudo()
        data = {'name': name, 'description': (vals.get('description') or '').strip() or False,
                'company_id': company or False}
        if _as_id(vals.get('id')):
            level = Level.browse(_as_id(vals['id'])).exists()
            if not level or level.id not in Level.search(self._level_domain()).ids:
                raise UserError(_("That level is no longer there."))
            level.write(data)
        else:
            last = Level.search(self._level_domain(), order='sequence desc', limit=1)
            data['sequence'] = (last.sequence or 0) + 10
            Level.create(data)
        return self._level_rows()

    @api.model
    def move_level(self, level_id, step):
        """One place up (step -1) or down (+1) the ladder."""
        oc.require_manage(self.env)
        levels = self.env['pb.job.level'].sudo().search(self._level_domain())
        ids = levels.ids
        lid = _as_id(level_id)
        if lid not in ids:
            raise UserError(_("That level is no longer there."))
        i = ids.index(lid)
        j = i + (1 if _as_id(step) > 0 else -1)
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            for n, rid in enumerate(ids):
                levels.browse(rid).sequence = (n + 1) * 10
        return self._level_rows()

    @api.model
    def archive_level(self, level_id):
        oc.require_manage(self.env)
        level = self.env['pb.job.level'].sudo().browse(_as_id(level_id)).exists()
        if not level or level.id not in self.env['pb.job.level'].sudo().search(
                self._level_domain()).ids:
            raise UserError(_("That level is no longer there."))
        if level.job_count:
            raise UserError(_(
                "%(n)s jobs are at \"%(level)s\". Move them to another level "
                "first.", n=level.job_count, level=level.name))
        level.active = False
        return self._level_rows()

    # ======================================================== cost centres
    @api.model
    def _unlisted_texts(self):
        """Cost-centre texts on running contracts that name nothing in the
        list: [{company_id, company, text, contracts}]."""
        co = self._co_ids()
        Contract = self.env['hr.contract'].sudo()
        groups = Contract._read_group(
            [('company_id', 'in', co), ('state', 'in', ('open', 'draft')),
             ('costcenter', '!=', False), ('pb_cost_centre_id', '=', False)],
            ['company_id', 'costcenter'], ['__count'])
        out = {}
        for company, text, n in groups:
            if not (text or '').strip():
                continue
            key = (company.id, _norm(text))
            hit = out.setdefault(key, {'company_id': company.id, 'company': company.name,
                                       'text': text.strip(), 'contracts': 0})
            hit['contracts'] += n
        return sorted(out.values(), key=lambda r: (-r['contracts'], r['text']))

    @api.model
    def get_cost_centres(self):
        oc.require_read(self.env)
        co = self._co_ids()
        CC = self.env['pb.cost.centre'].sudo().with_context(active_test=False)
        Contract = self.env['hr.contract'].sudo()
        counts = {cc.id: n for cc, n in Contract._read_group(
            [('company_id', 'in', co), ('state', 'in', ('open', 'draft')),
             ('pb_cost_centre_id', '!=', False)], ['pb_cost_centre_id'], ['__count'])}
        Dept = self.env['hr.department'].sudo()
        team_counts = {cc.id: n for cc, n in Dept._read_group(
            [('company_id', 'in', co), ('pb_cost_centre_id', '!=', False)],
            ['pb_cost_centre_id'], ['__count'])}
        Move = self.env['pb.cost.centre.move'].sudo()
        waiting = {cc.id: n for cc, n in Move._read_group(
            [('company_id', 'in', co), ('state', '=', 'scheduled')],
            ['cost_centre_id'], ['__count'])}
        rows = [{
            'id': cc.id, 'code': cc.code or '', 'name': cc.name or '',
            'company': cc.company_id.name or '', 'company_id': cc.company_id.id,
            'active': cc.active, 'note': cc.note or '',
            'contracts': counts.get(cc.id, 0), 'teams': team_counts.get(cc.id, 0),
            'waiting': waiting.get(cc.id, 0),
        } for cc in CC.search([('company_id', 'in', co)], order='active desc, code')]
        teams = [{'id': d.id, 'name': d.display_name, 'company_id': d.company_id.id,
                  'cost_centre_id': d.pb_cost_centre_id.id or 0,
                  'cost_centre': d.pb_cost_centre_id.display_name or ''}
                 for d in self._teams()]
        moves = Move.search([('company_id', 'in', co),
                             '|', ('state', '=', 'scheduled'),
                             ('write_date', '>=', fields.Datetime.now() - timedelta(days=30))],
                            order='state desc, date_start, id', limit=200)
        return {
            'rows': rows,
            'unlisted': self._unlisted_texts(),
            'teams': teams,
            'moves': [self._move_row(m) for m in moves],
            'can_manage': oc.can_manage(self.env),
        }

    @api.model
    def _move_row(self, move):
        return {
            'id': move.id,
            'person': move.employee_id.name or '',
            'cost_centre': move.cost_centre_id.display_name or '',
            'from': str(move.date_start or ''),
            'state': move.state,
            'state_label': dict(move._fields['state']._description_selection(
                self.env)).get(move.state, ''),
            'before': move.old_text or move.contract_id.costcenter or '',
            'problem': move.problem or '',
            'note': move.note or '',
        }

    @api.model
    def save_cost_centre(self, vals):
        oc.require_manage(self.env)
        vals = vals or {}
        code = (vals.get('code') or '').strip()
        name = (vals.get('name') or '').strip() or code
        if not code:
            raise UserError(_("Give the cost centre a code."))
        CC = self.env['pb.cost.centre'].sudo().with_context(active_test=False)
        data = {'code': code, 'name': name, 'note': (vals.get('note') or '').strip() or False}
        if _as_id(vals.get('id')):
            cc = CC.browse(_as_id(vals['id'])).exists()
            if not cc or cc.company_id.id not in self._co_ids():
                raise UserError(_("That cost centre is no longer there."))
            cc.write(data)
        else:
            company = _as_id(vals.get('company_id')) or self.env.company.id
            if company not in self._co_ids():
                raise UserError(_("Choose one of your companies."))
            data['company_id'] = company
            CC.create(data)
        return self.get_cost_centres()

    @api.model
    def set_cost_centre_active(self, cc_id, active):
        oc.require_manage(self.env)
        cc = self.env['pb.cost.centre'].sudo().with_context(
            active_test=False).browse(_as_id(cc_id)).exists()
        if not cc or cc.company_id.id not in self._co_ids():
            raise UserError(_("That cost centre is no longer there."))
        cc.active = bool(active)
        return self.get_cost_centres()

    @api.model
    def make_list_from_contracts(self, company_id=None):
        """One list entry per cost-centre text already on contracts. Writes
        NO contract: the texts already say these codes."""
        oc.require_manage(self.env)
        CC = self.env['pb.cost.centre'].sudo()
        made = 0
        for row in self._unlisted_texts():
            if company_id and row['company_id'] != _as_id(company_id):
                continue
            CC.create({'code': row['text'], 'name': row['text'],
                       'company_id': row['company_id']})
            made += 1
        result = self.get_cost_centres()
        result['made'] = made
        return result

    @api.model
    def set_team_cost_centre(self, department_id, cost_centre_id):
        """The team's usual cost centre (new contracts in it that have none).
        Writes no existing contract."""
        oc.require_manage(self.env)
        dept = self.env['hr.department'].sudo().browse(_as_id(department_id)).exists()
        if not dept or dept.company_id.id not in self._co_ids():
            raise UserError(_("That team is no longer there."))
        cc = self.env['pb.cost.centre'].sudo().browse(_as_id(cost_centre_id)).exists()
        if cc and cc.company_id != dept.company_id:
            raise UserError(_("Choose a cost centre of the team's own company."))
        dept.pb_cost_centre_id = cc.id or False
        return self.get_cost_centres()

    @api.model
    def search_people(self, query, company_id=None):
        oc.require_read(self.env)
        q = (query or '').strip()
        if len(q) < 2:
            return []
        dom = [('company_id', 'in', self._co_ids()), ('name', 'ilike', q)]
        if company_id:
            dom.append(('company_id', '=', _as_id(company_id)))
        return [{'id': e.id, 'name': e.name, 'team': e.department_id.name or ''}
                for e in self.env['hr.employee'].sudo().search(dom, limit=12)]

    @api.model
    def _move_targets(self, cost_centre, employee_ids=None, department_id=None):
        Contract = self.env['hr.contract'].sudo()
        dom = [('company_id', '=', cost_centre.company_id.id), ('state', '=', 'open')]
        if department_id:
            dept = self.env['hr.department'].sudo().browse(_as_id(department_id)).exists()
            if not dept:
                raise UserError(_("That team is no longer there."))
            emp_dom = [('department_id', 'child_of', dept.id)]
            emps = self.env['hr.employee'].sudo().search(emp_dom)
            dom.append(('employee_id', 'in', emps.ids))
        elif employee_ids:
            dom.append(('employee_id', 'in', [_as_id(e) for e in employee_ids]))
        else:
            raise UserError(_("Choose a team or the people to move."))
        return Contract.search(dom, limit=MAX_PEOPLE + 1)

    @api.model
    def _check_move(self, cost_centre_id, date_start):
        cc = self.env['pb.cost.centre'].sudo().browse(_as_id(cost_centre_id)).exists()
        if not cc or not cc.active or cc.company_id.id not in self._co_ids():
            raise UserError(_("Choose a cost centre from the list."))
        today = fields.Date.context_today(self)
        try:
            start = fields.Date.to_date(date_start) if date_start else None
        except (TypeError, ValueError):
            start = None
        if not start:
            raise UserError(_("Choose the date the new cost centre starts."))
        if start < today:
            raise UserError(_(
                "A cost centre change starts today or later. Payslips already "
                "made keep the cost centre they were paid under."))
        if start > today + timedelta(days=MAX_DAYS_AHEAD):
            raise UserError(_("Choose a date within the next twelve months."))
        return cc, start

    @api.model
    def preview_move(self, cost_centre_id, date_start, employee_ids=None,
                     department_id=None):
        oc.require_manage(self.env)
        cc, start = self._check_move(cost_centre_id, date_start)
        contracts = self._move_targets(cc, employee_ids, department_id)
        if len(contracts) > MAX_PEOPLE:
            raise UserError(_(
                "That is more than %s people at once. Choose a smaller team.",
                MAX_PEOPLE))
        already = contracts.filtered(lambda c: c.pb_cost_centre_id == cc)
        moving = contracts - already
        return {
            'moving': len(moving),
            'already': len(already),
            'names': moving[:8].mapped('employee_id.name'),
            'today': start == fields.Date.context_today(self),
            'from': str(start),
        }

    @api.model
    def move_people(self, cost_centre_id, date_start, employee_ids=None,
                    department_id=None, note=''):
        oc.require_manage(self.env)
        cc, start = self._check_move(cost_centre_id, date_start)
        contracts = self._move_targets(cc, employee_ids, department_id)
        if len(contracts) > MAX_PEOPLE:
            raise UserError(_(
                "That is more than %s people at once. Choose a smaller team.",
                MAX_PEOPLE))
        moving = contracts.filtered(lambda c: c.pb_cost_centre_id != cc)
        Move = self.env['pb.cost.centre.move'].sudo()
        # One waiting change per contract: a newer one replaces it.
        Move.search([('contract_id', 'in', moving.ids),
                     ('state', '=', 'scheduled')]).write({'state': 'cancelled'})
        moves = Move.create([{
            'contract_id': c.id, 'cost_centre_id': cc.id, 'date_start': start,
            'note': (note or '').strip()[:200] or False,
        } for c in moving])
        moves._pb_apply()
        done = len(moves.filtered(lambda m: m.state == 'done'))
        result = self.get_cost_centres()
        result['moved'] = done
        result['waiting'] = len(moves) - done
        return result

    @api.model
    def cancel_move(self, move_id):
        oc.require_manage(self.env)
        move = self.env['pb.cost.centre.move'].sudo().browse(_as_id(move_id)).exists()
        if not move or move.company_id.id not in self._co_ids():
            raise UserError(_("That change is no longer there."))
        if move.state != 'scheduled':
            raise UserError(_("Only a change still waiting for its date can be cancelled."))
        move.state = 'cancelled'
        return self.get_cost_centres()

    # ======================================================== hiring pause
    @api.model
    def _pause_meta(self, rec):
        reason = rec.pb_hiring_pause_reason_self if rec._name == 'hr.job' \
            else rec.pb_hiring_pause_reason
        return {
            'reason': reason or '',
            'by': rec.pb_hiring_pause_by.name or '',
            'on': str(rec.pb_hiring_pause_on or '')[:10],
        }

    @api.model
    def get_pauses(self):
        oc.require_read(self.env)
        co = self._co_ids()
        Job = self.env['hr.job'].sudo()
        open_by_company = {c.id: n for c, n in Job._read_group(
            [('company_id', 'in', co), ('no_of_recruitment', '>', 0)],
            ['company_id'], ['__count'])}
        open_by_team = {d.id: n for d, n in Job._read_group(
            [('company_id', 'in', co), ('no_of_recruitment', '>', 0),
             ('department_id', '!=', False)], ['department_id'], ['__count'])}
        companies = [dict(self._pause_meta(c), id=c.id, name=c.name,
                          paused=bool(c.pb_hiring_pause),
                          open_roles=open_by_company.get(c.id, 0))
                     for c in self._companies()]
        teams = []
        for d in self._teams():
            source = d._pb_pause_source() if d.pb_hiring_paused else d.browse()
            teams.append(dict(
                self._pause_meta(d), id=d.id, name=d.display_name,
                company=d.company_id.name or '', company_id=d.company_id.id,
                paused=bool(d.pb_hiring_pause),
                inherited=bool(d.pb_hiring_paused and not d.pb_hiring_pause),
                inherited_from=(source.display_name if source and source != d else ''),
                open_roles=open_by_team.get(d.id, 0)))
        roles = [dict(self._pause_meta(j), id=j.id, name=j.name,
                      team=j.department_id.display_name or '',
                      company=j.company_id.name or '')
                 for j in Job.search([('company_id', 'in', co),
                                      ('pb_hiring_pause_self', '=', True)], order='name')]
        return {'companies': companies, 'teams': teams, 'roles': roles,
                'can_pause': oc.can_pause(self.env)}

    @api.model
    def set_pause(self, kind, res_id, paused, reason=''):
        """Pause or restart hiring for a company, a team or one role."""
        oc.require_pause(self.env)
        reason = (reason or '').strip()[:240]
        rid = _as_id(res_id)
        if kind == 'company':
            rec = self.env['res.company'].sudo().browse(rid).exists()
            if not rec or rec.id not in self._co_ids():
                raise UserError(_("Choose one of your companies."))
            field, reason_field = 'pb_hiring_pause', 'pb_hiring_pause_reason'
        elif kind == 'team':
            rec = self.env['hr.department'].sudo().browse(rid).exists()
            if not rec or rec.company_id.id not in self._co_ids():
                raise UserError(_("That team is no longer there."))
            field, reason_field = 'pb_hiring_pause', 'pb_hiring_pause_reason'
        elif kind == 'role':
            rec = self._job(rid)
            field, reason_field = 'pb_hiring_pause_self', 'pb_hiring_pause_reason_self'
        else:
            raise UserError(_("That is not something this screen can do."))
        if paused and not reason:
            raise UserError(_(
                "Say why hiring is paused — people who try to hire will read it."))
        rec.write({
            field: bool(paused),
            reason_field: reason if paused else False,
            'pb_hiring_pause_by': self.env.user.id if paused else False,
            'pb_hiring_pause_on': fields.Datetime.now() if paused else False,
        })
        verb = _("Hiring paused") if paused else _("Hiring restarted")
        body = Markup('%s%s') % (verb, (': ' + reason) if paused and reason else '')
        if hasattr(rec, 'message_post'):
            rec.message_post(body=body)
        return self.get_pauses()
