# -*- coding: utf-8 -*-
"""X4 — a regular send of a saved Explorer view can go out in my layout.

The choice lives on the schedule (`layout_id`, "Send as"). The file is made
in `pb_explorer`'s one seam, `_pbx_attachment`, with the facade AS THE
RECIPIENT (their companies, divisions and language — FACTS §3, ledger
QF2-G1/G2), so each person still gets only their own figures (rail R2).

A layout never stops a send (rail R5): when it cannot be used the standard
Excel goes out instead and that person's history line says why
(`layout_failed`, with the reason kept as a code so it is shown in the
language of whoever reads the history).
"""
import contextvars
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .words import error_words
from .xlsx_fill import LayoutError

_logger = logging.getLogger(__name__)

# {user id: (code, sheet)} of the people in the send that is running now
# whose layout could not be used. Set by `_send_one`, filled by the hook.
LAYOUT_FAILS = contextvars.ContextVar('pbxl_layout_fails', default=None)


class PbExplorerSchedule(models.Model):
    _inherit = 'pb.explorer.schedule'

    layout_id = fields.Many2one('pb.excel.layout', string='Send as',
                                ondelete='set null', index=True)

    def _pbx_attachment(self, user, standard, explorer=None, spec=None):
        standard = super()._pbx_attachment(user, standard, explorer=explorer,
                                           spec=spec)
        layout = self.layout_id.sudo()
        if not layout or explorer is None:
            return standard
        try:
            if (layout.source_model, layout.source_id) != (
                    'pb.explorer.view', self.view_id.id):
                raise LayoutError('wrong_source')
            view = self.view_id.sudo()
            table = self.env['pb.excel.layout.board']._pbxl_clean_table(
                view._pbxl_table_for(explorer, spec))
            data, _notes = layout._pbxl_fill_with(table)
            return layout._pbxl_filename(), data, layout._pbxl_mimetype()
        except Exception as err:                           # noqa: BLE001
            code = err.code if isinstance(err, LayoutError) else 'unreadable'
            sheet = (err.params.get('sheet') if isinstance(err, LayoutError)
                     else '') or ''
            _logger.warning('pb_excel_layout: schedule %s, user %s: layout %s '
                            'not used (%s); the standard Excel was sent',
                            self.id, user.id, layout.id, code)
            fails = LAYOUT_FAILS.get()
            if fails is not None:
                fails[user.id] = (code, sheet)
            return standard

    def _send_one(self, trigger='schedule'):
        token = LAYOUT_FAILS.set({})
        try:
            summary = super()._send_one(trigger)
            fails = LAYOUT_FAILS.get() or {}
            if fails:
                sched = self.sudo()
                Log = self.env['pb.explorer.schedule.log'].sudo()
                logs = Log.search([('schedule_id', '=', sched.id),
                                   ('batch', '=', sched.send_count),
                                   ('user_id', 'in', list(fails)),
                                   ('state', '=', 'queued')])
                for log in logs:
                    code, sheet = fails[log.user_id.id]
                    log.write({'state': 'layout_failed',
                               'reason': '%s|%s' % (code, sheet)})
        finally:
            LAYOUT_FAILS.reset(token)
        return summary

    def _pbx_history(self):
        """`layout_failed` is a send that WENT (with the standard Excel): it
        counts as sent, and its line says why the layout was not used."""
        out = super()._pbx_history()
        Log = self.env['pb.explorer.schedule.log'].sudo()
        failed = Log.search([('schedule_id', '=', self.id),
                             ('state', '=', 'layout_failed')])
        if not failed:
            return out
        reasons = {}
        for log in failed:
            code, _sep, sheet = (log.reason or '').partition('|')
            reasons[(log.batch, log.user_id.name or _("Someone"))] = \
                error_words(self.env, code, {'sheet': sheet})
        for entry in out:
            extra = 0
            for line in entry['lines']:
                if line['state'] == 'layout_failed':
                    extra += 1
                    why = reasons.get((entry['batch'], line['name']), '')
                    line['label'] = _(
                        "Sent as the standard Excel — the layout could not be "
                        "used: %s", why) if why else _(
                        "Sent as the standard Excel — the layout could not be "
                        "used")
            if extra:
                entry['sent'] += extra
                entry['summary'] = _("Sent to %(sent)s of %(total)s",
                                     sent=entry['sent'],
                                     total=len(entry['lines']))
        return out

    def _pbx_payload(self):
        out = super()._pbx_payload()
        layout = self.layout_id.sudo()
        out.update({
            'layout_id': layout.id or 0,
            'layout_name': layout.name or '',
            'layout_ok': bool(layout.sheet_ok) if layout else True,
        })
        return out


class PbExplorerScheduleLog(models.Model):
    _inherit = 'pb.explorer.schedule.log'

    state = fields.Selection(
        selection_add=[('layout_failed', 'Sent as the standard Excel')],
        ondelete={'layout_failed': lambda recs: recs.write(
            {'state': 'queued'})})
    reason = fields.Char(string='Why')


class PbExplorerScheduleFacade(models.AbstractModel):
    """The drawer's "Send as" choice. Every entry point still passes the
    Explorer's own checks first (`super()`)."""
    _inherit = 'pb.explorer'

    @api.model
    def _pbxl_layouts_for_view(self, view):
        Layout = self.env['pb.excel.layout'].sudo()
        uid = self.env.uid
        return Layout.search([('source_model', '=', 'pb.explorer.view'),
                              ('source_id', '=', view.id),
                              '|', ('user_id', '=', uid),
                              ('shared', '=', True)])

    @api.model
    def schedule_drawer(self, view_id):
        out = super().schedule_drawer(view_id)
        view = self.env['pb.explorer.view'].browse(out['view']['id'])
        out['layouts'] = [{'id': l.id, 'name': l.name,
                           'ok': bool(l.sheet_ok),
                           'mine': l.user_id.id == self.env.uid}
                          for l in self._pbxl_layouts_for_view(view)]
        return out

    @api.model
    def schedule_save(self, view_id, vals, schedule_id=False):
        vals = vals if isinstance(vals, dict) else {}
        layout = self.env['pb.excel.layout']
        raw = vals.get('layout_id')
        if raw:
            try:
                wanted = int(raw)
            except (TypeError, ValueError):
                wanted = 0
            view = self._pbx_own_view(view_id)
            layout = self._pbxl_layouts_for_view(view).filtered(
                lambda l: l.id == wanted)
            if not layout:
                raise UserError(_("That Excel layout is no longer available. "
                                  "Choose another, or the standard Excel."))
        out = super().schedule_save(view_id, vals, schedule_id=schedule_id)
        if 'layout_id' in vals:
            sched = self.env['pb.explorer.schedule'].with_context(
                active_test=False).browse(out['id'])
            sched.layout_id = layout.id or False
            out = sched._pbx_payload()
        return out
