# -*- coding: utf-8 -*-
"""Jobs inside the company on the employee home (pb_me_portal's hooks only).

  * the tile `/my/jobs` sits in Growth (registered at import, the
    `pb_training/models/me_home_tile.py` precedent — no pb_me_portal edit);
  * "My requests" lists the person's own staff applications, in the plain
    employee words, never a stage name;
  * "Needs you" tells a MANAGER, once an offer is near, that somebody in
    their team may move (E4). Nothing about an application reaches the
    manager's home before that.
"""
import logging
from datetime import datetime, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

JOBS_TILE = '/my/jobs'
MOVES_PAGE = '/my/jobs/moves'
#: How long a "may move" line stays on a manager's home after they were told.
TOLD_DAYS = 21

try:
    from odoo.addons.pb_me_portal.models import pb_me_home as _pbme
    _pbme.TILES.setdefault(JOBS_TILE, {
        'group': 'growth',
        'icon': 'briefcase',
        'tone': 'teal',
        'seq': _pbme.GROUPS.index('growth') * 100 + 6,
        # No short `text`: pb_me_portal's home test wants every short text in
        # its own .po; the template's own words are translated here.
    })
except Exception:                       # noqa: BLE001 — a tile is not fatal
    _logger.warning('pb_hiring_internal: the jobs tile could not be placed on '
                    'the employee home', exc_info=True)


class PbMeHomeInternalJobs(models.AbstractModel):
    _inherit = 'pb.me.home'

    # -------------------------------------------------------------- manager
    @api.model
    def _pbhi_team_moves(self, manager):
        """Applications of `manager`'s people whose manager was told (an
        offer is near) and that are still about a move. Read under sudo for
        the session's own employee (the caller passes `emp` from the home)."""
        if not manager:
            return self.env['hr.applicant'].sudo().browse()
        since = fields.Datetime.now() - timedelta(days=TOLD_DAYS)
        apps = self.env['hr.applicant'].sudo().with_context(
            active_test=False).search([
                ('pb_internal', '=', True),
                ('pb_manager_told_id', '=', manager.id),
                ('pb_manager_told_on', '!=', False),
            ], order='pb_manager_told_on desc', limit=50)
        return apps.filtered(
            lambda a: a._pbhi_state() in ('offer', 'accepted')
            or (a._pbhi_state() == 'moved' and a.pb_manager_told_on >= since))

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        _ = self.env._
        moves = self._pbhi_team_moves(emp)
        n = len(moves)
        if not n:
            return
        if n == 1:
            label = _('%s may move to another role', moves.employee_id.name or '')
            sentence = _('Somebody in your team may move to another role.')
        else:
            label = _('%s people in your team may move to another role', n)
            sentence = _('%s people in your team may move to another role.', n)
        put('pbhi_team_move', n, MOVES_PAGE, label=label,
            sub=_('An offer is near. HR will talk to you about the timing.'),
            icon='users', tone='blue', sentence=sentence)

    # ---------------------------------------------------------- my requests
    @api.model
    def _my_requests_sources(self):
        sources = super()._my_requests_sources()
        _ = self.env._
        sources.append({
            'key': 'pbhi_internal_role', 'model': 'hr.applicant',
            'label': _('Internal role'), 'icon': 'briefcase',
            'employee_field': 'employee_id', 'date_field': 'create_date',
            'state_field': 'pb_internal',
            # The words, per employee state (EMPLOYEE_STATES).
            'states': {
                'received': (_('Received'), 'wait'),
                'considered': (_('Being considered'), 'wait'),
                'offer': (_('Offer being prepared'), 'wait'),
                'accepted': (_('Offer accepted'), 'ok'),
                'moved': (_('Moving to this role'), 'ok'),
                'closed': (_('Not this time'), 'no'),
                'withdrawn': (_('Withdrawn'), 'off'),
            },
            'url': lambda rec: '%s/%s' % (JOBS_TILE, rec.pb_requisition_id.id)
            if rec.pb_requisition_id else JOBS_TILE,
            'title': lambda rec: rec.pb_requisition_id._pbhi_title()
            if rec.pb_requisition_id else (rec.job_id.name or ''),
        })
        return sources

    @api.model
    def _my_requests_rows(self, src, emp):
        """The internal-role source reads ONLY the person's staff
        applications (an outside hire's old candidate row also points at
        their employee record) and says the employee's word for each."""
        if src.get('key') != 'pbhi_internal_role':
            return super()._my_requests_rows(src, emp)
        apps = self.env['hr.applicant'].sudo().with_context(
            active_test=False).search([
                ('employee_id', '=', emp.id), ('pb_internal', '=', True)],
                order='id desc', limit=100)
        rows = []
        for rec in apps:
            state = rec._pbhi_state()
            label, tone = src['states'].get(state) or (state, 'off')
            when = rec.create_date
            if not isinstance(when, datetime):
                when = datetime.combine(when, datetime.min.time())
            bucket = {'act': 'act', 'wait': 'wait'}.get(tone, 'done')
            rows.append({
                'key': src['key'], 'model': src['model'], 'id': rec.id,
                'kind': src['label'], 'icon': src['icon'],
                'title': src['title'](rec), 'state': state,
                'state_label': label, 'tone': tone, 'bucket': bucket,
                'url': src['url'](rec), 'date': when,
                'created': rec.create_date,
            })
        return rows
