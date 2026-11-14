# -*- coding: utf-8 -*-
"""Named Explorer views people save, open again and share (WDGAP QF2 A).

A saved view is a QUESTION, not an answer: it keeps the cleaned spec and,
when the period on screen was one of the seven moving starting points, the
key of that starting point. "Last month" saved in November opens on
November's last month and in December on December's. A stretch somebody drew
by hand is kept as the two dates it was, and labelled "Fixed dates".

Opening a view runs the stored spec through `_clean_spec` again, and the
query narrows by the READER's companies and divisions at query time, so a
view never widens what the person opening it may see (R7, R2). Record rules in
`security/pb_explorer_view_rules.xml` enforce private / shared / owner-only
writes; every RPC here also passes the Explorer gate first.

Cloned from `pb_filter_kit/models/filter_view.py` (FACTS §2) rather than
reusing it: that model has no Explorer gate, replaces a non-dict payload with
`{}` and is wired to the list mixin.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

NAME_MAX = 80
VIEW_CAP = 50              # saved views per owner; stated in the refusal
# The moving starting points a saved view may follow. 'all' (Everything) has
# no dates at all, so it moves trivially and is stored as itself.
MOVING = ('this_month', 'last_month', 'this_quarter', 'last_quarter',
          'this_year', 'last_year', 'all')
# Only these keys of a spec are worth keeping; anything else a client sends is
# dropped before it is stored (R7).
SPEC_KEYS = ('measure', 'dimension', 'grain', 'chart', 'filters', 'date_from',
             'date_to', 'limit', 'advances', 'currency', 'target_currency',
             'per_head', 'path')


class PbExplorerView(models.Model):
    _name = 'pb.explorer.view'
    _description = 'Saved Explorer view'
    _order = 'sequence, name, id'

    name = fields.Char(required=True)
    user_id = fields.Many2one('res.users', string='Saved by', required=True,
                              index=True, ondelete='cascade',
                              default=lambda self: self.env.user)
    shared = fields.Boolean(string='Everyone who can open the Explorer')
    spec = fields.Json(string='Question', default=dict)
    # '' = the two dates in `spec` are fixed; a key of MOVING = follow it.
    period_preset = fields.Char(string='Period')
    sequence = fields.Integer(default=10)
    schedule_ids = fields.One2many('pb.explorer.schedule', 'view_id',
                                   string='Regular sends')

    # ------------------------------------------------------------ helpers
    @api.model
    def _pbx_clean_name(self, name):
        name = ' '.join((name or '').split())[:NAME_MAX]
        if not name:
            raise UserError(_("Give the view a name."))
        return name

    @api.model
    def _pbx_store(self, spec):
        """(clean spec, preset) for storage. The spec is cleaned by the same
        method every query uses, so nothing unknown is ever kept."""
        explorer = self.env['pb.explorer']
        raw = {k: v for k, v in (spec if isinstance(spec, dict) else {}).items()
               if k in SPEC_KEYS}
        clean = explorer._clean_spec(raw)
        period = explorer._resolve_period(clean)
        preset = period.get('preset') or ''
        if preset not in MOVING:
            preset = ''
        return clean, preset

    def _pbx_spec_now(self, today=None):
        """The stored question, with a moving period resolved for `today`,
        re-cleaned. Never raises on a stored spec that no longer fits."""
        self.ensure_one()
        explorer = self.env['pb.explorer']
        spec = dict(self.spec or {}) if isinstance(self.spec, dict) else {}
        spec = {k: v for k, v in spec.items() if k in SPEC_KEYS}
        preset = self.period_preset or ''
        if preset == 'all':
            spec['date_from'] = spec['date_to'] = None
        elif preset in MOVING:
            for entry in explorer._period_presets(today):
                if entry['key'] == preset:
                    spec['date_from'] = entry['date_from']
                    spec['date_to'] = entry['date_to']
                    break
        return explorer._clean_spec(spec)

    def _pbx_drift(self):
        """True when part of the stored question no longer exists here (a
        measure, a breakdown, a filter) and opening it fell back to a default."""
        self.ensure_one()
        stored = self.spec if isinstance(self.spec, dict) else {}
        clean = self.env['pb.explorer']._clean_spec(stored)
        for key in ('measure', 'dimension', 'grain', 'chart'):
            if stored.get(key) and stored.get(key) != clean.get(key):
                return True
        raw_filters = stored.get('filters') if isinstance(
            stored.get('filters'), dict) else {}
        return any(k not in clean['filters'] for k in raw_filters
                   if raw_filters.get(k))

    def _pbx_period_label(self):
        """What the saved period MEANS, in words: a moving starting point
        says that it moves; fixed dates say that they are fixed."""
        self.ensure_one()
        explorer = self.env['pb.explorer']
        preset = self.period_preset or ''
        if preset == 'all':
            return _("Everything")
        if preset in MOVING:
            words = {p['key']: p['label'] for p in explorer._period_presets()}
            return _("%(period)s, moves with the calendar",
                     period=words.get(preset, preset))
        spec = self.spec if isinstance(self.spec, dict) else {}
        start, end = spec.get('date_from'), spec.get('date_to')
        if not start and not end:
            return _("Everything")
        return _("Fixed dates: %(start)s to %(end)s",
                 start=start or '…', end=end or '…')

    def _pbx_payload(self):
        self.ensure_one()
        uid = self.env.uid
        mine = self.user_id.id == uid
        spec = self.spec if isinstance(self.spec, dict) else {}
        own_schedules = self.sudo().with_context(
            active_test=False).schedule_ids.filtered(
            lambda s: s.user_id.id == uid) if mine else self.env[
                'pb.explorer.schedule']
        return {
            'id': self.id,
            'name': self.name,
            'shared': bool(self.shared),
            'mine': mine,
            'owner': '' if mine else (self.user_id.sudo().name or ''),
            'period_label': self._pbx_period_label(),
            'preset': self.period_preset or '',
            'measure': spec.get('measure') or '',
            'schedules': len(own_schedules),
            'schedules_on': len(own_schedules.filtered('active')),
        }

    def _pbx_own(self):
        """Refuse, in words, a change to somebody else's view. The record
        rules refuse it anyway; this only makes the refusal readable."""
        for view in self:
            if view.user_id.id != self.env.uid and \
                    not self.env.user.has_group('base.group_system'):
                raise AccessError(_("Only the person who saved this view can "
                                    "change it."))

    # ---------------------------------------------------------------- api
    @api.model
    def pbx_save(self, name, spec=None, shared=False):
        """A new view owned by the current user; returns its payload."""
        self.env['pb.explorer']._require()
        if self.search_count([('user_id', '=', self.env.uid)]) >= VIEW_CAP:
            raise UserError(_("You already have %s saved views. Delete one "
                              "you no longer use first.", VIEW_CAP))
        clean, preset = self._pbx_store(spec)
        view = self.create({
            'name': self._pbx_clean_name(name),
            'spec': clean,
            'period_preset': preset,
            'shared': bool(shared),
            'user_id': self.env.uid,
        })
        return view._pbx_payload()

    def pbx_update(self, vals):
        """Rename, share or unshare, or overwrite the question of one of
        your own views."""
        self.ensure_one()
        self.env['pb.explorer']._require()
        self._pbx_own()
        vals = vals if isinstance(vals, dict) else {}
        clean = {}
        if 'name' in vals:
            clean['name'] = self._pbx_clean_name(vals['name'])
        if 'shared' in vals:
            clean['shared'] = bool(vals['shared'])
        if 'spec' in vals:
            spec, preset = self._pbx_store(vals['spec'])
            clean.update({'spec': spec, 'period_preset': preset})
        if clean:
            self.write(clean)
        return self._pbx_payload()

    def pbx_delete(self):
        self.ensure_one()
        self.env['pb.explorer']._require()
        self._pbx_own()
        # Its regular sends go with it (ondelete='cascade' on the schedule);
        # sudo because a schedule's log is written by the system, not by you.
        self.sudo().with_context(active_test=False).schedule_ids.unlink()
        self.unlink()
        return True


class PbExplorerViews(models.AbstractModel):
    """The Explorer facade's view entry points (kept out of `pb_explorer.py`,
    which test_08 asserts never writes)."""
    _inherit = 'pb.explorer'

    @api.model
    def open_view(self, view_id):
        """The saved question, ready to run, with a plain note when part of
        it no longer exists here. Never a traceback (R7)."""
        self._require()
        View = self.env['pb.explorer.view']
        try:
            view = View.browse(int(view_id or 0)).exists()
            if view:
                view.check_access('read')
        except (AccessError, TypeError, ValueError):
            view = View
        if not view:
            return {'ok': False,
                    'msg': _("This saved view is no longer available. It may "
                             "have been deleted or no longer shared.")}
        try:
            spec = view._pbx_spec_now()
            drift = view._pbx_drift()
        except Exception:                                  # noqa: BLE001
            _logger.exception('pb_explorer: saved view %s did not open', view.id)
            spec, drift = self._clean_spec({}), True
        return {
            'ok': True,
            'spec': spec,
            'view': view._pbx_payload(),
            'note': (_("Part of this saved view no longer exists here, so it "
                       "opened with the closest match. Save it again to keep "
                       "this version.") if drift else ''),
        }
