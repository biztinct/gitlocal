# -*- coding: utf-8 -*-
"""UPDATES P3b — an unfinished update survives closing the browser.

A draft is a `pb.updates.batch` in state `draft`: the file (kept once, as the
named update keeps it), the column choice and the on-screen choices, saved as
the person works. Rails (handover §2, §4):

  * private — a record rule shows a draft to its owner only, and every list
    here asks for the caller's own;
  * it holds NO value that bypasses review: continuing a draft reads the file
    again against today's records, and the saved fixes are only typed values
    the review judges again;
  * it is never a past update and never counted (`get_history` skips it);
  * applying it turns the SAME record into the update (`_new_batch`);
  * nothing deletes a draft by itself — only Discard (the owner, or a records
    manager).

Loaded after `updates_desk` (models/__init__.py).
"""
import json

from odoo import _, api, fields, models

#: The step names the screen saves, in order.
STEPS = ('match', 'review', 'apply')


class PbUpdatesDrafts(models.AbstractModel):
    _inherit = 'pb.updates.desk'

    @api.model
    def _json(self, text, default):
        try:
            value = json.loads(text or '')
        except (TypeError, ValueError):
            return default
        return value if isinstance(value, type(default)) else default

    @api.model
    def save_draft(self, draft_id=0, kind='lasting', month=None, filename='',
                   file_b64='', columns=None, choices=None, step=''):
        """Save (or update) the caller's draft. The file is sent once, with
        the first save; later saves carry only the choices. `choices` is
        merged key by key into what is saved. Quiet: a draft that cannot be
        saved never stops the person working."""
        desk = self._gate()
        if not self._can_write(desk):
            return {'ok': False, 'quiet': True}
        draft = self._own_draft(draft_id)
        step = step if step in STEPS else (draft.draft_step if draft else 'match')
        saved = self._json(draft.draft_choices, {}) if draft else {}
        if isinstance(choices, dict):
            saved.update(choices)
        vals = {
            'draft_choices': json.dumps(saved, default=str),
            'draft_saved_at': fields.Datetime.now(),
            'draft_step': step,
        }
        if isinstance(columns, dict):
            vals['draft_columns'] = json.dumps(columns, default=str)
        if kind == 'oneoff':
            month_day, _why = self._oneoff_month(month) if month else (None, '')
            vals.update(kind='oneoff', period_month=month_day or False)
        else:
            vals['kind'] = 'lasting'
        if draft:
            draft.write(vals)
        else:
            if not file_b64:
                return {'ok': False, 'quiet': True}
            name = (filename or '').strip() or _("Unfinished update")
            vals.update(name=name[:200], state='draft',
                        filename=(filename or '').strip() or False)
            draft = self._new_batch(vals, file_b64, filename)
        return {'ok': True, 'draft_id': draft.id,
                'saved_at': fields.Datetime.to_string(draft.draft_saved_at)}

    @api.model
    def _draft_row(self, draft):
        Oneoff = self.env['pb.updates.oneoff']
        step = draft.draft_step or 'match'
        return {
            'id': draft.id,
            'filename': draft.filename or draft.name or '',
            'kind': draft.kind or 'lasting',
            'month': fields.Date.to_string(draft.period_month) if draft.period_month else '',
            'month_label': Oneoff._month_label(draft.period_month) if draft.period_month else '',
            'step': step,
            'saved_at': fields.Datetime.to_string(draft.draft_saved_at or draft.write_date),
        }

    @api.model
    def list_drafts(self):
        """The caller's own drafts, newest first."""
        self._gate()
        drafts = self.env['pb.updates.batch'].search(
            [('state', '=', 'draft'), ('user_id', '=', self.env.uid),
             ('company_id', 'in', self.env.companies.ids)],
            order='draft_saved_at desc, id desc', limit=100)
        return {'drafts': [self._draft_row(d) for d in drafts]}

    @api.model
    def open_draft(self, draft_id=0):
        """Everything the screen needs to continue: the file, the kind and
        month, the column choice, the choices and the step reached. The file
        is read again from scratch by the screen — nothing here is a verdict."""
        self._gate()
        draft = self._own_draft(draft_id)
        if not draft:
            return {'ok': False, 'msg': _(
                "That draft is not there any more. It may have been applied or "
                "discarded.")}
        if not draft.attachment_id:
            return {'ok': False, 'msg': _(
                "This draft has lost its file. Discard it and start again.")}
        datas = draft.attachment_id.sudo().datas or b''
        return dict(self._draft_row(draft), ok=True,
                    file_b64=datas.decode() if isinstance(datas, bytes) else datas,
                    columns=self._json(draft.draft_columns, {}),
                    choices=self._json(draft.draft_choices, {}))

    @api.model
    def discard_draft(self, draft_id=0):
        """Throw a draft away: its owner, or a records manager. Nothing else
        is touched — a draft changed nothing."""
        self._gate()
        draft = self._own_draft(draft_id)
        if not draft:
            try:
                draft_id = int(draft_id or 0)
            except (TypeError, ValueError):
                draft_id = 0
            other = self.env['pb.updates.batch'].sudo().search(
                [('id', '=', draft_id), ('state', '=', 'draft'),
                 ('company_id', 'in', self.env.companies.ids)], limit=1)
            manager = any(self.env.user.has_group(g) for g in (
                'hr.group_hr_manager',
                'pb_hr_payroll_base.group_payroll_base_manager',
                'base.group_system'))
            draft = other if (other and manager) else draft
        if not draft:
            return {'ok': False, 'msg': _(
                "That draft is not there any more, or it is not yours to "
                "discard.")}
        name = draft.filename or draft.name or ''
        draft = draft.sudo()
        if draft.apply_ids:
            # A draft never has parts; one that has is not a draft to lose.
            return {'ok': False, 'msg': _("This is not a draft any more.")}
        draft.attachment_id.unlink()
        draft.unlink()
        return {'ok': True, 'msg': _("Draft “%s” discarded.") % name}

    @api.model
    def get_home(self):
        answer = super().get_home()
        answer['drafts'] = self.list_drafts()['drafts']
        return answer
