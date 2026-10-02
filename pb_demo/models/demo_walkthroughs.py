# -*- coding: utf-8 -*-
"""LEARN REFRESH step 6 — the demo world walks every lesson on real data.

Two things the walkthroughs needed that the demo world did not have:

ITEM 6 · A PAY RUN GOES THROUGH APPROVAL. The demo company's pay-run route
resolved to "No approval needed", so a submitted run finished at once and
nobody could watch the route. `_ensure_demo_payrun_route` binds the company to
its real three-step route (Payroll check → HR lead review → Finance approval)
and seats demo people in it: the demo login holds the first step, two DEMO
users the other two. Whoever held a seat before stays on it as the backup.
It never touches a run: the April/May/June runs keep their states.

ITEM 7 · LIVE EXAMPLES. One open pay review with scored rows (the budget meter
about half way, one row that breaks a limit and stops approval) and one final
settlement that the month's load made and nobody has checked yet ("Ready to
check"). Leavers at every step, trial periods, growth plans, contracts ending
and hiring roles were already in the demo world (the boards looked empty only
to a login standing in another company, or one without access to the screen).

Both are idempotent and run ONLY on the apex demo database (`payobook`, the
company "Payobook Vietnam JSC"): at the end of `action_generate_all` so they
survive a regeneration, and from this module's migration. Every record made
here is registered with the Load/Delete demo data register, named DEMO.
"""
import json
import logging
from datetime import date

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

DEMO_DB = 'payobook'
DEMO_COMPANY = 'Payobook Vietnam JSC'

#: responsibility key -> login of the demo person who holds the seat
ROUTE_SEATS = (
    ('payroll_mgr', 'demo@payobook.com'),
    ('hr_lead', 'demo.a3.an@example.com'),
    ('finance', 'demo.a3.binh@example.com'),
)

REVIEW_NAME = 'DEMO Retail pay review · 2026'
REVIEW_LIMIT_PCT = 15.0


class PbDemoGeneratorWalkthroughs(models.TransientModel):
    _inherit = 'pb.demo.generator'

    def action_generate_all(self):
        res = super().action_generate_all()
        try:
            self.ensure_walkthrough_world()
        except Exception:       # noqa: BLE001 — a demo world is still built
            _logger.exception('pb_demo: walkthrough examples not laid')
        return res

    # ------------------------------------------------------------ the gate
    @api.model
    def _walkthrough_company(self):
        if self.env.cr.dbname != DEMO_DB:
            return self.env['res.company']
        return self.env['res.company'].sudo().search(
            [('name', '=', DEMO_COMPANY)], limit=1)

    @api.model
    def ensure_walkthrough_world(self):
        company = self._walkthrough_company()
        if not company:
            _logger.info('pb_demo: not the demo database — no walkthrough '
                         'examples here')
            return {}
        out = {}
        for key, fn in (('route', self._ensure_demo_payrun_route),
                        ('review', self._ensure_demo_pay_review),
                        ('settlement', self._ensure_demo_settlement_to_check)):
            try:
                with self.env.cr.savepoint():
                    out[key] = fn(company)
            except Exception as e:      # noqa: BLE001 — one piece, one reason
                _logger.exception('pb_demo: walkthrough piece %s failed', key)
                out[key] = 'failed: %s' % e
        _logger.info('pb_demo: walkthrough examples %s', out)
        return out

    @api.model
    def _walk_register(self, records, label):
        seed = self.env.get('pb.demo.seed')
        if seed is not None and records:
            seed.sudo().register(records, label)

    # ---------------------------------------------------- item 6: the route
    @api.model
    def _ensure_demo_payrun_route(self, company):
        env = self.env(su=True)
        process = env['biz.approval.process']._by_key('payrun') \
            if 'biz.approval.process' in env else False
        if not process:
            return 'no pay-run process'
        Workflow = env['biz.approval.workflow']
        Binding = env['biz.approval.binding'].with_context(active_test=False)
        Responsibility = env['biz.approval.responsibility'].with_context(
            active_test=False)
        # the real route: the one the pay-run seed laid, published
        workflow = Workflow.search([
            ('company_id', '=', company.id), ('process_id', '=', process.id),
            ('name', '=', 'Pay run approval')], limit=1)
        if not workflow:
            env['hr.payslip.run']._approval_seed_default(company)
            workflow = Workflow.search([
                ('company_id', '=', company.id),
                ('process_id', '=', process.id),
                ('name', '=', 'Pay run approval')], limit=1)
        if not workflow or not workflow.version_ids.filtered(
                lambda v: v.status == 'published'):
            return 'no published pay-run route'

        # THE ROUTE'S SHAPE, FOR A DEMO. Two things in the default route stop
        # one demo login from walking it: "independent" hands the first step
        # to the backup when the demo login sent the run in itself, and the HR
        # lead step is looked up per part of the business (no demo person
        # holds those). The demo company's route keeps its three steps and its
        # "different people per step" rule; the HR lead is company-wide and a
        # person may check a run they sent in.
        self._demo_route_shape(workflow)

        # the seats
        seated = []
        for key, login in ROUTE_SEATS:
            role = env['biz.approval.role'].search([('key', '=', key)], limit=1)
            user = env['res.users'].with_context(active_test=False).search(
                [('login', '=', login)], limit=1)
            if not role or not user:
                seated.append('%s: nobody (%s missing)' % (key, login))
                continue
            if company not in user.company_ids:
                user.write({'company_ids': [(4, company.id)]})
            held = Responsibility.search([
                ('company_id', '=', company.id), ('role_id', '=', role.id),
                ('scope_key', '=', '')], limit=1)
            if held:
                if held.user_id != user or not held.active:
                    vals = {'user_id': user.id, 'active': True}
                    if held.user_id and held.user_id != user \
                            and not held.backup_user_id:
                        vals['backup_user_id'] = held.user_id.id
                    held.write(vals)
            else:
                Responsibility.create({
                    'company_id': company.id, 'role_id': role.id,
                    'scope_key': '', 'scope_label': company.name,
                    'user_id': user.id,
                    'date_from': fields.Date.context_today(self),
                    'note': 'DEMO: the demo world walks its pay runs '
                            'through the real route.',
                })
            seated.append('%s: %s' % (key, user.name))

        # the binding: the real route on, "No approval needed" off
        company_bindings = Binding.search([
            ('company_id', '=', company.id), ('process_id', '=', process.id),
            ('scope_key', '=', '')])
        for binding in company_bindings:
            if binding.workflow_id != workflow and binding.active:
                binding.write({'active': False})
        mine = company_bindings.filtered(lambda b: b.workflow_id == workflow)
        if mine:
            if not mine[:1].active:
                mine[:1].write({'active': True})
        else:
            Binding.create({
                'company_id': company.id, 'process_id': process.id,
                'scope_key': '', 'scope_label': company.name,
                'kind_key': 'any', 'workflow_id': workflow.id,
                'mode': 'follow',
                'note': 'DEMO: every demo pay run follows the real route.',
            })
        return '; '.join(seated)

    @api.model
    def _demo_route_shape(self, workflow):
        env = self.env(su=True)
        published = workflow.version_ids.filtered(
            lambda v: v.status == 'published').sorted('revision')[-1:]
        definition = json.loads(json.dumps(published.definition or {}))
        steps = definition.get('steps') or []
        guards = definition.setdefault('safeguards', {})
        changed = False
        for step in steps:
            who = step.get('who') or {}
            if who.get('mode') == 'role' and who.get('scope') == 'area':
                who['scope'] = 'company'
                changed = True
        if guards.get('independent'):
            guards['independent'] = False
            changed = True
        if not changed:
            return False
        Version = env['biz.approval.workflow.version']
        draft = workflow.version_ids.filtered(
            lambda v: v.status == 'draft').sorted('revision')[-1:]
        if draft:
            draft.write({'definition': definition})
        else:
            draft = Version.create({
                'workflow_id': workflow.id,
                'revision': max(workflow.version_ids.mapped('revision') or [0]) + 1,
                'status': 'draft', 'definition': definition})
        admin = self.env.ref('base.user_admin', raise_if_not_found=False)
        engine = env['biz.approval.engine'].with_user(admin).sudo()
        checks = engine.validate_for_publish(draft.id)
        if checks['errors']:
            _logger.warning('pb_demo: demo route refused: %s',
                            [e['code'] for e in checks['errors']])
            return False
        engine.publish(draft.id, draft.draft_revision, None,
                       'DEMO: one demo login can walk a pay run through',
                       [w['code'] for w in checks['warnings']])
        return True

    # ------------------------------------------------ item 7: a pay review
    @api.model
    def _ensure_demo_pay_review(self, company):
        env = self.env(su=True)
        if 'pb.pay.review' not in env:
            return 'no pay reviews here'
        Review = env['pb.pay.review']
        review = Review.search([('name', '=', REVIEW_NAME)], limit=1)
        if review:
            return 'kept %s (%s people)' % (review.name, review.people)
        division = env['pb.division'].search([('name', '=', 'Retail')],
                                             limit=1) \
            if 'pb.division' in env else False
        values = {'name': REVIEW_NAME,
                  'scope_kind': 'division' if division else 'company',
                  'scope_ref': division.id if division else company.id,
                  'year': date.today().year,
                  'note': 'DEMO: an open review for the walkthroughs.'}
        Reviews = env['pb.pay.reviews']
        if not Reviews._can_write():
            # the gate asks the person, not the superuser flag: act as the
            # built-in administrator, the way the demo world is generated
            admin = self.env.ref('base.user_admin', raise_if_not_found=False)
            Reviews = Reviews.with_user(admin).sudo()
        made = Reviews.with_company(company).with_context(
            allowed_company_ids=[company.id]).create_review(values)
        review = Review.browse(made['id'])
        # one limit that STOPS approval, so a row can break it
        if not review.limit_ids.filtered(lambda l: l.kind == 'max_raise_pct'):
            env['pb.pay.review.limit'].create({
                'review_id': review.id, 'kind': 'max_raise_pct',
                'value': REVIEW_LIMIT_PCT, 'enforcement': 'block'})
        # every row scored: a person nobody has scored gets a middle score
        lines = review.line_ids.sorted('id')
        for line in lines.filtered(lambda l: not l.rating):
            line.rating = 3
        review.apply_guidance_to(lines)
        # one row over the limit — the one that stops approval
        if lines:
            lines[0].set_proposal(pct=REVIEW_LIMIT_PCT + 7.0)
        # the chips (what stops approval) are worked out by the review, not by
        # the row: ask it, or the meter counts a row it has not looked at
        review.recompute_chips(lines)
        review.invalidate_recordset()
        # the budget meter about half way
        review.budget_amount = round((review.allocated_amount or 0.0) * 2, -6)
        review.mark_fairness_dirty()
        self._walk_register(review, 'DEMO pay review for the walkthroughs')
        return 'made %s (%s people, %s blocked)' % (
            review.name, review.people, review.lines_blocked)

    # ------------------------------------- item 7: a settlement to check
    @api.model
    def _ensure_demo_settlement_to_check(self, company):
        env = self.env(su=True)
        if 'hr.full.final.settlement' not in env \
                or 'pb.journey.case' not in env:
            return 'no settlements here'
        FF = env['hr.full.final.settlement']
        waiting = FF.search([('company_id', '=', company.id),
                             ('source', '=', 'auto'),
                             ('state', 'in', ('draft', 'returned'))], limit=1)
        if waiting:
            return 'kept %s' % waiting.employee_id.name
        # A leaver whose last day has passed and who has no settlement yet —
        # the lifecycle stories' people carry no payslips of their own, so the
        # figures are what the Retail end-of-month scheme works out for them,
        # the same call the monthly load makes (`_compute_from_config`); where
        # that gives nothing, a Retail payslip's figures stand in (DEMO data).
        today = fields.Date.context_today(self)
        cases = env['pb.journey.case'].search([
            ('company_id', '=', company.id),
            ('case_type', '=', 'offboarding'),
            ('state', 'in', ('draft', 'active', 'on_hold')),
            ('anchor_date', '!=', False),
        ], order='anchor_date')
        cases = cases.filtered(lambda c: c.anchor_date < today) \
            + cases.filtered(lambda c: c.anchor_date >= today)
        Config = env['hr.formula.config']
        config = Config.search([('company_id', '=', company.id),
                                ('code', 'ilike', 'RETAIL'),
                                ('cycle_type', '!=', 'mid'),
                                ('state', '=', 'active')], limit=1) \
            or Config.search([('company_id', '=', company.id),
                              ('state', '=', 'active')], limit=1)
        if not config:
            return 'no active pay scheme'
        stand_in = env['hr.payslip'].search([
            ('formula_config_id', '=', config.id), ('state', '!=', 'cancel'),
            ('formula_computed_values', '!=', False)],
            order='date_to desc, id desc', limit=1)
        for case in cases:
            emp = case.employee_id
            if not emp or FF.search_count([('employee_id', '=', emp.id)]):
                continue
            contract = env['hr.contract'].search(
                [('employee_id', '=', emp.id)], order='date_start desc',
                limit=1)
            inputs, values = {}, {}
            if contract:
                try:
                    with self.env.cr.savepoint():
                        inputs, values = FF._compute_from_config(
                            config, emp, contract, {})
                except Exception:       # noqa: BLE001 — fall back below
                    inputs, values = {}, {}
            if not values and stand_in:
                inputs = json.loads(stand_in.formula_input_values or '{}')
                values = json.loads(stand_in.formula_computed_values or '{}')
            if not values:
                continue
            settlement = FF.create({
                'name': 'FNF/%s/%s' % (emp.name, case.anchor_date),
                'employee_id': emp.id,
                'company_id': company.id,
                'contract_id': contract.id or False,
                'formula_config_id': config.id,
                'settlement_date': case.anchor_date,
                'date_from': case.anchor_date.replace(day=1),
                'date_to': case.anchor_date,
                'source': 'auto',
                'raw_data_json': json.dumps({}),
                'input_values_json': json.dumps(inputs, default=str),
                'computed_values_json': json.dumps(values, default=str),
                'currency_id': (config.currency_id or company.currency_id).id,
            })
            self._walk_register(settlement,
                                'DEMO final settlement waiting to be checked')
            return 'made %s (%s, %s)' % (emp.name, settlement.net_payable,
                                         settlement.state)
        return 'no leaver without a settlement'
