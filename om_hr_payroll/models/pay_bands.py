# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class HrPayslipLine(models.Model):
    """Which money band a payslip line belongs in — ONE answer, read everywhere.

    WHY THIS EXISTS. Every screen that shows Gross / Deductions / Net used to
    work the bands out for itself, from `hr_salary_rule_category.code`. That
    code is whatever the imported workbook's own headings implied, so the
    screens disagreed with each other on the same run: the Rize August 2026 run
    reported ₫2,060,124,305 gross and ₫289,886,044 deductions on the pay run,
    and ₫0 gross with ₫10,747,123,945 deductions on the Payroll Report — the
    scheme has no GROSS category at all, and its insurance bases and tax bases
    sit under DED, where they are working figures, not money withheld.

    The scheme already knows the answer. It derives it from its own net-pay
    formula and stamps it on the line when the payslip is computed
    (`hr.payslip.line.pay_role`, VALUEKIND/NETROLE). This module reads that
    first and falls back to the category only for lines written before the
    stamp existed, so an existing tenant's figures never move under it without
    a recompute.

    KEEP THIS IN STEP WITH `hr.payslip.run._pb_bucket_sql`, which is the same
    rule expressed in SQL because a run aggregates hundreds of thousands of
    lines and cannot afford the ORM. The two are tested against each other.
    """
    _inherit = 'hr.payslip.line'

    #: What net pay does with a line → the band it is counted in.
    #: `info` and `mixed` deliberately map to nothing: a component counted in
    #: days is not an amount, and one that is both added and taken off has no
    #: single band. Both are dropped from every money figure.
    _PB_BAND_BY_ROLE = {
        'earning': 'GROSS',
        'deduction': 'DED',
        'net': 'NET',
        'employer_cost': 'ERCOST',
        'info': False,
        'mixed': False,
    }

    #: The fallback, for lines that carry no pay role. Deliberately the same
    #: set of codes as `hr.payslip.run._PB_CATEGORY_BUCKETS` — a band that one
    #: screen recognises and another does not is the disease this file cures.
    _PB_BAND_BY_CATEGORY = {
        'GROSS': 'GROSS',
        'BASIC': 'BASIC',
        'ALW': 'ALW',
        'DED': 'DED',
        'DEDUCTION': 'DED',
        'COMP': 'DED',
        'NET': 'NET',
    }

    def pb_pay_band(self):
        """'GROSS' | 'BASIC' | 'ALW' | 'DED' | 'NET' | 'ERCOST' | False.

        BASIC and ALW stay apart from GROSS on purpose: a scheme that reports
        its own gross line must not have its parts added on top of it. See
        :meth:`pb_pay_totals`.
        """
        self.ensure_one()
        role = self.pay_role if 'pay_role' in self._fields else False
        if role:
            return self._PB_BAND_BY_ROLE.get(role, False)
        code = (self.category_id.code or '').upper() if self.category_id else ''
        return self._PB_BAND_BY_CATEGORY.get(code, False)

    def pb_counts_in_totals(self):
        """Should a total add this line, or is it already inside another one?

        `SI-HI-UI Total 10.5%` is taken off net pay and so is `Total
        Deduction` — but only because the second CONTAINS the first. A detail
        line still shows on the payslip; it is the TOTALS that skip it. Net is
        exempt: net pay is a total of everything by definition, and skipping it
        would leave nothing to reconcile against.
        """
        self.ensure_one()
        band = self.pb_pay_band()
        if not band:
            return False
        category = (self.category_id.code or '').upper() if self.category_id else ''
        if band == 'NET' or category == 'NET':
            return True
        detail = self.component_detail \
            if 'component_detail' in self._fields else False
        return not detail

    def pb_pay_totals(self):
        """{'gross', 'deductions', 'net', 'employer_cost'} for these lines.

        MONEY TAKEN OFF IS TAKEN OFF, however the scheme signs it. The
        reference demo world writes insurance and tax as NEGATIVE amounts and
        the mid-month advance as a POSITIVE one, all of them deductions;
        summing the raw figures let ₫19.8bn of advance cancel ₫5.9bn of
        insurance and tax, and one abs() at the end could not put it back.
        """
        bands = {}
        for line in self:
            if not line.pb_counts_in_totals():
                continue
            band = line.pb_pay_band()
            amount = line.total or 0.0
            if band in ('DED', 'ERCOST'):
                amount = abs(amount)
            bands[band] = bands.get(band, 0.0) + amount
        return {
            # A scheme's own gross line is the answer where it has one; only a
            # scheme without one is rebuilt from its parts.
            'gross': bands.get('GROSS') or (bands.get('BASIC', 0.0)
                                            + bands.get('ALW', 0.0)),
            'deductions': bands.get('DED', 0.0),
            'net': bands.get('NET', 0.0),
            'employer_cost': bands.get('ERCOST', 0.0),
        }

    def pb_lines_in_band(self, band):
        """The lines a total in `band` is made of — for a breakdown list.

        A breakdown that does not add up to the figure above it is worse than
        no breakdown, so this returns exactly what :meth:`pb_pay_totals` counts.
        `band` is one of 'gross', 'deductions', 'net', 'employer_cost'.
        """
        wanted = {'gross': ('GROSS', 'BASIC', 'ALW'), 'deductions': ('DED',),
                  'net': ('NET',), 'employer_cost': ('ERCOST',)}[band]
        counted = self.filtered(lambda l: l.pb_counts_in_totals())
        lines = counted.filtered(lambda l: l.pb_pay_band() in wanted)
        if band == 'gross' and any(l.pb_pay_band() == 'GROSS' for l in lines):
            # Same rule as the total: the scheme's own gross line wins, and its
            # parts are not listed beside it.
            lines = lines.filtered(lambda l: l.pb_pay_band() == 'GROSS')
        return lines

    #: What to search for, per band: the pay roles, and the rule categories
    #: that stand in for them on a line written before the roles existed.
    #: 'gross' is deliberately absent — the gross rule is "the scheme's own
    #: gross line, or its parts where it has none", which is a choice made
    #: after reading the lines and cannot be put in a domain. Total a
    #: payslip's lines with :meth:`pb_pay_totals` for gross.
    _PB_DOMAIN_BY_BAND = {
        'deductions': (('deduction',), ('DED', 'DEDUCTION', 'COMP')),
        'net': (('net',), ('NET',)),
        'employer_cost': (('employer_cost',), ()),
    }

    @api.model
    def pb_band_domain(self, band):
        """A search domain for the lines a `band` total is made of.

        The same rule as :meth:`pb_pay_band`, for the screens that search for
        lines rather than walk a payslip. Still worth passing the result
        through :meth:`pb_counts_in_totals` afterwards on an old tenant, where
        some lines carry a pay role and others do not.
        """
        roles, categories = self._PB_DOMAIN_BY_BAND[band]
        by_category = [('category_id.code', 'in', list(categories))] \
            if categories else [(0, '=', 1)]
        if 'pay_role' not in self._fields:
            return by_category
        domain = ['|', ('pay_role', 'in', list(roles)),
                  '&', ('pay_role', '=', False)] + by_category
        if 'component_detail' in self._fields and band != 'net':
            domain = [('component_detail', '!=', True)] + domain
        return domain

    def pb_net_line(self):
        """The one line that IS net pay, or an empty recordset.

        A scheme may put more than one component in the NET category — the
        reference demo world has `FULLPAY` and `NET` both there, and picking
        the first in sequence hands out the wrong figure. The pay role names
        the real one.
        """
        if 'pay_role' in self._fields:
            net = self.filtered(lambda l: l.pay_role == 'net')
            if net:
                return net[:1]
            if any(l.pay_role for l in self):
                # The scheme HAS been classified and says none of these is net.
                # Guessing from the category now would override its answer.
                return self.browse()
        by_code = self.filtered(lambda l: (l.code or '').upper() == 'NET')
        if by_code:
            return by_code[:1]
        by_cat = self.filtered(
            lambda l: l.category_id and (l.category_id.code or '').upper() == 'NET')
        return by_cat[:1]


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def pb_pay_totals(self):
        """Gross / Deductions / Net / Employer cost across these payslips."""
        return self.mapped('line_ids').pb_pay_totals()

    def pb_net_amount(self):
        """This payslip's take-home figure, or 0.0 when it has none."""
        self.ensure_one()
        line = self.line_ids.pb_net_line()
        return line.total if line else 0.0
