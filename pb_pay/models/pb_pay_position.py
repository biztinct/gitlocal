# -*- coding: utf-8 -*-
"""`pb.pay.position` — where every open contract sits in its band.

DERIVED, LIKE THE FACT TABLES
-----------------------------
One row per open contract. Nothing is ever typed here and nothing outside this
file writes it; dropping the table and rebuilding it is always safe. That is
what makes it cheap enough to keep current: the whole company is rebuilt in ONE
SQL statement rather than 4,500 ORM computes, which is the difference between
two seconds and four minutes.

WHY IT IS A TABLE AND NOT A COMPUTE ON THE CONTRACT
---------------------------------------------------
Three reasons, all of them things the old `hr.contract.compa_ratio` got wrong.
A stored compute on the contract recomputes when the WAGE changes and not when
the BAND moves, so it drifts and nothing says so. It cannot be grouped by band
without a join the contract does not have. And it puts a payroll-sensitive
figure on a table every payroll screen writes, so a bug here could reach a pay
run — this table is read by screens and by nothing else.

WHERE THE JOB COMES FROM (WFPLAN WF7)
-------------------------------------
`hr.contract.job_id` is filled on the AB Mauri tenant and NULL on all 4,510 of
the demo company's contracts, where the truth lives on the employee's current
version. One `COALESCE(c.job_id, v.job_id)` answers both databases, exactly as
the Decision Room's baseline does.
"""

import logging
import time

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

STATES = [
    ('below', 'Paid below the band'),
    ('in', 'Inside the band'),
    ('above', 'Paid above the band'),
    ('no_band', 'No band for this job yet'),
]


class PbPayPosition(models.Model):
    _name = 'pb.pay.position'
    _description = 'Where a contract sits in its band'
    _order = 'company_id, band_id, position_pct'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', index=True,
                                  ondelete='cascade', string='Employee')
    contract_id = fields.Many2one('hr.contract', index=True,
                                  ondelete='cascade', string='Contract')
    # PERSON, not employment — an Integer for the same reason `pb.fact.emp`
    # carries one: the person lives in a module this one does not depend on,
    # and a foreign key would drag the whole of it into every install.
    person_id = fields.Integer(string='Person', index=True)
    company_id = fields.Many2one('res.company', index=True, string='Company')
    job_id = fields.Many2one('hr.job', index=True, string='Job position')
    band_id = fields.Many2one('pb.pay.band', index=True, ondelete='cascade',
                              string='Band')

    wage = fields.Float(string='Monthly pay', digits=(16, 2))
    currency_id = fields.Many2one('res.currency', string='Currency')
    position_pct = fields.Float(
        string='Position in band', digits=(16, 2),
        help='0 is the bottom of the band and 100 the top. Below 0 or above '
             '100 means the pay is outside it.')
    compa = fields.Float(
        string='Against the middle', digits=(16, 4),
        help='The pay divided by the middle of the band. 1.0 is exactly the '
             'middle.')
    state = fields.Selection(STATES, index=True, string='Standing')
    as_of = fields.Date(string='Worked out on', index=True)

    # ================================================================ the pass
    @api.model
    def recompute_all(self, company_ids=None):
        """Rebuild the table in one statement. Returns the number of rows.

        `company_ids` narrows the rebuild to some companies; everything else
        is left alone, so a band edited for Vietnam does not churn Singapore.
        """
        started = time.time()
        companies = [int(c) for c in (company_ids or [])]
        today = fields.Date.context_today(self)

        rules = self._band_rules(today, companies)
        cr = self.env.cr
        # The ORM is still holding writes to the contracts and bands this pass
        # is about to read (GR13): flush first, invalidate WITHOUT flushing
        # afterwards, or the ORM's pending values land on top of the raw work.
        self.env.flush_all()

        where_company = ''
        params = []
        if companies:
            where_company = ' AND c.company_id IN %s'
            params.append(tuple(companies))

        cr.execute('DELETE FROM pb_pay_position WHERE TRUE'
                   + (' AND company_id IN %s' if companies else ''),
                   [tuple(companies)] if companies else [])

        # A person may hold two employments (GROUP P5). Where that module is
        # installed the row carries the PERSON, so a head count over this table
        # counts human beings; where it is not, the employee is the person.
        person_col = 'e.pb_person_id' \
            if 'pb_person_id' in self.env['hr.employee']._fields \
            else 'NULL::int'

        # Built by CONCATENATION and never by `%`-formatting: the fragments
        # themselves carry `%s` placeholders, and a second round of formatting
        # over them would eat the ones psycopg is meant to fill.
        if rules:
            row = ('(%s::int, %s::int, %s::int, %s::numeric, %s::numeric, '
                   '%s::numeric)')
            values = ', '.join([row] * len(rules))
            rule_params = []
            for job_id, company_id, band_id, low, mid, high in rules:
                rule_params += [job_id, company_id, band_id, low, mid, high]
            band_cte = ('bands (job_id, company_id, band_id, low, mid, high) '
                        'AS ( VALUES ' + values + ' )')
        else:
            band_cte = (
                'bands (job_id, company_id, band_id, low, mid, high) AS ('
                ' SELECT NULL::int, NULL::int, NULL::int, NULL::numeric,'
                ' NULL::numeric, NULL::numeric WHERE FALSE )')
            rule_params = []

        sql = 'WITH ' + band_cte + ',' + """
            live AS (
                SELECT DISTINCT ON (c.employee_id)
                       c.id           AS contract_id,
                       c.employee_id  AS employee_id,
                       c.company_id   AS company_id,
                       COALESCE(c.wage, 0)::numeric AS wage,
                       COALESCE(c.job_id, v.job_id) AS job_id,
                       """ + person_col + """ AS person_id
                  FROM hr_contract c
                  JOIN hr_employee e ON e.id = c.employee_id AND e.active
             LEFT JOIN hr_version v ON v.id = e.current_version_id
                 WHERE c.state = 'open' AND c.active
            """ + where_company + """
              ORDER BY c.employee_id, c.date_start DESC NULLS LAST, c.id DESC
            )
            INSERT INTO pb_pay_position
                (employee_id, contract_id, person_id, company_id, job_id,
                 band_id, wage, currency_id, position_pct, compa, state, as_of)
            SELECT l.employee_id, l.contract_id,
                   COALESCE(l.person_id, l.employee_id), l.company_id,
                   l.job_id, b.band_id, l.wage, co.currency_id,
                   CASE WHEN b.band_id IS NULL OR b.high <= b.low THEN 0
                        ELSE ROUND(((l.wage - b.low)
                                    / (b.high - b.low)) * 100, 2) END,
                   CASE WHEN b.band_id IS NULL OR b.mid <= 0 THEN 0
                        ELSE ROUND(l.wage / b.mid, 4) END,
                   CASE WHEN b.band_id IS NULL THEN 'no_band'
                        WHEN l.wage < b.low  THEN 'below'
                        WHEN l.wage > b.high THEN 'above'
                        ELSE 'in' END,
                   %s
              FROM live l
         LEFT JOIN LATERAL (
                   SELECT bb.band_id, bb.low, bb.mid, bb.high
                     FROM bands bb
                    WHERE bb.job_id = l.job_id
                      AND (bb.company_id IS NULL
                           OR bb.company_id = l.company_id)
                 ORDER BY (bb.company_id IS NULL)
                    LIMIT 1
               ) b ON TRUE
         LEFT JOIN res_company co ON co.id = l.company_id
        """

        cr.execute(sql, rule_params + params + [today])
        self.env.invalidate_all(flush=False)

        cr.execute('SELECT COUNT(*) FROM pb_pay_position'
                   + (' WHERE company_id IN %s' if companies else ''),
                   [tuple(companies)] if companies else [])
        made = cr.fetchone()[0]
        _logger.info('pb_pay: %s positions rebuilt in %.0f ms',
                     made, (time.time() - started) * 1000)
        return made

    @api.model
    def _band_rules(self, day, companies):
        """(job, company or None, band, low, mid, high) for every linked job.

        A job may be linked to one band with no company restriction and to
        another restricted to one company; the SQL prefers the specific row by
        DISTINCT-ing on job + company, so the more specific rule is emitted
        first and the general one only where nothing more specific exists.
        """
        Band = self.env['pb.pay.band'].sudo()
        bands = Band.search([
            ('date_from', '<=', day),
            '|', ('date_to', '=', False), ('date_to', '>=', day),
        ])
        rules, seen = [], set()
        # Specific first: a band that names companies beats one that does not,
        # and inside each group the band that started most recently wins.
        ordered = sorted(
            bands, key=lambda b: (0 if b.company_ids else 1,
                                  -(b.date_from.toordinal() if b.date_from
                                    else 0)))
        for band in ordered:
            targets = band.company_ids.ids or [None]
            for link in band.job_ids:
                for company_id in targets:
                    key = (link.job_id.id, company_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    rules.append((link.job_id.id, company_id, band.id,
                                  band.min_amount, band.mid_amount,
                                  band.max_amount))
        return rules

    # -------------------------------------------------------------- triggers
    @api.model
    def _cron_recompute(self):
        """Nightly. Bands do not move often; wages do."""
        self.recompute_all()

    @api.model
    def touch_companies(self, company_ids):
        """Rebuild after a band, a job link or a wage changed."""
        try:
            return self.sudo().recompute_all(company_ids or None)
        except Exception:       # noqa: BLE001 — never take a save down for a
            _logger.exception(  # figure a screen recomputes on demand anyway
                'pb_pay: the position pass failed after a change')
            return 0

    def label(self):
        """"62% of the way through the band" — the sentence, once."""
        self.ensure_one()
        if self.state == 'no_band':
            return _("No band for this job yet")
        if self.state == 'below':
            return _("Below the band")
        if self.state == 'above':
            return _("Above the band")
        return _("%(pct)s%% of the way through the band",
                 pct=int(round(self.position_pct)))
