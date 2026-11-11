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
    values_off_scheme = fields.Integer(
        string='Values not in the pay scheme',
        help="Pay-item values skipped because the item is not in that "
             "person's pay scheme.")
    # UPDATES P3b — an unfinished update, saved as it is worked on. A draft
    # is private to the person who made it (record rule), carries NO value
    # that bypasses review (continuing it always reads the file again
    # against today's records) and is never listed in Past updates or
    # counted. Every batch made before this phase is `sent`; a non-draft
    # batch's words are still read off its applies (`_batch_state`).
    state = fields.Selection([('draft', 'Draft'), ('sent', 'Sent')],
                             string='Stage', default='sent', required=True,
                             index=True)
    #: The column choice `_clean_columns` reads, as the screen last had it.
    draft_columns = fields.Text(string='Column choice (draft)')
    #: On-screen fixes and choices: fixes, rows found by hand, rows skipped,
    #: start date, what waits, add-as-new, the step reached.
    draft_choices = fields.Text(string='Choices (draft)')
    draft_saved_at = fields.Datetime(string='Saved at (draft)')
    draft_step = fields.Char(string='Step reached (draft)')


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
    #: UPDATES P2d — a one-off sheet's matchings are kept apart from the
    #: lasting-change ones: the same heading means a different destination.
    kind = fields.Selection([('lasting', 'Lasting changes'),
                             ('oneoff', 'One-off pay items')],
                            string='Kind of sheet', default='lasting')

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
    def remember(self, headings_to_targets, kind='lasting'):
        """Upsert this company's matching for one set of headings.

        `headings_to_targets` is `[(heading, target)]` in file order. The
        latest matching is the truth: the map is replaced, not merged, and the
        use count goes up by one. `kind` (UPDATES P2d): a one-off sheet's
        matching is its own, under its own fingerprint."""
        pairs = [(h, t) for h, t in headings_to_targets if _norm(h) and t]
        if not pairs:
            return self.browse()
        fingerprint = heading_fingerprint([h for h, _t in headings_to_targets])
        if kind == 'oneoff':
            fingerprint = 'oneoff:' + fingerprint
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
                     'use_count': 1,
                     'kind': 'oneoff' if kind == 'oneoff' else 'lasting'})
        return self.create(vals)


class PbRecordsApplyUpdates(models.Model):
    _inherit = 'pb.records.apply'

    updates_batch_id = fields.Many2one(
        'pb.updates.batch', string='Named update', index=True,
        ondelete='set null', readonly=True, copy=False)
