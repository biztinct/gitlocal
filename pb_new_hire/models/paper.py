# -*- coding: utf-8 -*-
"""NEWHIRE P3a — the papers a new person needs, per country of work
(handover §2.2).

One small table, not a flag on the document category: one category can be
needed before the first pay in one country and optional in another
(FACTS_ONBOARD §C6). Rows with no company are the shipped defaults
(`data/papers.xml`, noupdate); a row of a company for the same category and
country overrides the default, and an INACTIVE company row means "not
needed here". The editor in step 5 (`papers_edit_*` on `pb.new.hire`) only
ever writes company rows; "Back to the usual list" deletes them.

The table lives in `pb_new_hire` (D10): it exists only where the studio is
installed.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

NEEDS = [
    ('first_pay', 'Needed before first pay'),
    ('joining', 'Asked at joining'),
    ('optional', 'Optional'),
]
#: The order a need ranks in when two rows meet (the stronger wins).
NEED_RANK = {'first_pay': 0, 'joining': 1, 'optional': 2}

#: Who may change the list (the screen twin of this table).
EDITOR_GROUPS = ('hr.group_hr_manager',)


def stronger(a, b):
    """The stronger of two needs."""
    return a if NEED_RANK.get(a, 9) <= NEED_RANK.get(b, 9) else b


class PbNewHirePaper(models.Model):
    _name = 'pb.new.hire.paper'
    _description = 'Papers needed by a new person, per country of work'
    _order = 'country_code, sequence, id'

    category_id = fields.Many2one('pb.employee.document.category', string='Paper',
                                  required=True, ondelete='cascade', index=True)
    country_code = fields.Selection('_country_selection', string='Country of work',
                                    required=True, index=True)
    need = fields.Selection(NEEDS, string='Needed', required=True, default='optional')
    label = fields.Char(string='What this country calls it', translate=True,
                        help='Empty: the name of the paper is used.')
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', string='Company', index=True,
                                 help='Empty: the usual list every company starts from.')
    active = fields.Boolean(default=True)

    _one_row = models.UniqueIndex(
        '(category_id, country_code, COALESCE(company_id, 0))',
        'A paper is listed once per country (and once more for a company that changes it).')

    @api.model
    def _country_selection(self):
        return self.env['pb.new.hire']._countries()

    # ------------------------------------------------------------ reading
    @api.model
    def _effective(self, country_code, company):
        """`{category: row}` — the company's row beats the shipped default;
        an inactive company row means "not needed here" (kept in the map so
        the editor can show it)."""
        rows = self.sudo().with_context(active_test=False).search([
            ('country_code', '=', country_code),
            ('company_id', 'in', [False, company.id] if company else [False])])
        out = {}
        for row in rows.sorted(lambda r: (bool(r.company_id), r.sequence, r.id)):
            if not row.company_id and not row.active:
                continue                        # a switched-off default is not a default
            if not row.category_id.active:
                continue
            out[row.category_id] = row          # company rows sort last: they win
        return out

    @api.model
    def for_country(self, country_code, company=None):
        """The papers a new person in this country is asked for, in order:
        `pb.new.hire.paper` rows (company row beats default; "not needed
        here" left out)."""
        company = company or self.env.company
        rows = [r for r in self._effective(country_code, company).values() if r.active]
        rows.sort(key=lambda r: (r.sequence, r.category_id.sequence, r.category_id.id))
        return self.browse([r.id for r in rows])

    def display_label(self):
        """What this country calls the paper: the row's own word, else (a
        company row) the usual row's word, else the paper's name."""
        self.ensure_one()
        if self.label:
            return self.label
        if self.company_id:
            usual = self.sudo().search([('category_id', '=', self.category_id.id),
                                        ('country_code', '=', self.country_code),
                                        ('company_id', '=', False)], limit=1)
            if usual.label:
                return usual.label
        return self.category_id.name or ''

    # ------------------------------------------------------------ the editor
    @api.model
    def _can_edit(self):
        user = self.env.user
        return user._is_superuser() or user.has_group('base.group_system') \
            or any(user.has_group(g) for g in EDITOR_GROUPS)

    @api.model
    def _require_editor(self):
        if not self._can_edit():
            raise AccessError(_("Changing which papers are asked for is for HR managers."))
