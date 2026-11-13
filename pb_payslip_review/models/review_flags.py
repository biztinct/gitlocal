# -*- coding: utf-8 -*-
"""What "Need review" flags on a pay run — ONE answer, read by two screens.

LEARN REFRESH step 6. "Need review" is counted in two places: the Run lens's
Review step (pb_payrun_wizard `get_summary`) and Pay Run › Payslips
(`pb.payslip.review.get_review_data`). They used to decide "flagged" each for
themselves (net ≤ 0, from two different ideas of which line is net), and
neither said anything about a big change on last month — the one thing a
payroll officer most wants a screen to catch. Both now call
`hr.payslip.run.pb_review_flags`, so the two counters cannot disagree.

A payslip is flagged when
  * its take-home pay is zero or below, or
  * its take-home pay differs by more than the threshold (Payroll defaults,
    default 30%) from the SAME employee's previous payslip in the SAME pay
    scheme — the previous one before this period, never a cancelled one or a
    refund. A joiner (no previous payslip) is never flagged for change.

Take-home pay is the scheme's own net line — the SQL twin of
`hr.payslip.line.pb_net_line` (om_hr_payroll/models/pay_bands.py): the line
whose pay role is net; on a payslip whose lines carry no pay role at all, the
line coded NET, else the line in the NET category. Keep the two in step
(test_review_flags::test_net_matches_the_orm_helper).

Cost: one query per run, whatever its size.
"""
from odoo import _, api, fields, models
from odoo.tools.misc import format_date

#: ir.config_parameter key for the threshold, in percent.
CHANGE_PARAM = 'pb_payslip_review.net_change_pct'
DEFAULT_CHANGE_PCT = 30


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    @api.model
    def pb_review_change_pct(self):
        """The threshold in percent; 0 switches the change flag off."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            CHANGE_PARAM, str(DEFAULT_CHANGE_PCT))
        try:
            pct = float(raw)
        except (TypeError, ValueError):
            return float(DEFAULT_CHANGE_PCT)
        return pct if pct >= 0 else float(DEFAULT_CHANGE_PCT)

    def pb_review_flags(self, slip_ids=None):
        """{slip_id: {...}} for every payslip of this run (or of `slip_ids`).

        Each value: ``net`` (float or None when the payslip has no net line),
        ``prev_net`` / ``prev_date`` (the previous payslip's, or None),
        ``change_pct`` (signed, or None), ``flag`` (bool), ``kind``
        ('zero' | 'change' | '') and ``reason`` (a plain sentence in the
        reader's language, '' when not flagged).
        """
        self.ensure_one()
        cr = self.env.cr
        # the ORM may hold unwritten line totals — the SQL must see them
        self.env['hr.payslip.line'].flush_model()
        self.env['hr.payslip'].flush_model()
        # read BEFORE the query: get_param runs its own query on this cursor
        threshold = self.pb_review_change_pct()
        params = {'run': self.id}
        only = ''
        if slip_ids is not None:
            if not slip_ids:
                return {}
            only = 'AND s.id IN %(ids)s'
            params['ids'] = tuple(slip_ids)
        role_aware = 'pay_role' in self.env['hr.payslip.line']._fields
        # ONE set-based query per run (LEARN REFRESH step 6): the previous
        # payslip is a DISTINCT ON over a hash join, and each payslip's net
        # line is a DISTINCT ON over the lines of just these payslips. The
        # first version asked per payslip and took 13 s on a 900-person run
        # (hr_payslip has no employee index); this takes about 0.4 s.
        role = "pl.pay_role" if role_aware else "NULL::varchar"
        cr.execute("""
            WITH cur AS (
                SELECT s.id, s.state, s.employee_id, s.formula_config_id,
                       s.date_from
                FROM hr_payslip s
                WHERE s.payslip_run_id = %(run)s """ + only + """
            ), prev AS (
                SELECT DISTINCT ON (c.id) c.id AS sid, p.id AS pid, p.date_to
                FROM cur c
                JOIN hr_payslip p
                  ON p.employee_id = c.employee_id
                 AND p.formula_config_id = c.formula_config_id
                 AND p.id != c.id
                 AND p.state != 'cancel'
                 AND COALESCE(p.credit_note, FALSE) = FALSE
                 AND p.date_to < c.date_from
                ORDER BY c.id, p.date_to DESC, p.id DESC
            ), ids AS (
                SELECT id FROM cur UNION SELECT pid FROM prev
            ), lines AS (
                SELECT pl.slip_id, pl.total, """ + role + """ AS role,
                       UPPER(pl.code) AS ucode, UPPER(c.code) AS ccode,
                       pl.sequence, pl.id,
                       bool_or(""" + role + """ IS NOT NULL)
                           OVER (PARTITION BY pl.slip_id) AS has_role
                FROM hr_payslip_line pl
                LEFT JOIN hr_salary_rule_category c ON c.id = pl.category_id
                WHERE pl.slip_id IN (SELECT id FROM ids)
            ), net AS (
                SELECT DISTINCT ON (slip_id) slip_id, total
                FROM lines
                WHERE role = 'net'
                   OR (NOT has_role AND (ucode = 'NET' OR ccode = 'NET'))
                ORDER BY slip_id,
                         CASE WHEN role = 'net' THEN 0
                              WHEN ucode = 'NET' THEN 1 ELSE 2 END,
                         sequence, id
            )
            SELECT c.id, c.state, n1.total, pr.pid, pr.date_to, n2.total
            FROM cur c
            LEFT JOIN prev pr ON pr.sid = c.id
            LEFT JOIN net n1 ON n1.slip_id = c.id
            LEFT JOIN net n2 ON n2.slip_id = pr.pid
        """, params)
        rows = cr.fetchall()
        out = {}
        for sid, state, net, prev_id, prev_date, prev_net in rows:
            row = {'net': net, 'prev_net': prev_net if prev_id else None,
                   'prev_date': prev_date, 'change_pct': None,
                   'flag': False, 'kind': '', 'reason': ''}
            if state == 'cancel':
                # a cancelled payslip is paid nothing and needs nobody
                pass
            elif net is not None and net <= 0:
                row.update(flag=True, kind='zero',
                           reason=_('Take-home pay is zero or below'))
            elif (net is not None and prev_id and prev_net
                  and prev_net > 0):
                change = (net - prev_net) / prev_net * 100.0
                row['change_pct'] = change
                if threshold and abs(change) > threshold:
                    month = format_date(self.env, prev_date,
                                        date_format='MMMM y')
                    pct = round(abs(change))
                    row.update(flag=True, kind='change', reason=(
                        _('Net pay up %(pct)s%% on %(month)s',
                          pct=pct, month=month) if change > 0 else
                        _('Net pay down %(pct)s%% on %(month)s',
                          pct=pct, month=month)))
            out[sid] = row
        return out


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pb_review_change_pct = fields.Integer(
        string='Flag a change in take-home pay above (%)',
        config_parameter=CHANGE_PARAM, default=DEFAULT_CHANGE_PCT,
        help="A payslip whose take-home pay moved by more than this, against "
             "the same person's previous payslip in the same pay scheme, is "
             "counted under Need review. 0 switches it off.")
