# -*- coding: utf-8 -*-
"""`pb.pay.band` — a salary range, and the jobs that sit inside it.

WHAT A BAND IS
--------------
The lowest, the middle and the highest MONTHLY amount this company means to pay
somebody at one level of one job family, in one country's money. Three numbers
and a from-date. Everything else on the Pay Bands screen — the picture, the
health cards, the suggested offer for a new hire, the position printed on a
contract — is read out of those three numbers and the wages people are actually
on.

WHY A FROM-DATE
---------------
Bands move, usually once a year, and a band that is edited in place rewrites
history: last March's "below band" becomes this March's "in band" and nobody
can say what was true at the time. So a band carries `date_from`/`date_to`, two
bands for the same family, level and country may never overlap in time, and
moving a band next April means writing the NEXT one rather than editing this
one. (GR23's lesson from the division links, applied on purpose: a range that
starts today leaves everything before today unexplained, so the screen says
which day a band has been in force since.)

WHAT A BAND NEVER DOES
----------------------
It never changes anybody's pay. No pay run reads this table. A band is a
statement of intent that the product then measures reality against; moving one
moves the MEASUREMENT and nothing else, which is exactly why dragging its edge
is safe enough to be the hero of the screen.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

#: The countries the payroll engine knows, in the engine's own order and codes
#: (`hr.formula.config.country_code`). One list, so a band and a scheme can
#: never disagree about what "VN" means.
COUNTRIES = [
    ('VN', 'Vietnam'),
    ('ID', 'Indonesia'),
    ('IN', 'India'),
    ('SG', 'Singapore'),
    ('MY', 'Malaysia'),
    ('TH', 'Thailand'),
    ('KH', 'Cambodia'),
    ('PH', 'Philippines'),
]

#: What a country is normally paid in. A DEFAULT and never a rule: a Vietnamese
#: entity that genuinely writes its bands in dollars edits the currency and the
#: product believes it.
COUNTRY_CURRENCY = {
    'VN': 'VND', 'ID': 'IDR', 'IN': 'INR', 'SG': 'SGD',
    'MY': 'MYR', 'TH': 'THB', 'KH': 'KHR', 'PH': 'PHP',
}

MAX_LEVEL = 12


class PbPayBand(models.Model):
    _name = 'pb.pay.band'
    _description = 'Pay band'
    _inherit = ['mail.thread']
    _order = 'country_code, family_id, level, date_from desc'

    name = fields.Char(string='Band', compute='_compute_name', store=True)
    family_id = fields.Many2one(
        'pb.pay.family', string='Job family', required=True,
        ondelete='restrict', index=True, tracking=True)
    level = fields.Integer(
        string='Level', default=1, required=True, index=True, tracking=True,
        help='1 is the most junior. Levels are this company\'s own ladder.')
    country_code = fields.Selection(
        COUNTRIES, string='Country', required=True, index=True, tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id)

    min_amount = fields.Monetary(string='Lowest', tracking=True)
    mid_amount = fields.Monetary(string='Middle', tracking=True)
    max_amount = fields.Monetary(string='Highest', tracking=True)

    date_from = fields.Date(
        string='In force from', required=True, index=True, tracking=True,
        default=lambda self: fields.Date.context_today(self))
    date_to = fields.Date(string='In force until', tracking=True)

    company_ids = fields.Many2many(
        'res.company', string='Only these companies',
        help='Leave empty and every company in this country uses the band.')
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')

    job_ids = fields.One2many('pb.pay.band.job', 'band_id', string='Jobs')
    job_count = fields.Integer(string='Jobs', compute='_compute_counts')
    people_count = fields.Integer(string='People', compute='_compute_counts')

    # ------------------------------------------------------------- computes
    @api.depends('family_id.name', 'level', 'country_code')
    def _compute_name(self):
        countries = dict(COUNTRIES)
        for band in self:
            family = band.family_id.name or _('Unnamed')
            country = countries.get(band.country_code, band.country_code or '')
            band.name = _(
                '%(family)s · level %(level)s · %(country)s',
                family=family, level=band.level or 1, country=country)

    def _compute_counts(self):
        jobs, people = {}, {}
        if self.ids:
            rows = self.env['pb.pay.band.job'].sudo()._read_group(
                [('band_id', 'in', self.ids)], ['band_id'], ['__count'])
            jobs = {band.id: count for band, count in rows if band}
            rows = self.env['pb.pay.position'].sudo()._read_group(
                [('band_id', 'in', self.ids)], ['band_id'], ['__count'])
            people = {band.id: count for band, count in rows if band}
        for band in self:
            band.job_count = jobs.get(band.id, 0)
            band.people_count = people.get(band.id, 0)

    @api.onchange('country_code')
    def _onchange_country_code(self):
        for band in self:
            code = COUNTRY_CURRENCY.get(band.country_code)
            if not code:
                continue
            currency = self.env['res.currency'].with_context(
                active_test=False).search([('name', '=', code)], limit=1)
            if currency:
                band.currency_id = currency

    # --------------------------------------------------------- the promises
    @api.constrains('min_amount', 'mid_amount', 'max_amount')
    def _check_order(self):
        for band in self:
            if band.min_amount > band.mid_amount \
                    or band.mid_amount > band.max_amount:
                raise ValidationError(_(
                    "A band reads lowest, middle, highest. On %(band)s the "
                    "three numbers are not in that order.", band=band.name
                    or _('this band')))
            if band.max_amount <= 0:
                raise ValidationError(_(
                    "A band needs a highest amount above zero, or nobody can "
                    "be measured against it."))

    @api.constrains('level')
    def _check_level(self):
        for band in self:
            if not 1 <= band.level <= MAX_LEVEL:
                raise ValidationError(_(
                    "A level runs from 1 to %(top)s.", top=MAX_LEVEL))

    @api.constrains('date_from', 'date_to', 'family_id', 'level',
                    'country_code', 'active')
    def _check_no_overlap(self):
        for band in self:
            if not band.active:
                continue
            clash = self.search([
                ('id', '!=', band.id),
                ('family_id', '=', band.family_id.id),
                ('level', '=', band.level),
                ('country_code', '=', band.country_code),
                ('date_from', '<=', band.date_to or '9999-12-31'),
                '|', ('date_to', '=', False),
                ('date_to', '>=', band.date_from),
            ], limit=1)
            if clash:
                raise ValidationError(_(
                    "%(band)s already has a range in force from %(since)s. "
                    "Two ranges for the same family, level and country cannot "
                    "cover the same days — end the old one the day before the "
                    "new one starts.",
                    band=band.name or _('This band'),
                    since=fields.Date.to_string(clash.date_from)))

    # ------------------------------------------------------------- the reads
    @api.model
    def bands_on(self, on_date=None, company=None):
        """Every band in force on a day, newest first.

        `company` narrows to the bands that company may use: the ones with no
        company restriction at all, plus the ones that name it.
        """
        day = fields.Date.to_date(on_date) if on_date else \
            fields.Date.context_today(self)
        bands = self.sudo().search([
            ('date_from', '<=', day),
            '|', ('date_to', '=', False), ('date_to', '>=', day),
        ])
        if company:
            bands = bands.filtered(
                lambda b: not b.company_ids or company.id in b.company_ids.ids)
        return bands

    def money(self, amount):
        """One amount in this band's own money, formatted for a sentence."""
        self.ensure_one()
        currency = self.currency_id or self.env.company.currency_id
        return self.env['pb.pay.bands']._money(amount, currency)

    # ---------------------------------------------------------- the migration
    @api.model
    def migrate_legacy(self):
        """Carry the old Pay Grades over. Idempotent, and never writes back.

        A grade held a name, a code, a level, a country and a min/mid/max in
        one company's currency, and contracts pointed at it directly. A band
        holds the same three numbers but belongs to a FAMILY and a LEVEL, and
        jobs — not people — point at it. So:

          * every grade becomes one band under a family called "Migrated",
            at the grade's own level, in the grade's own country and money,
            in force from today and noted as migrated;
          * a job whose people all sat on the SAME grade gets a link to that
            grade's band. A job whose people sat on two different grades is a
            CONFLICT: nothing is guessed, the job is left unlinked and the
            band's note names it, because a job silently placed in the wrong
            band would misreport every person in it.

        The legacy module is not touched, read or written — `wfp.pay.grade`
        rows and `hr.contract.grade_id` values are left exactly as they are.
        """
        report = {'grades': 0, 'bands': 0, 'jobs_linked': 0, 'conflicts': [],
                  'skipped': 0}
        if 'wfp.pay.grade' not in self.env:
            return report
        Grade = self.env['wfp.pay.grade'].sudo()
        grades = Grade.with_context(active_test=False).search([])
        report['grades'] = len(grades)
        if not grades:
            return report

        family = self.env['pb.pay.family'].sudo().search(
            [('name', '=', 'Migrated')], limit=1)
        if not family:
            family = self.env['pb.pay.family'].sudo().create({
                'name': 'Migrated', 'code': 'MIG', 'sequence': 90,
                'note': 'Carried over from the old Pay Grades screen.',
            })

        today = fields.Date.context_today(self)
        by_grade = {}
        for grade in grades:
            existing = self.sudo().with_context(active_test=False).search([
                ('family_id', '=', family.id),
                ('note', 'like', 'wfp.pay.grade:%s;' % grade.id),
            ], limit=1)
            if existing:
                by_grade[grade.id] = existing
                report['skipped'] += 1
                continue
            level = min(max(int(grade.grade_level or 1), 1), MAX_LEVEL)
            country = grade.country_code or (
                grade.company_id.country_id.code if grade.company_id else '')
            if country not in dict(COUNTRIES):
                country = 'VN'
            currency = grade.currency_id or grade.company_id.currency_id \
                or self.env.company.currency_id
            # A family/level/country that already carries a band cannot take a
            # second one on the same days (the overlap rule above), so a second
            # grade at the same level walks DOWN the free levels rather than
            # failing the whole migration.
            for candidate in list(range(level, MAX_LEVEL + 1)) \
                    + list(range(level - 1, 0, -1)):
                clash = self.sudo().search([
                    ('family_id', '=', family.id),
                    ('level', '=', candidate),
                    ('country_code', '=', country),
                ], limit=1)
                if not clash:
                    level = candidate
                    break
            else:
                report['conflicts'].append(
                    'no free level for grade %s' % (grade.code or grade.name))
                continue
            band = self.sudo().create({
                'family_id': family.id,
                'level': level,
                'country_code': country,
                'currency_id': currency.id,
                'min_amount': grade.range_min,
                'mid_amount': grade.range_mid,
                'max_amount': grade.range_max,
                'date_from': today,
                'company_ids': [(6, 0, grade.company_id.ids)]
                if grade.company_id else False,
                'note': 'wfp.pay.grade:%s; %s' % (
                    grade.id,
                    'migrated from Pay Grades (%s)' % (grade.name or '')),
            })
            by_grade[grade.id] = band
            report['bands'] += 1

        report.update(self._migrate_job_links(by_grade))
        return report

    @api.model
    def _migrate_job_links(self, by_grade):
        """Point each job at the band its people were already graded into."""
        out = {'jobs_linked': 0, 'conflicts': []}
        if not by_grade:
            return out
        self.env.cr.execute("""
            SELECT COALESCE(c.job_id, v.job_id) AS job_id,
                   c.grade_id, COUNT(*)
              FROM hr_contract c
              JOIN hr_employee e ON e.id = c.employee_id
         LEFT JOIN hr_version v ON v.id = e.current_version_id
             WHERE c.grade_id IS NOT NULL
               AND COALESCE(c.job_id, v.job_id) IS NOT NULL
          GROUP BY 1, 2
        """)
        by_job = {}
        for job_id, grade_id, count in self.env.cr.fetchall():
            by_job.setdefault(job_id, []).append((grade_id, count))
        Link = self.env['pb.pay.band.job'].sudo()
        for job_id, pairs in by_job.items():
            if len({g for g, _c in pairs}) > 1:
                out['conflicts'].append(job_id)
                continue
            band = by_grade.get(pairs[0][0])
            if not band:
                continue
            if Link.search([('job_id', '=', job_id),
                            ('band_id', '=', band.id)], limit=1):
                continue
            try:
                Link.create({'band_id': band.id, 'job_id': job_id})
                out['jobs_linked'] += 1
            except Exception as error:      # noqa: BLE001
                _logger.info('pb_pay: job %s could not be linked: %s',
                             job_id, error)
                out['conflicts'].append(job_id)
        if out['conflicts']:
            names = self.env['hr.job'].sudo().browse(
                out['conflicts']).mapped('display_name')
            note = 'Jobs left unlinked because their people sat on more than ' \
                   'one old grade: %s' % ', '.join(sorted(names))
            for band in set(by_grade.values()):
                band.sudo().note = (band.note or '') + '\n' + note
                break
        return out


class PbPayBandJob(models.Model):
    """Which jobs a band covers.

    The link is JOB to BAND and never person to band: a band is a statement
    about a kind of work, and putting one person in a different band from
    everybody doing their job is the thing bands exist to make visible.
    """
    _name = 'pb.pay.band.job'
    _description = 'Job in a pay band'
    _order = 'band_id, job_id'
    _rec_name = 'job_id'

    band_id = fields.Many2one(
        'pb.pay.band', string='Band', required=True, ondelete='cascade',
        index=True)
    job_id = fields.Many2one(
        'hr.job', string='Job position', required=True, ondelete='cascade',
        index=True)
    company_id = fields.Many2one(
        'res.company', related='job_id.company_id', store=True, index=True)

    _job_band_uniq = models.Constraint(
        'unique(band_id, job_id)',
        'That job is already in this band.')

    @api.constrains('band_id', 'job_id')
    def _check_one_band_at_a_time(self):
        """A job belongs to ONE band on any given day.

        The dates live on the BAND, so the check reads the other links of the
        same job and refuses one whose band's days overlap this one's.
        """
        for link in self:
            band = link.band_id
            others = self.search([
                ('job_id', '=', link.job_id.id), ('id', '!=', link.id)])
            for other in others:
                theirs = other.band_id
                if not theirs or not theirs.active:
                    continue
                starts_after_they_end = theirs.date_to \
                    and band.date_from > theirs.date_to
                ends_before_they_start = band.date_to \
                    and band.date_to < theirs.date_from
                if starts_after_they_end or ends_before_they_start:
                    continue
                raise ValidationError(_(
                    "%(job)s is already in %(band)s over those days. A job "
                    "sits in one band at a time.",
                    job=link.job_id.display_name, band=theirs.name))
