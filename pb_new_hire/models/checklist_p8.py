# -*- coding: utf-8 -*-
"""NEWHIRE P8 — the joining checklist.

G. The checklist follows the Country of work. `pb.zoho.pipeline._open_case`
   (every door: this studio, Hiring's "Confirm they joined", the connected
   system) picked the onboarding template by NATIONALITY (ledger NH19). It now
   runs with the person's Country of work in the context, and
   `pb.journey.template.pick_for` reads it for onboarding: that country's own
   template, else the one with no country. Nationality (today's rule) is used
   only when the Country of work is empty. A checklist already running is
   returned by `_open_case` before any template is picked, so no open case is
   re-templated. Step 6's preview uses the same function
   (`_pbnh_pick_onboarding`).

F. Equipment handed over ticks the "Laptop and equipment" step. When a
   request that counts for that step is handed over (`fulfilment` delivered
   or confirmed — `action_fulfil`, the Equipment board, any write), the step
   is ticked by the system (author: the system user) with the note "Ticked
   when the laptop was handed over". A request counts when it answers the
   step (`journey_task_id`: the studio, Hiring's checklist) or is a laptop for
   the person made since the checklist opened (by hand on the Equipment
   board). pb_assets' own tick in `action_fulfil` ran as the person pressing
   it and was lost (logged) for anybody outside the lifecycle roles; this one
   runs as the system first, so that tick then finds the step done.
   Idempotent; never un-ticked. Until then the step reads "Requested" on
   Journeys and the New joiners drawer (display only, nothing written).
"""
import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)

#: The Country of work an onboarding template is picked for (a code, VN…).
WORK_CTX = 'pbnh_work_country'
#: The joining step equipment answers (`pb_onboarding.step_rize_laptop`).
LAPTOP_KEY = 'asset_laptop'
HANDED = ('delivered', 'confirmed')
DEAD = ('refused', 'cancelled')
OPEN_TASK = ('pending', 'in_progress', 'blocked')


class PbJourneyTemplateNH(models.Model):
    _inherit = 'pb.journey.template'

    @api.model
    def pick_for(self, case_type, country_id=False, company_id=False):
        code = self.env.context.get(WORK_CTX)
        if case_type == 'onboarding' and code:
            return self._pbnh_pick_onboarding(code, country_id, company_id)
        return super().pick_for(case_type, country_id, company_id)

    @api.model
    def _pbnh_pick_onboarding(self, work_code, nationality_id=False, company_id=False):
        """The joining checklist for somebody working in `work_code`: that
        country's own, else the one with no country. Today's rule (the
        nationality) only when there is no Country of work."""
        work = self.env['res.country'].sudo().search([('code', '=', work_code)], limit=1) \
            if work_code else self.env['res.country']
        return super().pick_for('onboarding', work.id if work else (nationality_id or False),
                                company_id)


class PbZohoPipelineNH(models.AbstractModel):
    _inherit = 'pb.zoho.pipeline'

    def _open_case(self, employee, case_type, anchor_date, company):
        pipeline = self
        if case_type == 'onboarding' and employee and 'payroll_country' in employee._fields:
            pipeline = self.with_context(**{WORK_CTX: employee.sudo().payroll_country or False})
        return super(PbZohoPipelineNH, pipeline)._open_case(employee, case_type, anchor_date, company)


class PbAssetRequestNH(models.Model):
    _inherit = 'pb.asset.request'

    def write(self, vals):
        res = super().write(vals)
        if vals.get('fulfilment') in HANDED:
            for request in self:
                try:
                    request._pbnh_tick_laptop_step()
                except Exception:               # noqa: BLE001 — never lose a handover
                    _logger.warning('pb_new_hire: the laptop step was not ticked for %s',
                                    request.id, exc_info=True)
        return res

    def _pbnh_laptop_tasks(self):
        """The person's open "Laptop and equipment" steps on a running
        joining checklist."""
        self.ensure_one()
        if 'pb.journey.task' not in self.env or not self.employee_id:
            return self.env['pb.journey.task'] if 'pb.journey.task' in self.env else None
        Task = self.env['pb.journey.task'].sudo()
        domain = [('case_id.employee_id', '=', self.employee_id.id),
                  ('case_id.case_type', '=', 'onboarding'),
                  ('case_id.state', 'in', ('draft', 'active', 'on_hold')),
                  ('state', 'in', OPEN_TASK)]
        tasks = Task.search(domain + [('automation_key', '=', LAPTOP_KEY)])
        if self.journey_task_id and self.journey_task_id.state in OPEN_TASK:
            tasks |= self.journey_task_id.sudo()
        return tasks

    def _pbnh_step_requests(self, task):
        """Every live request that counts for `task`."""
        Request = self.env['pb.asset.request'].sudo()
        laptop = self.env.ref('pb_assets.cat_laptop', raise_if_not_found=False)
        domain = [('employee_id', '=', task.case_id.employee_id.id), ('state', 'not in', DEAD)]
        linked = Request.search(domain + [('journey_task_id', '=', task.id)])
        loose = Request.browse()
        if laptop:
            loose = Request.search(domain + [('journey_task_id', '=', False),
                                             ('category_id', '=', laptop.id),
                                             ('create_date', '>=', task.case_id.create_date)])
        return linked | loose

    def _pbnh_tick_laptop_step(self):
        self.ensure_one()
        if self.fulfilment not in HANDED or self.state in DEAD:
            return False
        tasks = self._pbnh_laptop_tasks()
        if not tasks:
            return False
        root = self.env.ref('base.user_root')
        ticked = False
        for task in tasks:
            if self.sudo() not in self._pbnh_step_requests(task):
                continue
            task._settle('done', by_user=root, note=_("Ticked when the laptop was handed over"))
            task.case_id.sudo().message_post(body=_("%(step)s — done.", step=task.name))
            ticked = True
        return ticked


class PbJourneysNH(models.AbstractModel):
    _inherit = 'pb.journeys'

    @api.model
    def get_case(self, case_id):
        out = super().get_case(case_id)
        try:
            self._pbnh_requested_lines(out)
        except Exception:                       # noqa: BLE001 — a sub-line never breaks a case
            _logger.warning('pb_new_hire: the "Requested" line failed', exc_info=True)
        return out

    @api.model
    def _pbnh_requested_lines(self, out):
        """"Requested" under the laptop step while its equipment is on the way."""
        rows = [t for t in (out or {}).get('tasks') or []
                if t.get('state') in OPEN_TASK and not t.get('note')]
        if not rows or 'pb.asset.request' not in self.env:
            return
        Task = self.env['pb.journey.task'].sudo()
        for row in rows:
            task = Task.browse(row['id']).exists()
            if not task or task.automation_key != LAPTOP_KEY:
                continue
            requests = self.env['pb.asset.request']._pbnh_step_requests(task)
            if requests:
                row['note'] = _("Requested")
