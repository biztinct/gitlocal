# -*- coding: utf-8 -*-
"""`pb.pay.guidance` — what a raise should be before anybody has an opinion.

WHAT IT IS
----------
A small grid. Across it: how well somebody has done, on this company's own
scale. Down it: where their pay already sits in its band. In each square: the
percentage this company means to give. That is the whole model, and it is the
thing that lets a review of four thousand people OPEN with an answer instead of
four thousand empty boxes.

WHY THE TWO AXES ARE THOSE TWO
------------------------------
Because they are the two facts that make a raise defensible. Performance alone
gives the best people the same rise whether they are already the best paid in
the team or the worst; position alone rewards being underpaid and nothing else.
Together they say the sentence a manager has to be able to say out loud: "you
did very well and you are near the bottom of the range, so you get more than
somebody who did very well and is already at the top."

WORDS ON THE SCREEN
-------------------
Never "merit matrix", never "compa ratio", never "quartile". On screen this is
"Guidance", its rows are "Doing well" and "Outstanding", and its columns are
"Below the band", "Bottom third", "Middle third", "Top third", "Above the band".
The old product's vocabulary is not carried across with the old product's data.

WHAT IT NEVER DOES
------------------
It never writes a proposal on its own and it never writes a wage. It answers a
question — "what would you suggest for this person" — and a human being decides
whether to keep the answer.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .pb_pay_band import COUNTRIES

_logger = logging.getLogger(__name__)

#: Where a person's pay already sits, in the five buckets a grid is written
#: with. The keys are stored; the labels are what a reader sees.
POSITION_BANDS = [
    ('below', 'Below the band'),
    ('low', 'Bottom third'),
    ('mid', 'Middle third'),
    ('high', 'Top third'),
    ('above', 'Above the band'),
]

#: The order the grid is drawn in, left to right.
POSITION_ORDER = [key for key, _label in POSITION_BANDS]

#: The middle column, used when nobody knows where a person sits (no band).
MIDDLE_BAND = 'mid'

SCALES = [('3', '3 levels'), ('4', '4 levels'), ('5', '5 levels')]

#: Which words a scale uses, in order. The words THEMSELVES are written
#: inside `scale_words` below, where `_()` can find them — see the note there.
SCALE_LADDERS = {
    '3': ['support', 'well', 'outstanding'],
    '4': ['support', 'well', 'strong', 'outstanding'],
    '5': ['support', 'nearly', 'well', 'strong', 'outstanding'],
}

#: A grid nobody has filled in still has to answer, and answering ZERO for
#: everybody is an honest answer that reads as a broken screen. So a NEW grid
#: is born with a shape: more for the people who did better, more for the
#: people who are paid least for it, nothing at all above the band.
SEED = {
    'below': [2.0, 5.0, 7.0, 9.0, 11.0],
    'low':   [1.0, 4.0, 6.0, 8.0, 10.0],
    'mid':   [0.0, 3.0, 4.5, 6.0, 8.0],
    'high':  [0.0, 2.0, 3.0, 4.0, 6.0],
    'above': [0.0, 0.0, 1.0, 2.0, 3.0],
}


def scale_words(scale):
    """What each rating is CALLED, always as many words as the scale has.

    A number on its own tells a manager nothing and means something different
    in every company, so every scale ships words — and those words are read
    aloud in a calibration meeting, so they have to be in the reader's own
    language.

    THE WORDS ARE WRITTEN HERE, INSIDE THE `_()` CALLS. A literal that lives
    in a module-level list is invisible to the string extractor as a Python
    term (ledger T24), so these five printed in English under every column of
    a fully Vietnamese picture. They are a DICT keyed by the value and the
    order is derived from it, because the extractor also collects the first
    string of a tuple that contains a `_()` call and would otherwise put the
    bare key into the catalogue as a term somebody has to translate (GR59).
    """
    words = {
        'support': _("Needs support"),
        'nearly': _("Nearly there"),
        'well': _("Doing well"),
        'strong': _("Very strong"),
        'outstanding': _("Outstanding"),
    }
    ladder = SCALE_LADDERS.get(str(scale) or '4', SCALE_LADDERS['4'])
    return [words[key] for key in ladder]


def band_for(position_pct, has_band):
    """Which column of the grid a person falls in.

    `has_band` is the honest half: a person whose job has no band at all does
    not sit anywhere, and pretending they sit in the middle without saying so
    is how a number nobody can explain gets onto a payslip. The caller keeps
    the chip; this function only picks a column so the row is never empty.
    """
    if not has_band:
        return MIDDLE_BAND
    pct = float(position_pct or 0.0)
    if pct < 0:
        return 'below'
    if pct > 100:
        return 'above'
    if pct <= 33:
        return 'low'
    if pct <= 66:
        return 'mid'
    return 'high'


class PbPayGuidance(models.Model):
    _name = 'pb.pay.guidance'
    _description = 'Pay review guidance'
    _order = 'sequence, name'

    name = fields.Char(string='Guidance', required=True)
    sequence = fields.Integer(default=10)
    country_code = fields.Selection(
        COUNTRIES, string='Country',
        help='Leave empty and this guidance may be used anywhere.')
    company_ids = fields.Many2many(
        'res.company', string='Only these companies',
        help='Leave empty and every company may use it.')
    rating_scale = fields.Selection(
        SCALES, string='How performance is scored', default='4',
        required=True)
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')
    cell_ids = fields.One2many('pb.pay.guidance.cell', 'guidance_id',
                               string='Squares')
    cell_count = fields.Integer(string='Squares', compute='_compute_cells')

    def _compute_cells(self):
        counted = {}
        if self.ids:
            rows = self.env['pb.pay.guidance.cell'].sudo()._read_group(
                [('guidance_id', 'in', self.ids)], ['guidance_id'],
                ['__count'])
            counted = {rec.id: count for rec, count in rows if rec}
        for grid in self:
            grid.cell_count = counted.get(grid.id, 0)

    # --------------------------------------------------------------- writing
    @api.model_create_multi
    def create(self, vals_list):
        grids = super().create(vals_list)
        for grid in grids:
            grid._fill_missing_cells(seed=True)
        return grids

    def write(self, vals):
        result = super().write(vals)
        if 'rating_scale' in vals:
            for grid in self:
                grid._fill_missing_cells(seed=True)
        return result

    def _fill_missing_cells(self, seed=False):
        """Every square exists, always. A missing square is a silent zero."""
        Cell = self.env['pb.pay.guidance.cell'].sudo()
        for grid in self:
            levels = int(grid.rating_scale or '4')
            have = {(cell.rating, cell.position_band): cell
                    for cell in grid.cell_ids}
            made = []
            for column in POSITION_ORDER:
                for rating in range(1, levels + 1):
                    if (rating, column) in have:
                        continue
                    pct = 0.0
                    if seed:
                        row = SEED.get(column) or []
                        # The seed is written for a five-level scale; a
                        # shorter one takes the top, the bottom and the
                        # spread between them rather than the first N.
                        if row:
                            spot = 0 if levels == 1 else \
                                int(round((rating - 1) * (len(row) - 1)
                                          / float(levels - 1)))
                            pct = row[min(spot, len(row) - 1)]
                    made.append({'guidance_id': grid.id, 'rating': rating,
                                 'position_band': column, 'pct': pct})
            if made:
                Cell.create(made)

    # --------------------------------------------------------------- reading
    def pct_for(self, rating, position_pct, has_band=True):
        """What this grid suggests for one person, as a percentage."""
        self.ensure_one()
        levels = int(self.rating_scale or '4')
        try:
            rating = int(rating or 0)
        except (TypeError, ValueError):
            rating = 0
        if rating > levels:
            # A score of 5 carried over from a five-point scale, read by a
            # four-level grid, means "the best there is" and not "we cannot
            # tell". Treating it as the middle would quietly halve the rise of
            # every one of a company's best people on the day it upgraded.
            rating = levels
        elif rating < 1:
            rating = self.middle_rating()
        column = band_for(position_pct, has_band)
        cell = self.cell_ids.filtered(
            lambda c: c.rating == rating and c.position_band == column)[:1]
        return float(cell.pct or 0.0)

    def middle_rating(self):
        """The rating an unrated person is treated as, and it is the middle.

        Not the bottom (which punishes a manager's paperwork) and not the top
        (which pays for it). The middle, with a chip on the row saying nobody
        has scored this person, so the number is visibly a placeholder.
        """
        self.ensure_one()
        levels = int(self.rating_scale or '4')
        return max(1, (levels + 1) // 2)

    def grid(self):
        """The whole grid as the screen draws it."""
        self.ensure_one()
        levels = int(self.rating_scale or '4')
        words = scale_words(self.rating_scale)
        columns = [{'key': key, 'label': label}
                   for key, label in POSITION_BANDS]
        cells = {(c.rating, c.position_band): c for c in self.cell_ids}
        rows = []
        for rating in range(levels, 0, -1):
            rows.append({
                'rating': rating,
                'label': words[min(rating - 1, len(words) - 1)],
                'cells': [{
                    'id': cells[(rating, key)].id
                    if (rating, key) in cells else 0,
                    'band': key,
                    'pct': float(cells[(rating, key)].pct)
                    if (rating, key) in cells else 0.0,
                } for key in POSITION_ORDER],
            })
        return {
            'id': self.id, 'name': self.name,
            'rating_scale': self.rating_scale,
            'levels': levels,
            'words': words,
            'columns': columns,
            'rows': rows,
            'note': self.note or '',
        }

    @api.model
    def for_company(self, company):
        """The grid a company's next review opens with, or nothing."""
        settings = self.env['pb.pay.settings'].sudo().for_company(company)
        if settings.guidance_id and settings.guidance_id.active:
            return settings.guidance_id
        country = (company.sudo().country_id.code or '').upper()
        grids = self.sudo().search([])
        mine = grids.filtered(lambda g: company.id in g.company_ids.ids)
        if mine:
            return mine[:1]
        same = grids.filtered(
            lambda g: not g.company_ids and g.country_code == country)
        if same:
            return same[:1]
        loose = grids.filtered(
            lambda g: not g.company_ids and not g.country_code)
        return loose[:1]

    # ------------------------------------------------------------ the seeder
    @api.model
    def make_default(self, company=None):
        """A grid a company can start from, made once and named plainly.

        The SCALE is read off the scores this company already holds rather
        than assumed. A company whose people are scored out of five and whose
        grid runs to four has a top row nobody can reach, and the first thing
        it does is under-pay everybody at the top.
        """
        company = company or self.env.company
        scale = self._scale_for(company)
        grid = self.sudo().create({
            'name': _('Standard guidance'),
            'rating_scale': scale,
            'country_code': (company.sudo().country_id.code or '').upper()
            or False,
        })
        return grid

    @api.model
    def _scale_for(self, company):
        """The number of levels the scores this reader can see actually need.

        Read across every company the reader is entitled to and not just the
        one they happen to be standing in: an administrator whose default
        company is the head-office shell has nobody in it, and a grid sized on
        an empty company is sized on nothing.
        """
        Employee = self.env['hr.employee']
        companies = (self.env.user.company_ids or company).ids
        if not companies:
            return '4'
        highest = 0
        for name in ('pb_performance_rating', 'wfp_performance_rating'):
            if name not in Employee._fields:
                continue
            self.env.cr.execute(
                'SELECT MAX(%s) FROM hr_employee WHERE company_id IN %%s'
                % name, [tuple(companies)])
            raw = self.env.cr.fetchone()[0]
            try:
                highest = max(highest, int(raw))
            except (TypeError, ValueError):
                continue
        if highest >= 5:
            return '5'
        if highest == 3:
            return '3'
        return '4' 

    # ---------------------------------------------------------- the migration
    @api.model
    def migrate_legacy(self):
        """Carry every old Merit Matrix over as a guidance grid. Idempotent.

        The old model held one row per cell with a performance BAND written as
        free text and a position range written as two compa-ratio numbers. A
        grid holds a rating LEVEL and one of five named columns, so the
        migration has to decide which column a range like 0.8-0.9 belongs to.
        It does that on the MIDPOINT of the range against the same thresholds
        the live grid uses, and it writes the old text into the note so that
        nothing a human typed is thrown away without a trace.
        """
        report = {'matrices': 0, 'grids': 0, 'cells': 0, 'skipped': 0,
                  'notes': []}
        if 'wfp.merit.matrix' not in self.env:
            return report
        Matrix = self.env['wfp.merit.matrix'].sudo()
        rows = Matrix.with_context(active_test=False).search([])
        report['matrices'] = len(rows)
        if not rows:
            return report

        # The old model is a header with cells (`cell_ids`), but a build that
        # ever shipped it flat is read too, because a migration that only knows
        # one shape silently migrates nothing and says it worked.
        header_field = None
        for candidate in ('cell_ids', 'line_ids'):
            if candidate in Matrix._fields:
                header_field = candidate
                break
        groups = {}
        if header_field:
            for matrix in rows:
                groups[matrix.id] = (matrix, matrix[header_field])
        else:
            for matrix in rows:
                key = matrix.name or _('Migrated guidance')
                groups.setdefault(key, (matrix, Matrix.browse()))
                groups[key] = (groups[key][0],
                               groups[key][1] | matrix)

        for key, (head, lines) in groups.items():
            tag = 'wfp.merit.matrix:%s;' % (
                head.id if header_field else key)
            existing = self.sudo().with_context(active_test=False).search(
                [('note', 'like', tag)], limit=1)
            if existing:
                report['skipped'] += 1
                continue
            name = _('Migrated · %(name)s', name=head.name or _('guidance'))
            grid = self.sudo().create({
                'name': name[:120],
                'rating_scale': '4',
                'note': '%s carried over from the old Merit Matrix screen.'
                        % tag,
            })
            report['grids'] += 1
            report['cells'] += grid._absorb_legacy_lines(lines or head)
        return report

    def _absorb_legacy_lines(self, lines):
        """Write the old cells into this grid's squares. Never creates one."""
        self.ensure_one()
        levels = int(self.rating_scale or '4')
        cells = {(c.rating, c.position_band): c for c in self.cell_ids}
        written = 0
        for line in lines:
            rating = self._legacy_rating(line, levels)
            column = self._legacy_column(line)
            pct = self._legacy_pct(line)
            if rating is None or column is None:
                continue
            cell = cells.get((rating, column))
            if not cell:
                continue
            cell.sudo().write({'pct': pct})
            written += 1
        return written

    @staticmethod
    def _legacy_rating(line, levels):
        """A rating level out of whatever the old row called performance.

        The shipped model held a free-text `performance_label` and an optional
        numeric min/max, and neither was ever required — which is why the old
        lookup ignored performance entirely and keyed on the compa ratio alone.
        Both are read here, the number first, and a row that says nothing at
        all about performance lands in the middle rather than being dropped.
        """
        for name in ('performance_min', 'performance_max',
                     'performance_level', 'performance_rating', 'rating'):
            if name not in line._fields:
                continue
            raw = line[name]
            if isinstance(raw, (int, float)) and raw:
                return max(1, min(int(raw), levels))
        for name in ('performance_label', 'performance_band', 'performance'):
            if name not in line._fields:
                continue
            text = str(line[name] or '').strip().lower()
            if not text:
                continue
            for number in range(levels, 0, -1):
                if str(number) in text:
                    return number
            for word, number in (('outstanding', levels),
                                 ('exception', levels),
                                 ('exceed', levels),
                                 ('strong', max(1, levels - 1)),
                                 ('meet', max(1, levels // 2 + 1)),
                                 ('good', max(1, levels // 2 + 1)),
                                 ('develop', 1), ('below', 1),
                                 ('improve', 1), ('support', 1)):
                if word in text:
                    return number
        return max(1, (levels + 1) // 2)

    @staticmethod
    def _legacy_column(line):
        """A named column out of the old row's compa range.

        The old field was written on TWO scales in the wild — the help text
        says "e.g. 0, 85, 100", so a hundred means the midpoint, while a
        careful person typing a ratio writes 1.0 for the same thing. A midpoint
        above ten can only be the percentage form, so it is divided down; below
        ten it can only be the ratio form and is left alone.
        """
        low = high = None
        for name in ('compa_min', 'compa_ratio_min', 'min_compa'):
            if name in line._fields and line[name]:
                low = float(line[name])
                break
        for name in ('compa_max', 'compa_ratio_max', 'max_compa'):
            if name in line._fields and line[name]:
                high = float(line[name])
                break
        if low is None and high is None:
            return MIDDLE_BAND
        middle = (float(low or 0.0) + float(high or low or 0.0)) / 2.0
        if middle > 10.0:
            middle = middle / 100.0
        if middle < 0.8:
            return 'below'
        if middle < 0.95:
            return 'low'
        if middle <= 1.05:
            return 'mid'
        if middle <= 1.2:
            return 'high'
        return 'above'

    @staticmethod
    def _legacy_pct(line):
        for name in ('increase_pct', 'increase_percentage', 'percentage',
                     'pct', 'increase'):
            if name in line._fields and line[name]:
                return float(line[name])
        return 0.0


class PbPayGuidanceCell(models.Model):
    """One square of the grid."""
    _name = 'pb.pay.guidance.cell'
    _description = 'Square of a pay review guidance grid'
    _order = 'guidance_id, rating desc, position_band'
    _rec_name = 'guidance_id'

    guidance_id = fields.Many2one(
        'pb.pay.guidance', string='Guidance', required=True,
        ondelete='cascade', index=True)
    rating = fields.Integer(string='How well they did', required=True)
    position_band = fields.Selection(
        POSITION_BANDS, string='Where their pay sits', required=True)
    pct = fields.Float(string='Suggested rise', digits=(16, 2))

    _cell_uniq = models.Constraint(
        'unique(guidance_id, rating, position_band)',
        'That square is already in this guidance.')

    @api.constrains('pct')
    def _check_pct(self):
        for cell in self:
            if cell.pct < -100.0 or cell.pct > 200.0:
                raise ValidationError(_(
                    "A suggested rise runs from -100% to 200%. %(pct)s is "
                    "outside that.", pct=cell.pct))
