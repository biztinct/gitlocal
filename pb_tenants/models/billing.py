# -*- coding: utf-8 -*-
"""FLEET P5 — what was measured, and what was invoiced for it.

TWO TABLES AND THEY ARE NOT THE SAME THING. `pb.tenant.usage` is a READING: how
many people were on Payobook at the end of September and how many payslips came
out of it. It is taken once, it is never edited, and it is taken for every
customer whatever plan they are on — because a plan can change next month and
last month cannot be measured again.

`pb.tenant.invoice` is what the owner DECIDED to charge for that reading. It
carries its own copy of the plan's name, price and tax at the moment it was
raised, so an invoice sent in September still says what it said in September
after the plan is edited in October. An invoice that recomputes itself from
today's plan is not a document, it is a query.

NOT AN ACCOUNTING ENTRY. These are the platform's own records — no journal, no
`account.move`, no reconciliation. The owner marks an invoice paid when the
bank transfer arrives, and the seam for a payment provider later is `state`
plus `paid_ref`, which nothing today writes.
"""
from odoo import _, api, fields, models

from .billing_rules import (
    INVOICE_STATES, PRICING, PRICING_LABEL, money, period_label, qty_text,
)

INVOICE_STATE_LABEL = {
    'draft': "Not sent yet",
    'sent': "Sent, waiting for payment",
    'paid': "Paid",
    'overdue': "Overdue",
    'void': "Cancelled",
}


class PbTenantUsage(models.Model):
    _name = 'pb.tenant.usage'
    _description = 'What one customer used in one month'
    _order = 'period desc, tenant_id'

    tenant_id = fields.Many2one('pb.tenant', required=True, ondelete='cascade',
                                index=True)
    period = fields.Date(required=True, index=True,
                         help="The first day of the month this reading covers.")
    employees = fields.Integer(
        help="People on Payobook on the last day of the month.")
    payslips = fields.Integer(
        help="Payslips produced during the month.")
    measured_at = fields.Datetime(default=fields.Datetime.now)
    #: The daily readings the month was built from, as JSON. Kept because the
    #: month-end number is the one that bills and the daily shape is the only
    #: thing that can ever explain it — "we had 40 people all month and you
    #: charged us for 55" is answerable with this and unanswerable without it.
    sample = fields.Text(default='{}')
    note = fields.Char()

    _sql_constraints = [
        ('one_per_month', 'unique(tenant_id, period)',
         'That customer already has a reading for that month.'),
    ]

    def as_dict(self):
        out = []
        for u in self:
            out.append({
                'id': u.id, 'tenant_id': u.tenant_id.id,
                'period': u.period.isoformat() if u.period else '',
                'period_label': period_label(u.period),
                'employees': u.employees, 'payslips': u.payslips,
                'measured_at': (u.measured_at.isoformat(sep=' ',
                                                        timespec='minutes')
                                if u.measured_at else ''),
                'note': u.note or '',
            })
        return out


class PbTenantInvoice(models.Model):
    _name = 'pb.tenant.invoice'
    _description = 'Payobook invoice to one customer'
    _order = 'period desc, number desc, id desc'

    tenant_id = fields.Many2one('pb.tenant', required=True, ondelete='cascade',
                                index=True)
    number = fields.Char(required=True, index=True, copy=False,
                         help="PB-2026-09-0001. Never reused.")
    period = fields.Date(required=True, index=True,
                         help="The first day of the month being invoiced.")
    #: A SNAPSHOT, not a live link. The plan may be renamed or repriced
    #: tomorrow; this invoice must keep saying what it said when it was sent.
    plan_id = fields.Many2one('pb.plan', ondelete='set null')
    plan_name = fields.Char()
    plan_pricing = fields.Selection([(p, PRICING_LABEL[p]) for p in PRICING])
    line_ids = fields.One2many('pb.tenant.invoice.line', 'invoice_id')

    currency_id = fields.Many2one('res.currency', required=True)
    subtotal = fields.Float(digits=(16, 2))
    vat_pct = fields.Float(digits=(16, 2))
    vat_amount = fields.Float(digits=(16, 2))
    total = fields.Float(digits=(16, 2))

    employees = fields.Integer(help="The reading this invoice was raised from.")
    payslips = fields.Integer()

    state = fields.Selection([(s, INVOICE_STATE_LABEL[s]) for s in INVOICE_STATES],
                             default='draft', required=True, index=True)
    issued_at = fields.Date(default=fields.Date.context_today)
    due_date = fields.Date(index=True)
    sent_at = fields.Datetime()
    sent_to = fields.Char()
    paid_at = fields.Datetime()
    paid_note = fields.Char(help="How it was paid, in the owner's own words.")
    #: THE SEAM FOR A PAYMENT PROVIDER, and nothing writes it today. When cards
    #: arrive, the provider's reference lands here and `state` goes to `paid`
    #: through the same method the owner presses now.
    paid_ref = fields.Char()
    void_reason = fields.Char()
    reminder_count = fields.Integer(default=0)
    last_reminder_at = fields.Datetime()
    #: The PDF as it was rendered when the invoice was raised. Stored rather
    #: than re-rendered on demand for the same reason the plan is snapshotted:
    #: a document that changes after it was sent is not a document.
    pdf = fields.Binary(attachment=True)
    pdf_name = fields.Char()

    _sql_constraints = [
        ('number_unique', 'unique(number)', 'That invoice number already exists.'),
    ]

    def money(self, amount):
        self.ensure_one()
        cur = self.currency_id
        return money(amount, cur.symbol or '', cur.rounding or 0.01,
                     cur.position or 'after')

    def as_dict(self):
        out = []
        today = fields.Date.context_today(self)
        for inv in self:
            days_overdue = 0
            if inv.due_date and inv.state in ('sent', 'overdue'):
                days_overdue = max(0, (today - inv.due_date).days)
            out.append({
                'id': inv.id,
                'tenant_id': inv.tenant_id.id,
                'tenant': inv.tenant_id.name or '',
                'slug': inv.tenant_id.slug or '',
                'number': inv.number or '',
                'period': inv.period.isoformat() if inv.period else '',
                'period_label': period_label(inv.period),
                'plan_name': inv.plan_name or '',
                'state': inv.state,
                'state_label': INVOICE_STATE_LABEL.get(inv.state, inv.state),
                'subtotal': inv.subtotal, 'subtotal_h': inv.money(inv.subtotal),
                'vat_pct': inv.vat_pct, 'vat_amount': inv.vat_amount,
                'vat_h': inv.money(inv.vat_amount),
                'total': inv.total, 'total_h': inv.money(inv.total),
                'currency': inv.currency_id.name or '',
                'employees': inv.employees, 'payslips': inv.payslips,
                'issued_at': inv.issued_at.isoformat() if inv.issued_at else '',
                'due_date': inv.due_date.isoformat() if inv.due_date else '',
                'days_overdue': days_overdue,
                'sent_at': (inv.sent_at.isoformat(sep=' ', timespec='minutes')
                            if inv.sent_at else ''),
                'sent_to': inv.sent_to or '',
                'paid_at': (inv.paid_at.isoformat(sep=' ', timespec='minutes')
                            if inv.paid_at else ''),
                'paid_note': inv.paid_note or '',
                'void_reason': inv.void_reason or '',
                'reminder_count': inv.reminder_count,
                'has_pdf': bool(inv.pdf),
                'lines': [{
                    'label': l.label or '', 'detail': l.detail or '',
                    'qty': l.qty, 'qty_h': qty_text(l.qty),
                    'unit_price': l.unit_price,
                    'unit_h': inv.money(l.unit_price),
                    'amount': l.amount, 'amount_h': inv.money(l.amount),
                } for l in inv.line_ids],
            })
        return out


    # ------------------------------------------------------------------ PDF
    def _customer_identity(self):
        """Who this invoice is addressed to, read off THEIR database.

        READ-ONLY SQL on the customer's own database (rail R1): the details a
        customer corrects on their own "Your company" page are the details that
        must print on the invoice, and copying them onto our record would mean
        printing whatever they were when the customer was created.

        A database that cannot be read falls back to what the platform knows —
        the company name and the administrator's address — rather than printing
        a blank block. An invoice with no addressee is not a document.
        """
        self.ensure_one()
        tenant = self.tenant_id
        fallback = {
            'name': tenant.name or '',
            'address': '',
            'vat': '',
            'email': tenant.billing_to() or '',
        }
        if not tenant.slug:
            return fallback
        try:
            with self.env['pb.tenants'].sudo()._pg_cursor(tenant.slug) as cr:
                cr.execute("""
                    SELECT p.name, p.street, p.street2, p.city, p.zip,
                           p.vat, p.email
                      FROM res_company c
                      JOIN res_partner p ON p.id = c.partner_id
                  ORDER BY c.id LIMIT 1""")
                row = cr.fetchone()
        except Exception:                                    # noqa: BLE001
            return fallback
        if not row:
            return fallback
        name, street, street2, city, zipcode, vat, email = row
        parts = [p for p in (street, street2,
                             ' '.join(x for x in (zipcode, city) if x)) if p]
        return {
            'name': name or fallback['name'],
            'address': '\n'.join(parts),
            'vat': vat or '',
            'email': email or fallback['email'],
        }

    def _render_data(self):
        """Everything the printed invoice puts on the page, already worded.

        The template holds property access and nothing else — no arithmetic and
        no formatting — so the figures on the PDF are the figures the invoice
        record carries, formatted by the one money formatter the whole phase
        uses.
        """
        self.ensure_one()
        svc = self.env['pb.tenants'].sudo()
        who = self._customer_identity()
        seller_name = (svc._billing_param('pb_tenants.billing_company',
                                          'Payobook') or 'Payobook').strip()
        data = self.as_dict()[0]
        return {
            'number': self.number or '',
            'state': self.state,
            'period_label': data['period_label'],
            'issued_at': self.issued_at.strftime('%d %B %Y') if self.issued_at else '',
            'due_date': self.due_date.strftime('%d %B %Y') if self.due_date else '',
            'customer_name': who['name'],
            'customer_address': who['address'],
            'customer_vat': who['vat'],
            'customer_email': who['email'],
            'seller_name': seller_name,
            'seller_address': (svc._billing_param('pb_tenants.billing_address', '')
                               or '').strip(),
            'seller_vat': (svc._billing_param('pb_tenants.billing_vat', '')
                           or '').strip(),
            'bank_details': (svc._billing_param('pb_tenants.bank_details', '')
                             or '').strip(),
            'footer': (svc._billing_param('pb_tenants.invoice_footer', '')
                       or '').strip(),
            'lines': data['lines'],
            'subtotal_h': data['subtotal_h'],
            'vat_pct': self.vat_pct or 0.0,
            'vat_pct_h': ('%g' % (self.vat_pct or 0.0)),
            'vat_h': data['vat_h'],
            'total_h': data['total_h'],
        }


class PbTenantInvoiceLine(models.Model):
    _name = 'pb.tenant.invoice.line'
    _description = 'One line of a Payobook invoice'
    _order = 'invoice_id, sequence, id'

    invoice_id = fields.Many2one('pb.tenant.invoice', required=True,
                                 ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    label = fields.Char(required=True)
    detail = fields.Char(help="The small print under the line.")
    qty = fields.Float(digits=(16, 2), default=1.0)
    unit_price = fields.Float(digits=(16, 2))
    amount = fields.Float(digits=(16, 2))
