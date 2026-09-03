# -*- coding: utf-8 -*-
"""FLEET P5 — measuring a customer, invoicing them, and pausing them.

THE SHAPE, AND IT IS THE SAME SHAPE AS EVERY PHASE BEFORE IT: the judgements
are next door in `billing_rules.py`, pure and tested. What is left here is the
three things that can only be done on a live box — read another database, make
a PDF, send an email — plus the one thing only a person may do, which is change
a customer's standing.

RAIL R1, AND IT IS SHARPER HERE THAN ANYWHERE ELSE IN THE PROGRAMME. Two crons
run in this file:

  * `_cron_meter` READS every customer, once a night, and writes the reading
    down on OUR database. It has never opened a customer's registry for a write
    and never will.
  * `_cron_billing` moves OUR invoices along, sends OUR emails, and raises OUR
    alerts. The one thing it can do to a customer is pause them — and only if
    the owner has deliberately switched `pb_tenants.auto_suspend` on, which is
    OFF by default and stays off until somebody types the words. Suspending a
    payroll customer at 08:30 on a Monday because a bank transfer was slow is
    not a thing software should do on its own.

NOBODY IS EVER INVOICED BY A CRON. `billing_raise` is a button. The preview
comes first, it lists every invoice and every line, and nothing is created
until the owner has read it.
"""
import base64
import json
import logging
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .billing_rules import (
    DEFAULT_DUE_DAYS, DEFAULT_REMINDER_DAYS, DEFAULT_RETENTION_DAYS,
    DEFAULT_SUSPEND_AFTER_DAYS, DEFAULT_TRIAL_DAYS, PRICING, PRICING_LABEL,
    SERVING_STATES, T_ACCESS, T_ACCESS_TEXT, T_INVOICES, T_PLAN_NAME,
    T_RECOVERY, T_SEAT_LIMIT, T_TRIAL_ENDS, TRIAL_GRACE_DAYS, access_payload,
    due_date_for,
    invoice_number, invoice_totals, money, month_closed, month_end,
    month_start, next_state, period_label, prev_month, price_for, qty_text,
    seat_verdict, state_transition, trial_phase, trial_sentence,
)

_logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r'^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$')

#: The settings this phase owns, defaults in CODE rather than in a data record
#: so an upgrade never freezes whatever a test run left behind (the pattern
#: RAILS_DEFAULTS and ALERT_DEFAULTS already set).
#:
#: `auto_suspend` IS THE OWNER'S RULING AND ITS DEFAULT IS OFF. It is written
#: here, once, and the screen that offers it says in red what it does.
BILLING_DEFAULTS = {
    'pb_tenants.auto_suspend': '0',
    'pb_tenants.invoice_prefix': 'PB',
    'pb_tenants.invoice_due_days': str(DEFAULT_DUE_DAYS),
    'pb_tenants.invoice_reminder_days': ','.join(str(d) for d in DEFAULT_REMINDER_DAYS),
    'pb_tenants.suspend_after_days': str(DEFAULT_SUSPEND_AFTER_DAYS),
    'pb_tenants.billing_from_name': 'Payobook',
    'pb_tenants.billing_from_email': '',
    'pb_tenants.billing_company': 'Payobook',
    'pb_tenants.billing_address': '',
    'pb_tenants.billing_vat': '',
    'pb_tenants.bank_details': '',
    'pb_tenants.invoice_footer': '',
}

#: Anything that reads as "off". Same list the rails guard already uses.
_OFF = ('', '0', 'off', 'false', 'no', 'none')

#: The payslip states that count as PRODUCED. A draft payslip is a piece of
#: arithmetic somebody is still doing and a rejected one never happened; both
#: would be a customer paying for work they did not get. The remaining four
#: states (`verify`, `level1`, `level2`, `done`) are all a payslip that exists
#: and has left the drafting stage.
PAYSLIP_PRODUCED_EXCLUDE = ('draft', 'cancel')

#: The PDF is rendered once, at issue, and stored. This is the report that
#: makes it.
INVOICE_REPORT = 'pb_tenants.report_tenant_invoice'


class PbTenantsBilling(models.AbstractModel):
    """The plans, meter, invoices and standings half of Mission Control."""
    _inherit = 'pb.tenants'

    # ================================================================ settings
    def _billing_param(self, key, default=''):
        """A setting whose EMPTY value is meaningful, read off the row (F24)."""
        row = self.env['ir.config_parameter'].sudo().search(
            [('key', '=', key)], limit=1)
        if not row:
            return default
        return row.value if row.value is not None else default

    def _billing_settings(self):
        """Every number and sentence the billing screens work from."""
        out = {}
        for key, fallback in BILLING_DEFAULTS.items():
            out[key.split('.', 1)[1]] = self._billing_param(key, fallback)
        return out

    def _auto_suspend_on(self):
        raw = (self._billing_param('pb_tenants.auto_suspend', '0') or '').strip().lower()
        return raw not in _OFF

    def _due_days(self):
        try:
            return max(0, int(self._billing_param(
                'pb_tenants.invoice_due_days', str(DEFAULT_DUE_DAYS)) or DEFAULT_DUE_DAYS))
        except (TypeError, ValueError):
            return DEFAULT_DUE_DAYS

    def _reminder_days(self):
        raw = self._billing_param('pb_tenants.invoice_reminder_days', '')
        days = []
        for part in re.split(r'[,;\s]+', raw or ''):
            try:
                days.append(int(part))
            except (TypeError, ValueError):
                continue
        return tuple(sorted(d for d in days if d > 0)) or DEFAULT_REMINDER_DAYS

    def _suspend_after(self):
        try:
            return max(0, int(self._billing_param(
                'pb_tenants.suspend_after_days',
                str(DEFAULT_SUSPEND_AFTER_DAYS)) or DEFAULT_SUSPEND_AFTER_DAYS))
        except (TypeError, ValueError):
            return DEFAULT_SUSPEND_AFTER_DAYS

    def _serving(self):
        """Every customer who still has a database. Paused ones included."""
        return self.env['pb.tenant'].sudo().search(
            [('state', 'in', SERVING_STATES)])

    # ================================================================== the meter
    #
    # READ-ONLY, ALWAYS (rail R1). Two counts through a plain cursor on the
    # customer's database: no registry is opened, no ORM is loaded and nothing
    # is written anywhere but our own tables.

    def _measure_db(self, dbname, period):
        """`(employees, payslips)` for one database and one month.

        A database that has no payroll tables at all — a template, a customer
        halfway through provisioning — answers nought rather than raising: the
        meter runs over the whole fleet every night and one odd database must
        not stop the other eleven being measured.
        """
        first, last = month_start(period), month_end(period)
        employees, payslips = 0, 0
        try:
            with self._pg_cursor(dbname) as cr:
                cr.execute("SELECT to_regclass('public.hr_employee')")
                if (cr.fetchone() or [None])[0]:
                    cr.execute("SELECT count(*) FROM hr_employee WHERE active")
                    employees = int((cr.fetchone() or [0])[0] or 0)
                cr.execute("SELECT to_regclass('public.hr_payslip')")
                if (cr.fetchone() or [None])[0]:
                    cr.execute(
                        "SELECT count(*) FROM hr_payslip "
                        "WHERE date_from >= %s AND date_from <= %s "
                        "AND state NOT IN %s",
                        (first, last, PAYSLIP_PRODUCED_EXCLUDE))
                    payslips = int((cr.fetchone() or [0])[0] or 0)
        except Exception:                                    # noqa: BLE001
            _logger.warning("pb_tenants: could not measure %s", dbname,
                            exc_info=True)
            return None
        return employees, payslips

    def _write_usage(self, tenant, period, employees, payslips, today,
                     note=''):
        """One reading, written onto our own record.

        The DAILY shape is kept in `sample` and the month-end number is what
        bills. "We had forty people all month and you charged us for
        fifty-five" is a question only the daily shape can answer.
        """
        Usage = self.env['pb.tenant.usage'].sudo()
        row = Usage.search([('tenant_id', '=', tenant.id),
                            ('period', '=', period)], limit=1)
        try:
            sample = json.loads(row.sample) if row and row.sample else {}
            if not isinstance(sample, dict):
                sample = {}
        except (ValueError, TypeError):
            sample = {}
        sample[today.isoformat()] = employees
        vals = {'employees': employees, 'payslips': payslips,
                'measured_at': fields.Datetime.now(),
                'sample': json.dumps(sample)}
        if note:
            vals['note'] = note
        if row:
            row.write(vals)
            return row
        return Usage.create(dict(vals, tenant_id=tenant.id, period=period))

    @api.model
    def _cron_meter(self):
        """Every night: how many people, how many payslips, per customer.

        Two months are touched, and the second one is the important one. The
        CURRENT month is re-read every night, so the row is final at the last
        reading before midnight on the last day. The PREVIOUS month is filled
        in only if it is missing — a platform whose meter started in the middle
        of September can still invoice August, and says so in the note.
        """
        today = fields.Date.context_today(self)
        this_month = month_start(today)
        last_month = prev_month(this_month)
        Usage = self.env['pb.tenant.usage'].sudo()
        done, failed = 0, []
        for tenant in self._serving():
            reading = self._measure_db(tenant.slug, this_month)
            if reading is None:
                failed.append(tenant.name)
                continue
            self._write_usage(tenant, this_month, reading[0], reading[1], today)
            if not Usage.search_count([('tenant_id', '=', tenant.id),
                                       ('period', '=', last_month)]):
                back = self._measure_db(tenant.slug, last_month)
                if back is not None:
                    self._write_usage(
                        tenant, last_month, back[0], back[1], today,
                        note=_("Measured after the month had ended — the "
                               "employee count is today's."))
            done += 1
            self.env.cr.commit()
        _logger.info("pb_tenants: meter read %d customer(s), %d could not be "
                     "reached", done, len(failed))
        return {'measured': done, 'failed': failed}

    @api.model
    def meter_run(self):
        """"Take a reading now" — the same job, started by a person."""
        self._require_admin()
        res = self._cron_meter()
        return dict(res, data=self.billing_data())

    # ============================================================ the invoices
    def _invoice_currency(self, plan):
        return plan.currency_id or self.env.company.currency_id

    def _next_invoice_number(self, period):
        """The next number in this month, never reused.

        Read off the invoices that exist rather than off a sequence record: a
        sequence that is rolled back with a failed raise leaves a gap, and a
        gap in an invoice book is a question from an auditor.
        """
        prefix = (self._billing_param('pb_tenants.invoice_prefix', 'PB')
                  or 'PB').strip() or 'PB'
        Invoice = self.env['pb.tenant.invoice'].sudo()
        stem = invoice_number(prefix, period, 0)[:-4]
        rows = Invoice.search([('number', 'like', stem + '%')])
        highest = 0
        for inv in rows:
            tail = (inv.number or '')[len(stem):]
            if tail.isdigit():
                highest = max(highest, int(tail))
        return invoice_number(prefix, period, highest + 1)

    def _preview_row(self, tenant, period, today):
        """One customer's invoice, worked out but not written down."""
        Usage = self.env['pb.tenant.usage'].sudo()
        Invoice = self.env['pb.tenant.invoice'].sudo()
        row = {
            'tenant_id': tenant.id, 'tenant': tenant.name,
            'slug': tenant.slug, 'state': tenant.state,
            'plan': tenant.plan_id.name or '',
            'plan_id': tenant.plan_id.id or False,
            'employees': 0, 'payslips': 0, 'lines': [],
            'subtotal': 0.0, 'vat_amount': 0.0, 'total': 0.0,
            'total_h': '', 'currency': '', 'skip': '', 'problem': '',
            'existing': '',
        }
        existing = Invoice.search([('tenant_id', '=', tenant.id),
                                   ('period', '=', period),
                                   ('state', '!=', 'void')], limit=1)
        if existing:
            row['existing'] = existing.number
            row['skip'] = _("Already invoiced as %s.") % existing.number
            return row
        if not tenant.plan_id:
            row['skip'] = _("No plan yet — pick one on their Plan tab.")
            return row
        if tenant.state == 'trial':
            row['skip'] = _("On trial until %s — nothing to charge yet.") % (
                tenant.trial_ends.isoformat() if tenant.trial_ends else '—')
            return row
        usage = Usage.search([('tenant_id', '=', tenant.id),
                              ('period', '=', period)], limit=1)
        if not usage:
            row['skip'] = _(
                "No reading for %s yet. Press \"Take a reading now\" first.")\
                % period_label(period)
            return row
        plan = tenant.plan_id.as_dict()
        cur = self._invoice_currency(tenant.plan_id)
        row.update({'employees': usage.employees, 'payslips': usage.payslips,
                    'currency': cur.name or ''})
        priced = price_for(plan, usage.employees, usage.payslips)
        if priced['problem']:
            row['problem'] = priced['problem']
            row['skip'] = priced['problem']
            return row
        if priced['nothing_to_bill']:
            row['skip'] = _("Nothing to bill — no employees and no payslips "
                            "in %s.") % period_label(period)
            return row
        totals = invoice_totals(priced['lines'], plan['vat_pct'],
                                cur.rounding or 0.01)
        fmt = lambda v: money(v, cur.symbol or '', cur.rounding or 0.01,   # noqa: E731
                              cur.position or 'after')
        row.update({
            'lines': [dict(l, amount_h=fmt(l['amount']),
                           unit_h=fmt(l['unit_price']),
                           qty_h=qty_text(l['qty']))
                      for l in priced['lines']],
            'subtotal': totals['subtotal'], 'subtotal_h': fmt(totals['subtotal']),
            'vat_pct': totals['vat_pct'], 'vat_amount': totals['vat_amount'],
            'vat_h': fmt(totals['vat_amount']),
            'total': totals['total'], 'total_h': fmt(totals['total']),
        })
        return row

    def _period_from(self, period):
        """Whatever the browser sent, as the first of a month."""
        if not period:
            return prev_month(month_start(fields.Date.context_today(self)))
        if isinstance(period, str):
            try:
                parsed = fields.Date.to_date(period)
            except (ValueError, TypeError):
                raise UserError(_('"%s" is not a month.') % period)
            if not parsed:
                raise UserError(_('"%s" is not a month.') % period)
            return month_start(parsed)
        return month_start(period)

    @api.model
    def billing_preview(self, period=None):
        """Every invoice this month would raise, before any of them exists.

        THE HERO OF THE PHASE. Nothing is written; every customer is listed
        with their reading, their lines and their total, and every customer who
        would be skipped says why in a sentence.
        """
        self._require_admin()
        period = self._period_from(period)
        today = fields.Date.context_today(self)
        rows = [self._preview_row(t, period, today) for t in self._serving()]
        billable = [r for r in rows if not r['skip']]
        by_currency = {}
        for r in billable:
            by_currency.setdefault(r['currency'], 0.0)
            by_currency[r['currency']] += r['total']
        return {
            'period': period.isoformat(),
            'period_label': period_label(period),
            'closed': month_closed(period, today),
            'rows': rows,
            'billable': len(billable),
            'skipped': len(rows) - len(billable),
            'totals': [{'currency': c, 'amount': a} for c, a in
                       sorted(by_currency.items())],
        }

    @api.model
    def billing_raise(self, period=None, early=False):
        """Create the invoices the preview just showed. A person presses this."""
        self._require_admin()
        period = self._period_from(period)
        today = fields.Date.context_today(self)
        if not month_closed(period, today) and not early:
            raise UserError(_(
                "%s is not over yet, so the counts would be incomplete. Raise "
                "it early on purpose if that is what you want — the button "
                "says so.") % period_label(period))
        made, skipped = [], []
        for tenant in self._serving():
            row = self._preview_row(tenant, period, today)
            if row['skip']:
                skipped.append({'tenant': tenant.name, 'why': row['skip']})
                continue
            invoice = self._create_invoice(tenant, period, row, today)
            made.append({'tenant': tenant.name, 'number': invoice.number,
                         'total_h': row['total_h'],
                         'pdf': bool(invoice.pdf)})
            self.env.cr.commit()
        return {'created': made, 'skipped': skipped,
                'period_label': period_label(period),
                'data': self.billing_data(period)}

    def _create_invoice(self, tenant, period, row, today):
        plan = tenant.plan_id
        cur = self._invoice_currency(plan)
        invoice = self.env['pb.tenant.invoice'].sudo().create({
            'tenant_id': tenant.id,
            'number': self._next_invoice_number(period),
            'period': period,
            'plan_id': plan.id,
            'plan_name': plan.name,
            'plan_pricing': plan.pricing,
            'currency_id': cur.id,
            'subtotal': row['subtotal'], 'vat_pct': row.get('vat_pct') or 0.0,
            'vat_amount': row['vat_amount'], 'total': row['total'],
            'employees': row['employees'], 'payslips': row['payslips'],
            'state': 'draft',
            'issued_at': today,
            'due_date': due_date_for(today, self._due_days()),
            'line_ids': [(0, 0, {
                'sequence': (i + 1) * 10, 'label': l['label'],
                'detail': l.get('detail') or '', 'qty': l['qty'],
                'unit_price': l['unit_price'], 'amount': l['amount'],
            }) for i, l in enumerate(row['lines'])],
        })
        self._attach_pdf(invoice)
        self._log_line(tenant, 'billing',
                       _("Invoice %(n)s raised for %(p)s — %(t)s.",
                         n=invoice.number, p=period_label(period),
                         t=row['total_h']))
        return invoice

    def _attach_pdf(self, invoice):
        """Render the invoice once and keep the bytes.

        A PDF re-rendered on demand is a document that changes after it was
        sent — the plan gets repriced, the company profile gets corrected, and
        the copy the customer downloads no longer matches the copy in their
        inbox. So it is made here, at issue, and stored.
        """
        try:
            pdf, _fmt = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                INVOICE_REPORT, res_ids=[invoice.id])
        except Exception:                                    # noqa: BLE001
            _logger.exception("pb_tenants: could not render invoice %s",
                              invoice.number)
            return False
        invoice.sudo().write({
            'pdf': base64.b64encode(pdf),
            'pdf_name': '%s.pdf' % invoice.number,
        })
        return True

    @api.model
    def invoice_pdf(self, invoice_id):
        """The stored PDF, for the download button. Renders one if it is
        missing rather than leaving the owner with a dead button."""
        self._require_admin()
        invoice = self._invoice(invoice_id)
        if not invoice.pdf:
            self._attach_pdf(invoice)
        if not invoice.pdf:
            raise UserError(_(
                "The PDF could not be made. Check that the PDF printer is "
                "installed on the server (wkhtmltopdf)."))
        return {'name': invoice.pdf_name or ('%s.pdf' % invoice.number),
                'data': invoice.pdf.decode() if isinstance(invoice.pdf, bytes)
                        else invoice.pdf}

    def _invoice(self, invoice_id):
        invoice = self.env['pb.tenant.invoice'].sudo().browse(
            int(invoice_id)).exists()
        if not invoice:
            raise UserError(_("There is no such invoice."))
        return invoice

    # ================================================================== sending
    def _billing_from(self):
        picked = (self._billing_param('pb_tenants.billing_from_email', '')
                  or '').strip()
        if picked and EMAIL_RE.match(picked):
            return picked
        return self._alert_from()

    def _send_customer_mail(self, tenant, subject, body_html, attachments=None,
                            to=None):
        """One email to one customer, sent now, with the outcome known.

        Same seam as the platform alerts (ledger F5: `email_from` is ALWAYS
        explicit) but a different audience — so a failure here does not raise
        `alert_channel_down`, which is about the owner's own channel. It is
        reported to the person who pressed the button instead.
        """
        address = (to or tenant.billing_to() or '').strip()
        if not EMAIL_RE.match(address or ''):
            return {'ok': False, 'to': address, 'reason': _(
                "%s has no billing address to send to. Add one on their Plan "
                "tab.") % tenant.name}
        sender = self._billing_from()
        name = (self._billing_param('pb_tenants.billing_from_name', 'Payobook')
                or 'Payobook').strip()
        mail = self.env['mail.mail'].sudo().create({
            'subject': subject,
            'body_html': body_html,
            'email_from': '%s <%s>' % (name, sender) if name else sender,
            'email_to': address,
            'auto_delete': False,
            'attachment_ids': [(6, 0, [a.id for a in (attachments or [])])],
        })
        try:
            mail.send(raise_exception=True)
        except Exception as exc:                             # noqa: BLE001
            _logger.error("pb_tenants: invoice email to %s failed: %s",
                          address, exc)
            return {'ok': False, 'to': address,
                    'reason': self._plain_smtp(exc)}
        mail.invalidate_recordset(['state', 'failure_reason'])
        if mail.state != 'sent':
            return {'ok': False, 'to': address,
                    'reason': self._plain_smtp(mail.failure_reason or '')}
        return {'ok': True, 'to': address, 'reason': '', 'mail_id': mail.id}

    # NAMED `_billing_mail_shell`, NOT `_mail_shell`, AND THE NAME IS THE
    # LESSON. `alert_service.py` already has a `_mail_shell` on this same
    # facade with a different signature, and the first version of this file
    # called its own helper by that name — which silently REPLACED the
    # platform's alert-email builder and broke the "Send a test email" button
    # with a TypeError nobody would have looked for here. One model, one
    # namespace: a helper added to a facade is a helper added to every file
    # that shares it.
    def _billing_mail_shell(self, heading, lead, blocks, tenant=None):
        """One house style for every customer-facing email in this phase.

        Brand tokens, no gradients, no images, and NOT ONE MENTION of the
        framework this is built on — an email is a user-visible string like any
        other (rail R7).
        """
        body = ''.join(blocks)
        return (
            '<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;'
            'color:#1E1B2E;max-width:620px">'
            '<div style="font-size:13px;letter-spacing:.08em;text-transform:'
            'uppercase;color:#5A4BB0;font-weight:700;margin-bottom:6px">'
            'Payobook</div>'
            '<h2 style="margin:0 0 10px;font-size:20px">%s</h2>'
            '<p style="margin:0 0 14px;font-size:15px;line-height:1.5">%s</p>'
            '%s'
            '<p style="margin:18px 0 0;font-size:13px;color:#6B6880">'
            'If anything here looks wrong, reply to this message and we will '
            'sort it out.</p>'
            '</div>' % (heading, lead, body))

    @staticmethod
    def _billing_mail_box(rows):
        """A small table of label/value pairs, as an email can render it."""
        cells = ''.join(
            '<tr><td style="padding:5px 12px 5px 0;color:#6B6880;font-size:14px">'
            '%s</td><td style="padding:5px 0;font-weight:600;font-size:14px">'
            '%s</td></tr>' % (k, v) for k, v in rows)
        return ('<table style="border:1px solid #E6E4F0;border-radius:10px;'
                'padding:10px 14px;border-collapse:separate;margin:0 0 14px">'
                '%s</table>' % cells)

    @api.model
    def invoice_send(self, invoice_id):
        """Email the invoice and its PDF, and push a copy to the customer."""
        self._require_admin()
        invoice = self._invoice(invoice_id)
        if invoice.state == 'void':
            raise UserError(_("That invoice was cancelled."))
        if not invoice.pdf:
            self._attach_pdf(invoice)
        attachments = self.env['ir.attachment'].sudo()
        if invoice.pdf:
            attachments = attachments.create({
                'name': invoice.pdf_name or ('%s.pdf' % invoice.number),
                'datas': invoice.pdf,
                'mimetype': 'application/pdf',
                'res_model': 'pb.tenant.invoice',
                'res_id': invoice.id,
            })
        tenant = invoice.tenant_id
        rows = [(_("Invoice"), invoice.number),
                (_("For"), period_label(invoice.period)),
                (_("Amount"), invoice.money(invoice.total)),
                (_("Due by"), invoice.due_date.isoformat()
                 if invoice.due_date else '—')]
        bank = (self._billing_param('pb_tenants.bank_details', '') or '').strip()
        blocks = [self._billing_mail_box(rows)]
        if bank:
            blocks.append(
                '<div style="border-left:3px solid #5A4BB0;padding:6px 0 6px 12px;'
                'margin:0 0 14px;font-size:14px;line-height:1.6;white-space:'
                'pre-wrap">%s</div>' % bank)
        body = self._billing_mail_shell(
            _("Your Payobook invoice for %s") % period_label(invoice.period),
            _("Here is your invoice for %(month)s. The PDF is attached, and "
              "it is also in Payobook under Settings → Plan &amp; usage.",
              month=period_label(invoice.period)),
            blocks)
        res = self._send_customer_mail(
            tenant, _("Payobook invoice %s") % invoice.number, body,
            attachments=attachments)
        if not res['ok']:
            raise UserError(res['reason'])
        invoice.write({
            'state': 'sent' if invoice.state == 'draft' else invoice.state,
            'sent_at': fields.Datetime.now(), 'sent_to': res['to'],
        })
        self._log_line(tenant, 'billing',
                       _("Invoice %(n)s emailed to %(to)s.",
                         n=invoice.number, to=res['to']))
        push = self._push_invoices(tenant)
        return {'ok': True, 'to': res['to'], 'push': push,
                'data': self.billing_data(invoice.period)}

    @api.model
    def invoice_mark_paid(self, invoice_id, note=''):
        self._require_admin()
        invoice = self._invoice(invoice_id)
        if invoice.state == 'void':
            raise UserError(_("That invoice was cancelled."))
        invoice.write({'state': 'paid', 'paid_at': fields.Datetime.now(),
                       'paid_note': (note or '')[:200]})
        self._clear_alert('invoice_overdue:%s' % invoice.tenant_id.slug,
                          _("The invoice was paid."))
        self._log_line(invoice.tenant_id, 'billing',
                       _("Invoice %(n)s marked paid. %(note)s",
                         n=invoice.number, note=(note or '')))
        self._push_invoices(invoice.tenant_id)
        return {'ok': True, 'data': self.billing_data(invoice.period)}

    @api.model
    def invoice_void(self, invoice_id, reason=''):
        self._require_admin()
        invoice = self._invoice(invoice_id)
        if invoice.state == 'paid':
            raise UserError(_(
                "That invoice is already paid. Cancelling a paid invoice would "
                "leave the money with nothing against it — raise a credit "
                "instead, or mark it unpaid first."))
        if not (reason or '').strip():
            raise UserError(_("Say why it is being cancelled — it stays on "
                              "the record."))
        invoice.write({'state': 'void', 'void_reason': reason.strip()[:200]})
        self._log_line(invoice.tenant_id, 'billing',
                       _("Invoice %(n)s cancelled: %(why)s",
                         n=invoice.number, why=reason.strip()))
        self._push_invoices(invoice.tenant_id)
        return {'ok': True, 'data': self.billing_data(invoice.period)}

    # ==================================================== telling the customer
    def _invoice_manifest(self, tenant):
        """The invoice list a customer sees on their own Settings page."""
        rows = self.env['pb.tenant.invoice'].sudo().search(
            [('tenant_id', '=', tenant.id), ('state', '!=', 'draft')],
            order='period desc, number desc')
        return rows

    def _push_invoices(self, tenant):
        """Put the invoices — and their PDFs — on the customer's database.

        WHY THE BYTES TRAVEL. The customer's administrator must be able to
        download last month's invoice from inside their own Payobook, on a
        morning when the platform is being restarted. A link back to us would
        be a dead link exactly when it matters, so the PDF is written into
        their own file store as an attachment and their page reads it locally.

        Never raises: a customer who cannot be reached leaves the invoice
        emailed and un-pushed, which is a row on the screen and not a failure
        of the send.
        """
        rows = self._invoice_manifest(tenant)
        manifest = []
        try:
            dbname = tenant.slug
            if not self._db_exists(dbname) or not self._tenancy_installed(dbname):
                return {'ok': False, 'reason': _(
                    "%s does not have the Platform Link yet, so the invoice "
                    "could not be put on their own screen.") % tenant.name}
            with self._tenant_env(dbname) as env:
                Att = env['ir.attachment'].sudo()
                for inv in rows:
                    name = inv.pdf_name or ('%s.pdf' % inv.number)
                    att = Att.search([('res_model', '=', 'pb.tenancy'),
                                      ('name', '=', name)], limit=1)
                    if not att and inv.pdf:
                        att = Att.create({
                            'name': name, 'datas': inv.pdf,
                            'mimetype': 'application/pdf',
                            'res_model': 'pb.tenancy', 'res_id': 0,
                        })
                    manifest.append({
                        'number': inv.number,
                        'period': inv.period.isoformat() if inv.period else '',
                        'period_label': period_label(inv.period),
                        'total': inv.money(inv.total),
                        'state': inv.state,
                        'due_date': (inv.due_date.isoformat()
                                     if inv.due_date else ''),
                        'issued_at': (inv.issued_at.isoformat()
                                      if inv.issued_at else ''),
                        'attachment_id': att.id if att else 0,
                    })
                env['ir.config_parameter'].sudo().set_param(
                    T_INVOICES, json.dumps(manifest))
        except Exception:                                    # noqa: BLE001
            _logger.warning("pb_tenants: could not put the invoices on %s",
                            tenant.slug, exc_info=True)
            return {'ok': False, 'reason': _(
                "Their database could not be reached just now — the invoice "
                "was emailed, and their own copy will appear next time.")}
        return {'ok': True, 'count': len(manifest)}

    def _access_values(self, tenant):
        plan = tenant.plan_id
        return access_payload(
            tenant.state, tenant.suspend_reason or '',
            tenant.trial_ends if tenant.state == 'trial' else None,
            plan.name or '', plan.employee_limit or 0)

    def _push_access(self, tenant, why=''):
        """Tell one customer's database where they stand. Never raises."""
        vals = self._access_values(tenant)
        payload = {T_ACCESS: vals['access'], T_ACCESS_TEXT: vals['access_text'],
                   T_TRIAL_ENDS: vals['trial_ends'],
                   T_PLAN_NAME: vals['plan_name'],
                   T_SEAT_LIMIT: vals['seat_limit'],
                   T_RECOVERY: self._rails_param(
                       'pb_tenants.break_glass_login')}
        try:
            res = self.push_tenancy(tenant.id, payload)
        except UserError as e:
            return {'ok': False, 'reason': str(e)}
        except Exception:                                    # noqa: BLE001
            _logger.warning("pb_tenants: could not push the standing to %s",
                            tenant.slug, exc_info=True)
            return {'ok': False, 'reason': _(
                "Their database could not be reached just now.")}
        if res.get('ok'):
            tenant.sudo().write({'access_pushed_at': fields.Datetime.now()})
            if why:
                self._log_line(tenant, 'billing', why)
        return res

    # ============================================== a customer's standing
    def _tenant(self, tenant_id):
        tenant = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(_("There is no such customer."))
        return tenant

    def _move_state(self, tenant, to, extra=None):
        ok, why = state_transition(tenant.state, to)
        if not ok:
            raise UserError(why)
        tenant.write(dict(extra or {}, state=to))

    @api.model
    def tenant_set_plan(self, tenant_id, plan_id, trial=False):
        """Put a customer on a plan, and give them what the plan includes.

        THE PLAN'S FEATURES BECOME `plan` ROWS, NOT `manual` ONES (P4 reserved
        the word). A switch somebody set by hand keeps its `manual` source and
        is left exactly where it is: a plan is what a customer bought, a manual
        row is somebody deciding, and deciding beats buying.
        """
        self._require_admin()
        tenant = self._tenant(tenant_id)
        plan = self.env['pb.plan'].sudo().browse(int(plan_id or 0)).exists()
        if not plan:
            raise UserError(_("Pick a plan first."))
        vals = {'plan_id': plan.id}
        if trial and tenant.state in ('trial', 'live'):
            vals['state'] = 'trial'
            vals['trial_ends'] = fields.Date.context_today(self) + timedelta(
                days=plan.trial_days or DEFAULT_TRIAL_DAYS)
            vals['trial_notified'] = ''
        tenant.write(vals)
        self._apply_plan_features(tenant, plan)
        self._push_access(tenant, _("Moved onto the %s plan.") % plan.name)
        push = self._push_features(tenant, _("Plan %s applied.") % plan.name)
        return {'ok': True, 'push': push, 'data': self.tenant_billing(tenant.id)}

    def _apply_plan_features(self, tenant, plan):
        """Write the plan's included features as `plan` rows.

        Rows the plan no longer includes are removed — but ONLY the ones this
        method wrote. A `manual` row is somebody's decision and is never
        touched here.
        """
        Row = self.env['pb.tenant.feature'].sudo()
        wanted = {f.id: f for f in plan.feature_ids}
        existing = Row.search([('tenant_id', '=', tenant.id),
                               ('source', '=', 'plan')])
        for row in existing:
            if row.feature_id.id not in wanted:
                row.unlink()
        manual = Row.search([('tenant_id', '=', tenant.id),
                             ('source', '=', 'manual')]).mapped('feature_id.id')
        for fid, feature in wanted.items():
            if fid in manual:
                continue
            row = Row.search([('tenant_id', '=', tenant.id),
                              ('feature_id', '=', fid)], limit=1)
            vals = {'on': True, 'source': 'plan',
                    'reason': _("Included in the %s plan.") % plan.name,
                    'changed_by': self.env.user.id,
                    'changed_at': fields.Datetime.now()}
            if row:
                row.write(vals)
            else:
                Row.create(dict(vals, tenant_id=tenant.id, feature_id=fid))

    @api.model
    def tenant_convert(self, tenant_id):
        """Trial to paying customer."""
        self._require_admin()
        tenant = self._tenant(tenant_id)
        self._move_state(tenant, 'live', {'trial_ends': False,
                                          'trial_notified': ''})
        self._push_access(tenant, _("Trial converted — they are now a paying "
                                    "customer."))
        self._clear_alert('trial_ending:%s' % tenant.slug,
                          _("The trial was converted."))
        return {'ok': True, 'data': self.tenant_billing(tenant.id)}

    @api.model
    def tenant_suspend(self, tenant_id, reason='', confirm_slug=''):
        """Pause a customer. Their data is untouched; their door is shut."""
        self._require_admin()
        tenant = self._tenant(tenant_id)
        if (confirm_slug or '').strip() != tenant.slug:
            raise UserError(_(
                "Type %s to confirm. Pausing shuts every one of their people "
                "out of Payobook until somebody resumes it.") % tenant.slug)
        return self._do_suspend(tenant, reason or _("Unpaid invoice."))

    def _do_suspend(self, tenant, reason):
        self._move_state(tenant, 'suspended', {
            'suspended_at': fields.Datetime.now(),
            'suspend_reason': (reason or '')[:200],
        })
        push = self._push_access(tenant, _("Access paused: %s") % reason)
        self._raise_alert(
            'tenant_suspended:%s' % tenant.slug, 'suspend_candidate', 'warning',
            _("%s is paused") % tenant.name,
            _("%(name)s's people cannot sign in. Reason: %(why)s. Resume them "
              "from their Plan tab the moment it is settled.",
              name=tenant.name, why=reason), tenant)
        return {'ok': True, 'push': push, 'data': self.tenant_billing(tenant.id)}

    @api.model
    def tenant_resume(self, tenant_id):
        """Let them back in. One click, no typing — undoing harm is never
        made harder than doing it."""
        self._require_admin()
        tenant = self._tenant(tenant_id)
        back = 'trial' if (tenant.trial_ends and tenant.trial_ends
                           >= fields.Date.context_today(self)) else 'live'
        self._move_state(tenant, back, {'suspended_at': False,
                                        'suspend_reason': False})
        push = self._push_access(tenant, _("Access resumed."))
        self._clear_alert('tenant_suspended:%s' % tenant.slug,
                          _("They were resumed."))
        self._clear_alert('suspend_candidate:%s' % tenant.slug,
                          _("They were resumed."))
        return {'ok': True, 'push': push, 'data': self.tenant_billing(tenant.id)}

    @api.model
    def tenant_schedule_deletion(self, tenant_id, days=DEFAULT_RETENTION_DAYS,
                                 reason='', confirm_slug=''):
        """Set the day their data may be deleted — and take a backup now.

        NOTHING DELETES ANYTHING. The date is a promise to the customer and a
        reminder to us; the deletion itself is still the offboard button with
        its own typed confirmation. A clock that erases a payroll database on
        its own is not a feature.
        """
        self._require_admin()
        tenant = self._tenant(tenant_id)
        if (confirm_slug or '').strip() != tenant.slug:
            raise UserError(_("Type %s to confirm.") % tenant.slug)
        try:
            days = max(1, int(days or DEFAULT_RETENTION_DAYS))
        except (TypeError, ValueError):
            days = DEFAULT_RETENTION_DAYS
        backup = ''
        try:
            self._do_backup(tenant, 'final')
            backup = _("A final backup was taken first.")
        except Exception:                                    # noqa: BLE001
            _logger.warning("pb_tenants: final backup before scheduling "
                            "deletion of %s failed", tenant.slug, exc_info=True)
            backup = _("The final backup did NOT succeed — take one by hand "
                       "before anything is deleted.")
        self._move_state(tenant, 'pending_deletion', {
            'delete_after': fields.Date.context_today(self) + timedelta(days=days),
            'deletion_reason': (reason or '')[:200],
        })
        self._log_line(tenant, 'billing', _(
            "Scheduled for deletion after %(day)s. %(backup)s",
            day=tenant.delete_after.isoformat(), backup=backup))
        return {'ok': True, 'backup': backup,
                'data': self.tenant_billing(tenant.id)}

    @api.model
    def tenant_cancel_deletion(self, tenant_id):
        self._require_admin()
        tenant = self._tenant(tenant_id)
        self._move_state(tenant, 'live', {'delete_after': False,
                                          'deletion_reason': False})
        self._push_access(tenant, _("Deletion called off."))
        return {'ok': True, 'data': self.tenant_billing(tenant.id)}

    # ================================================================== alerts
    def _raise_alert(self, key, kind, severity, title, text, tenant=None):
        """Raise or refresh one billing alert.

        These kinds are SELF-MANAGED (see `alert_rules.SELF_MANAGED_KINDS`):
        the fifteen-minute sweep takes no reading that could see an unpaid
        invoice, so if it were allowed to reconcile them it would close every
        one of them on its next run.
        """
        Alert = self.env['pb.alert'].sudo()
        now = fields.Datetime.now()
        row = Alert.search([('key', '=', key),
                            ('state', 'in', ('open', 'acknowledged'))], limit=1)
        if row:
            row.write({'last_seen': now, 'count': row.count + 1,
                       'severity': severity, 'title': title, 'text': text})
            return row
        return Alert.create({
            'key': key, 'kind': kind, 'severity': severity, 'title': title,
            'text': text, 'tenant_id': tenant.id if tenant else False,
            'first_seen': now, 'last_seen': now, 'count': 1, 'state': 'open',
        })

    def _clear_alert(self, key, why):
        rows = self.env['pb.alert'].sudo().search(
            [('key', '=', key), ('state', 'in', ('open', 'acknowledged'))])
        if rows:
            rows.write({'state': 'resolved',
                        'resolved_at': fields.Datetime.now(),
                        'resolution': why})
        return len(rows)

    # =================================================== the daily billing job
    @api.model
    def _cron_billing(self):
        """Once a morning: chase what is owed, and count the trials down.

        THE ONE THING IT CAN DO TO A CUSTOMER is pause them, and only when the
        owner has switched that on. Everything else it does is send an email
        and raise a flag on our own screen.
        """
        today = fields.Date.context_today(self)
        res = {'overdue': 0, 'reminders': 0, 'candidates': 0, 'suspended': 0,
               'trials': 0}
        try:
            res.update(self._billing_chase(today))
        except Exception:                                    # noqa: BLE001
            _logger.exception("pb_tenants: the invoice chase failed")
        try:
            res.update(self._trial_watch(today))
        except Exception:                                    # noqa: BLE001
            _logger.exception("pb_tenants: the trial countdown failed")
        self.env.cr.commit()
        return res

    def _billing_chase(self, today):
        Invoice = self.env['pb.tenant.invoice'].sudo()
        due_days, reminders, suspend_after = (
            self._due_days(), self._reminder_days(), self._suspend_after())
        auto = self._auto_suspend_on()
        counts = {'overdue': 0, 'reminders': 0, 'candidates': 0, 'suspended': 0}
        rows = Invoice.search([('state', 'in', ('sent', 'overdue'))])
        for inv in rows:
            verdict = next_state(
                {'state': inv.state, 'due_date': inv.due_date,
                 'reminder_count': inv.reminder_count},
                today, due_days, reminders, suspend_after)
            if verdict['changed']:
                inv.write({'state': verdict['state']})
                counts['overdue'] += 1
            if verdict['remind']:
                if self._send_reminder(inv, verdict['days_overdue'],
                                       verdict['reminder_no']):
                    counts['reminders'] += 1
            if verdict['suspend_candidate']:
                counts['candidates'] += 1
                self._suspend_candidate(inv, verdict['days_overdue'], auto)
                if auto:
                    counts['suspended'] += 1
            self.env.cr.commit()
        return counts

    def _send_reminder(self, invoice, days, number):
        tenant = invoice.tenant_id
        rows = [(_("Invoice"), invoice.number),
                (_("For"), period_label(invoice.period)),
                (_("Amount"), invoice.money(invoice.total)),
                (_("Was due"), invoice.due_date.isoformat()
                 if invoice.due_date else '—')]
        bank = (self._billing_param('pb_tenants.bank_details', '') or '').strip()
        blocks = [self._billing_mail_box(rows)]
        if bank:
            blocks.append(
                '<div style="border-left:3px solid #5A4BB0;padding:6px 0 6px 12px;'
                'margin:0 0 14px;font-size:14px;line-height:1.6;white-space:'
                'pre-wrap">%s</div>' % bank)
        body = self._billing_mail_shell(
            _("A reminder about invoice %s") % invoice.number,
            _("Invoice %(n)s is %(d)s day(s) past its due date. If it has "
              "already been paid, please ignore this — and tell us, so we can "
              "mark it off.", n=invoice.number, d=days),
            blocks)
        res = self._send_customer_mail(
            tenant, _("Reminder: Payobook invoice %s") % invoice.number, body)
        if res['ok']:
            invoice.write({'reminder_count': number,
                           'last_reminder_at': fields.Datetime.now()})
            self._log_line(tenant, 'billing', _(
                "Reminder %(n)s sent for invoice %(inv)s.",
                n=number, inv=invoice.number))
        else:
            _logger.warning("pb_tenants: reminder for %s not sent: %s",
                            invoice.number, res['reason'])
        self._raise_alert(
            'invoice_overdue:%s' % tenant.slug, 'invoice_overdue', 'warning',
            _("%s has an unpaid invoice") % tenant.name,
            _("Invoice %(n)s for %(p)s (%(t)s) is %(d)s day(s) overdue. "
              "%(mail)s",
              n=invoice.number, p=period_label(invoice.period),
              t=invoice.money(invoice.total), d=days,
              mail=(_("A reminder has been emailed to %s.") % res['to'])
              if res['ok'] else
              (_("The reminder could NOT be emailed: %s") % res['reason'])),
            tenant)
        return res['ok']

    def _suspend_candidate(self, invoice, days, auto):
        tenant = invoice.tenant_id
        if tenant.state == 'suspended':
            return
        if auto:
            _logger.warning("pb_tenants: auto-suspending %s over invoice %s",
                            tenant.slug, invoice.number)
            self._do_suspend(tenant, _(
                "Invoice %(n)s has been unpaid for %(d)s days.",
                n=invoice.number, d=days))
            return
        self._raise_alert(
            'suspend_candidate:%s' % tenant.slug, 'suspend_candidate',
            'critical',
            _("%s is %s days overdue — pause them?") % (tenant.name, days),
            _("Invoice %(n)s for %(p)s (%(t)s) has been unpaid for %(d)s days. "
              "Nothing has been done to them: pausing a customer is a button "
              "on their Plan tab, and it is yours to press. Their data is "
              "untouched either way.",
              n=invoice.number, p=period_label(invoice.period),
              t=invoice.money(invoice.total), d=days), tenant)

    def _trial_watch(self, today):
        """Count the trials down, and say so — to the customer and to us."""
        sent = 0
        for tenant in self.env['pb.tenant'].sudo().search(
                [('state', '=', 'trial')]):
            phase = trial_phase(tenant.trial_ends, today)
            done = [m for m in (tenant.trial_notified or '').split(',') if m]
            days = phase['days_left']
            milestone = ''
            if phase['phase'] == 'ended':
                milestone = 'ended'
            elif phase['phase'] == 'ending' and days <= 1:
                milestone = 'tomorrow'
            elif phase['phase'] == 'ending' and days <= 7:
                milestone = 'seven'
            # The countdown itself goes to their database every day it is
            # running: their bar reads the date, so a trial extended by hand
            # must be reflected without anybody pressing anything.
            self._push_access(tenant)
            if milestone and milestone not in done:
                if self._trial_mail(tenant, phase):
                    done.append(milestone)
                    tenant.write({'trial_notified': ','.join(done)})
                    sent += 1
            if phase['phase'] == 'ended' and abs(days) >= TRIAL_GRACE_DAYS:
                self._raise_alert(
                    'trial_ended:%s' % tenant.slug, 'trial_ending', 'warning',
                    _("%s's trial has ended") % tenant.name,
                    _("The trial ended on %(day)s. Convert them to a paying "
                      "customer, extend the trial, or pause them — all three "
                      "are buttons on their Plan tab. Nothing has happened to "
                      "their data.", day=tenant.trial_ends.isoformat()
                      if tenant.trial_ends else '—'), tenant)
            elif phase['phase'] == 'ending':
                self._raise_alert(
                    'trial_ending:%s' % tenant.slug, 'trial_ending', 'info',
                    _("%(name)s's trial ends in %(d)s day(s)",
                      name=tenant.name, d=max(days, 0)),
                    _("Their trial ends on %(day)s. Convert them on their "
                      "Plan tab when they are ready.",
                      day=tenant.trial_ends.isoformat()
                      if tenant.trial_ends else '—'), tenant)
            self.env.cr.commit()
        return {'trials': sent}

    def _trial_mail(self, tenant, phase):
        days = phase['days_left']
        if phase['phase'] == 'ended':
            heading = _("Your Payobook trial has ended")
            lead = _("Your trial ended on %s. Nothing has been deleted and "
                     "nothing has been switched off yet — tell us you would "
                     "like to carry on and we will move you onto a plan.") % (
                tenant.trial_ends.isoformat() if tenant.trial_ends else '')
        else:
            heading = trial_sentence(days)
            lead = _("Everything you have entered stays exactly where it is. "
                     "Reply to this message and we will move you onto a plan "
                     "before it runs out.")
        body = self._billing_mail_shell(heading, lead, [self._billing_mail_box([
            (_("Trial ends"), tenant.trial_ends.isoformat()
             if tenant.trial_ends else '—'),
            (_("Plan"), tenant.plan_id.name or _("Not chosen yet")),
        ])])
        res = self._send_customer_mail(
            tenant, heading, body,
            to=(tenant.admin_email or tenant.billing_to()))
        if not res['ok']:
            _logger.warning("pb_tenants: trial email to %s not sent: %s",
                            tenant.slug, res['reason'])
        return res['ok']

    # =============================================== what the cockpit reads
    @api.model
    def billing_data(self, period=None):
        """Everything the Billing screen draws, in one call."""
        self._require_admin()
        today = fields.Date.context_today(self)
        period = self._period_from(period)
        Invoice = self.env['pb.tenant.invoice'].sudo()
        Usage = self.env['pb.tenant.usage'].sudo()
        tenants = self._serving()
        month = Invoice.search([('period', '=', period)])
        outstanding = Invoice.search([('state', 'in', ('sent', 'overdue'))])
        rows = []
        for tenant in tenants:
            usage = Usage.search([('tenant_id', '=', tenant.id),
                                  ('period', '=', period)], limit=1)
            invoice = month.filtered(lambda i: i.tenant_id.id == tenant.id
                                     and i.state != 'void')[:1]
            plan = tenant.plan_id
            rows.append({
                'id': tenant.id, 'name': tenant.name, 'slug': tenant.slug,
                'state': tenant.state,
                'plan': plan.name or '', 'plan_id': plan.id or False,
                'employee_limit': plan.employee_limit or 0,
                'employees': usage.employees if usage else 0,
                'payslips': usage.payslips if usage else 0,
                'measured': (usage.measured_at.isoformat(sep=' ',
                                                         timespec='minutes')
                             if usage and usage.measured_at else ''),
                'seat': seat_verdict(plan.employee_limit or 0,
                                     usage.employees if usage else 0),
                'invoice': invoice.as_dict()[0] if invoice else None,
                'trial_ends': (tenant.trial_ends.isoformat()
                               if tenant.trial_ends else ''),
                'trial': tenant.trial_state(today),
                'delete_after': (tenant.delete_after.isoformat()
                                 if tenant.delete_after else ''),
                'billing_email': tenant.billing_to(),
                'history': self._usage_history(tenant, period),
            })
        by_currency = {}
        for inv in outstanding:
            key = inv.currency_id.name or ''
            by_currency.setdefault(key, {'amount': 0.0, 'count': 0,
                                         'symbol': inv.currency_id.symbol or '',
                                         'rounding': inv.currency_id.rounding})
            by_currency[key]['amount'] += inv.total
            by_currency[key]['count'] += 1
        return {
            'period': period.isoformat(),
            'period_label': period_label(period),
            'closed': month_closed(period, today),
            'months': self._month_strip(period),
            'rows': rows,
            'month_invoices': [i.as_dict()[0] for i in month],
            'due': [{'currency': k,
                     'amount_h': money(v['amount'], v['symbol'], v['rounding']),
                     'count': v['count']}
                    for k, v in sorted(by_currency.items())],
            'overdue_count': len(outstanding.filtered(
                lambda i: i.state == 'overdue')),
            'unpaid_count': len(outstanding),
            'plans': self.env['pb.plan'].sudo().catalogue(),
            'settings': self._billing_settings(),
            'auto_suspend': self._auto_suspend_on(),
            'currencies': [{'id': c.id, 'name': c.name, 'symbol': c.symbol or ''}
                           for c in self.env['res.currency'].sudo().search(
                               [('active', '=', True)], limit=200)],
            'features': self.env['pb.feature'].sudo().catalogue(),
            'pricing': [{'key': p, 'label': PRICING_LABEL[p]} for p in PRICING],
        }

    def _month_strip(self, period, back=12):
        """The last twelve months, each with what was invoiced in it."""
        Invoice = self.env['pb.tenant.invoice'].sudo()
        out, cursor = [], period
        for _i in range(back):
            rows = Invoice.search([('period', '=', cursor),
                                   ('state', '!=', 'void')])
            paid = rows.filtered(lambda i: i.state == 'paid')
            out.append({
                'period': cursor.isoformat(),
                'label': period_label(cursor),
                'short': '%s %s' % (period_label(cursor)[:3], cursor.year),
                'invoices': len(rows),
                'paid': len(paid),
                'overdue': len(rows.filtered(lambda i: i.state == 'overdue')),
                'current': cursor == period,
            })
            cursor = prev_month(cursor)
        out.reverse()
        return out

    def _usage_history(self, tenant, period, back=12):
        """Twelve readings, oldest first — the sparkline's numbers."""
        Usage = self.env['pb.tenant.usage'].sudo()
        cursor, out = period, []
        for _i in range(back):
            row = Usage.search([('tenant_id', '=', tenant.id),
                                ('period', '=', cursor)], limit=1)
            out.append({'period': cursor.isoformat(),
                        'label': period_label(cursor),
                        'employees': row.employees if row else 0,
                        'payslips': row.payslips if row else 0})
            cursor = prev_month(cursor)
        out.reverse()
        return out

    @api.model
    def tenant_billing(self, tenant_id):
        """One customer's Plan tab, in one call."""
        self._require_admin()
        tenant = self._tenant(tenant_id)
        today = fields.Date.context_today(self)
        usage = self.env['pb.tenant.usage'].sudo().search(
            [('tenant_id', '=', tenant.id)], order='period desc', limit=13)
        invoices = self.env['pb.tenant.invoice'].sudo().search(
            [('tenant_id', '=', tenant.id)], order='period desc, number desc')
        plan = tenant.plan_id
        latest = usage[:1]
        return {
            'id': tenant.id, 'name': tenant.name, 'slug': tenant.slug,
            'state': tenant.state,
            'plan_id': plan.id or False, 'plan': plan.name or '',
            'plan_blurb': plan.blurb or '',
            'plan_headline': plan.headline() if plan else '',
            'employee_limit': plan.employee_limit or 0,
            'billing_email': tenant.billing_to(),
            'billing_email_set': tenant.billing_email or '',
            'admin_email': tenant.admin_email or '',
            'trial_ends': (tenant.trial_ends.isoformat()
                           if tenant.trial_ends else ''),
            'trial': tenant.trial_state(today),
            'suspended_at': (tenant.suspended_at.isoformat(sep=' ',
                                                           timespec='minutes')
                             if tenant.suspended_at else ''),
            'suspend_reason': tenant.suspend_reason or '',
            'delete_after': (tenant.delete_after.isoformat()
                             if tenant.delete_after else ''),
            'deletion_reason': tenant.deletion_reason or '',
            'access_pushed_at': (tenant.access_pushed_at.isoformat(
                sep=' ', timespec='minutes') if tenant.access_pushed_at else ''),
            'seat': seat_verdict(plan.employee_limit or 0,
                                 latest.employees if latest else 0),
            'usage': usage.as_dict(),
            'invoices': invoices.as_dict(),
            'plans': self.env['pb.plan'].sudo().catalogue(),
            'linked': self._tenancy_installed(tenant.slug) if tenant.slug else False,
        }

    @api.model
    def tenant_billing_save(self, tenant_id, vals):
        """The small edits on the Plan tab: where invoices go, trial dates."""
        self._require_admin()
        tenant = self._tenant(tenant_id)
        clean = {}
        email = (vals or {}).get('billing_email')
        if email is not None:
            email = (email or '').strip()
            if email and not EMAIL_RE.match(email):
                raise UserError(_('"%s" is not an email address.') % email)
            clean['billing_email'] = email
        trial = (vals or {}).get('trial_ends')
        if trial is not None:
            clean['trial_ends'] = fields.Date.to_date(trial) if trial else False
            clean['trial_notified'] = ''
        if clean:
            tenant.write(clean)
            self._push_access(tenant)
        return self.tenant_billing(tenant.id)

    # ============================================================ the catalogue
    PLAN_WRITABLE = ('name', 'code', 'blurb', 'pricing', 'price',
                     'currency_id', 'employee_limit', 'vat_pct', 'trial_days',
                     'sequence', 'active')

    @api.model
    def plan_save(self, plan_id, vals):
        """Create or edit one plan. Tiers and features come in whole."""
        self._require_admin()
        clean = {k: v for k, v in (vals or {}).items() if k in self.PLAN_WRITABLE}
        if 'name' in clean and not (clean['name'] or '').strip():
            raise UserError(_("A plan needs a name people can read."))
        if 'pricing' in clean and clean['pricing'] not in PRICING:
            raise UserError(_("Pick how the plan charges."))
        # THE BANDS GO IN THE SAME WRITE AS THE PRICE STRUCTURE. A plan saved
        # as "one price by company size" and then given its bands afterwards
        # fails its own constraint in between — which is correct, and which is
        # why the two halves travel together.
        tiers = (vals or {}).get('tiers')
        if tiers is not None:
            rows = []
            for tier in tiers:
                try:
                    rows.append((0, 0, {'up_to': int(tier.get('up_to') or 0),
                                        'price': float(tier.get('price') or 0.0)}))
                except (TypeError, ValueError):
                    raise UserError(_("A size band needs a number of "
                                      "employees and a price."))
            clean['tier_ids'] = [(5, 0, 0)] + rows
        features = (vals or {}).get('feature_ids')
        if features is not None:
            clean['feature_ids'] = [(6, 0, [int(f) for f in features])]
        Plan = self.env['pb.plan'].sudo()
        if plan_id:
            plan = Plan.browse(int(plan_id)).exists()
            if not plan:
                raise UserError(_("There is no such plan."))
            plan.write(clean)
        else:
            if not clean.get('name'):
                raise UserError(_("A plan needs a name people can read."))
            clean.setdefault('code', re.sub(
                r'[^a-z0-9_]+', '_', clean['name'].lower()).strip('_') or 'plan')
            clean.setdefault('currency_id', self.env.company.currency_id.id)
            plan = Plan.create(clean)
        # A plan's included features moved, so every customer on it is brought
        # back in line — still rail R1, somebody pressed Save.
        for tenant in plan.tenant_ids.filtered(
                lambda t: t.state in SERVING_STATES):
            self._apply_plan_features(tenant, plan)
            self._push_features(tenant, _("The %s plan was edited.") % plan.name)
            self._push_access(tenant)
        return {'ok': True, 'plan_id': plan.id,
                'plans': self.env['pb.plan'].sudo().catalogue()}

    @api.model
    def plan_archive(self, plan_id, archive=True):
        self._require_admin()
        plan = self.env['pb.plan'].sudo().browse(int(plan_id)).exists()
        if not plan:
            raise UserError(_("There is no such plan."))
        if archive and plan.tenant_count:
            raise UserError(_(
                "%(n)s customer(s) are on the %(name)s plan. Move them to "
                "another plan first — archiving it would leave them with no "
                "price and no limit.", n=plan.tenant_count, name=plan.name))
        plan.write({'active': not archive})
        return {'ok': True, 'plans': self.env['pb.plan'].sudo().catalogue()}

    # ============================================================== settings
    @api.model
    def billing_settings_save(self, vals):
        """The billing settings, including the one that pauses customers."""
        self._require_admin()
        icp = self.env['ir.config_parameter'].sudo()
        touched = []
        for short, value in (vals or {}).items():
            key = 'pb_tenants.%s' % short
            if key not in BILLING_DEFAULTS:
                continue
            if short == 'billing_from_email' and value and not EMAIL_RE.match(value):
                raise UserError(_('"%s" is not an email address.') % value)
            icp.set_param(key, '' if value is None else str(value))
            touched.append(short)
        if 'auto_suspend' in touched:
            _logger.warning("pb_tenants: auto-suspend switched %s by %s",
                            'ON' if self._auto_suspend_on() else 'OFF',
                            self.env.user.login)
        return {'ok': True, 'settings': self._billing_settings(),
                'auto_suspend': self._auto_suspend_on()}
