# -*- coding: utf-8 -*-
"""UPDATES P1 — the two things Updates stores, and the one link it adds.

  * `pb.updates.batch` — one NAMED update: what the person called it, who sent
    it, when, the original file (an attachment readable only through the
    batch), and the Records Desk apply it produced. Its state is never stored:
    it is read off that apply every time, so "Waiting for approval", "Applied"
    and "Undone" can never disagree with the desk's own history.
  * `pb.updates.layout` — the column matching a company used for a file with a
    given set of headings, so month two is one click. Keyed by a fingerprint
    of the normalised headings; a heading also answers on its own for a file
    whose other columns differ.
  * `pb.records.apply.updates_batch_id` — the back-link, so an apply can say
    which named update it belongs to.

Nothing here writes an employee or a contract. That is the desk's job alone.
"""
import hashlib
import json

from odoo import api, fields, models

from odoo.addons.pb_records.models.pb_records_io import _norm


def heading_fingerprint(headings):
    """`sha1` of the normalised headings, in file order, joined by `\\x1f`.

    The SAME `_norm` the desk imports with, so a heading means the same thing
    in both modules ("Gaji Pokok " and "gaji pokok" are one heading)."""
    joined = '\x1f'.join(_norm(h) for h in headings if _norm(h))
    return hashlib.sha1(joined.encode('utf-8')).hexdigest()


class PbUpdatesBatch(models.Model):
    _name = 'pb.updates.batch'
    _description = 'Named update'
    _order = 'id desc'

    name = fields.Char(string='Name', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    user_id = fields.Many2one(
        'res.users', string='Sent by', default=lambda self: self.env.user)
    date = fields.Datetime(string='Sent on', default=fields.Datetime.now)
    filename = fields.Char(string='File name')
    attachment_id = fields.Many2one(
        'ir.attachment', string='Original file', ondelete='set null')
    apply_ids = fields.One2many(
        'pb.records.apply', 'updates_batch_id', string='Changes applied')
    rows_total = fields.Integer(string='Rows in the file')
    rows_unmatched = fields.Integer(string='Rows that matched nobody')
    values_refused = fields.Integer(string='Values left out')


class PbUpdatesLayout(models.Model):
    _name = 'pb.updates.layout'
    _description = 'Remembered column matching'
    _order = 'last_used desc, id desc'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    fingerprint = fields.Char(string='Headings fingerprint', required=True,
                              index=True)
    #: `{normalised heading: target}` — a card id, `identity:code|name|email`,
    #: or `ignore`.
    map_json = fields.Text(string='Column matching')
    use_count = fields.Integer(string='Times used', default=0)
    last_used = fields.Datetime(string='Last used', default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string='Last used by',
                              default=lambda self: self.env.user)

    _company_fingerprint_uniq = models.Constraint(
        'UNIQUE(company_id, fingerprint)',
        'This company already remembers a matching for these headings.')

    def get_map(self):
        self.ensure_one()
        try:
            data = json.loads(self.map_json or '{}')
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    @api.model
    def remember(self, headings_to_targets):
        """Upsert this company's matching for one set of headings.

        `headings_to_targets` is `[(heading, target)]` in file order. The
        latest matching is the truth: the map is replaced, not merged, and the
        use count goes up by one."""
        pairs = [(h, t) for h, t in headings_to_targets if _norm(h) and t]
        if not pairs:
            return self.browse()
        fingerprint = heading_fingerprint([h for h, _t in headings_to_targets])
        company = self.env.company
        mapping = {_norm(h): t for h, t in pairs}
        layout = self.search([('company_id', '=', company.id),
                              ('fingerprint', '=', fingerprint)], limit=1)
        vals = {'map_json': json.dumps(mapping, sort_keys=True),
                'last_used': fields.Datetime.now(),
                'user_id': self.env.user.id}
        if layout:
            vals['use_count'] = (layout.use_count or 0) + 1
            layout.write(vals)
            return layout
        vals.update({'company_id': company.id, 'fingerprint': fingerprint,
                     'use_count': 1})
        return self.create(vals)


class PbRecordsApplyUpdates(models.Model):
    _inherit = 'pb.records.apply'

    updates_batch_id = fields.Many2one(
        'pb.updates.batch', string='Named update', index=True,
        ondelete='set null', readonly=True, copy=False)
