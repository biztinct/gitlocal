# -*- coding: utf-8 -*-
"""Learning › CERTIFICATES — the register (LEARNING L1).

One read, `pb.training.certificates_board(filters)`, behind the same gate as
the board (`{'allowed': False}` without a training group). The rows are vault
documents with a `training_source`, read AS THE SYSTEM and narrowed by hand to
`company_id in env.companies` — the vault's own rules let only HR read other
people's documents, and a trainer holds no HR group by definition.

THE COUNTS ARE ONE FUNCTION (`_cert_counts`), read by the register's tiles,
the Overview block and the Numbers tiles, so "12 expire within 30 days" is the
same 12 on all three screens (R80).

Three verbs join the board's allow-list: `add_certificate` (HR files one for
anybody — verified on the spot, through the vault's own path),
`verify_certificate` and `assign_refresher` (the renewal course, now).
"""

import base64
import binascii
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .pb_training_claims import PbTrainingClaims
from .training_common import ASSIGN_OPEN, P_PEOPLE_LIMIT, as_id, fold, number

_logger = logging.getLogger(__name__)

#: Rows per page on the register.
PAGE_SIZE = 50

#: The register's filters, in the order the tiles are drawn.
TILE_KEYS = ('expiring_30', 'expiring_60', 'expiring_90', 'expired', 'valid',
             'no_expiry')

#: Problem first: what has lapsed, then what is about to, then the rest.
_RANK = {'expired': 0, 'soon': 1, 'valid': 2, 'none': 3, 'renewed': 4}


class PbTrainingCertificates(models.AbstractModel):
    _inherit = 'pb.training'

    _VERBS = PbTrainingClaims._VERBS + (
        'add_certificate', 'verify_certificate', 'assign_refresher',
    )

    # =====================================================================
    #  the rows
    # =====================================================================
    @api.model
    def _cert_docs(self):
        """Every certificate and licence in the reader's companies."""
        if 'pb.employee.document' not in self.env:
            return self.env['res.partner'].browse()
        return self.env['pb.employee.document'].sudo().search([
            ('training_source', '!=', False),
            ('company_id', 'in', self.env.companies.ids),
            ('employee_id.active', '=', True),
        ])

    @api.model
    def _cert_bucket(self, doc, today):
        """Which tiles a row counts towards (they overlap on purpose: 30 is
        inside 60, which is inside 90; Valid is everything still in date)."""
        out = set()
        if doc.renewed_by_id:
            return {'renewed'}
        if not doc.expiry_date:
            return {'no_expiry'}
        if doc.expiry_date < today:
            return {'expired'}
        out.add('valid')
        left = (doc.expiry_date - today).days
        for days in (30, 60, 90):
            if left <= days:
                out.add('expiring_%s' % days)
        return out

    @api.model
    def _cert_counts(self, docs=None):
        today = fields.Date.today()
        docs = self._cert_docs() if docs is None else docs
        counts = {k: 0 for k in TILE_KEYS + ('renewed',)}
        live = 0
        for doc in docs:
            buckets = self._cert_bucket(doc, today)
            for key in buckets:
                counts[key] = counts.get(key, 0) + 1
            if 'renewed' not in buckets:
                live += 1
        counts['total'] = live
        return counts

    # =====================================================================
    #  the register
    # =====================================================================
    @api.model
    def certificates_board(self, filters=None):
        if not self._can_read():
            return {'allowed': False, 'rows': [], 'tiles': []}
        filters = filters or {}
        today = fields.Date.today()
        docs = self._safe(self._cert_docs, default=self.env['res.partner'])
        counts = self._safe(lambda: self._cert_counts(docs), default={})
        state = filters.get('state') or ''
        dept = as_id(filters.get('department_id'))
        job = as_id(filters.get('job_id'))
        needle = fold(filters.get('q') or '')
        if dept:
            allowed = set(self.env['hr.department'].sudo().search(
                [('id', 'child_of', dept)]).ids)
        rows = []
        departments, jobs = {}, {}
        for doc in docs:
            emp = doc.employee_id.sudo()
            if emp.department_id:
                departments[emp.department_id.id] = emp.department_id.name
            if emp.job_id:
                jobs[emp.job_id.id] = emp.job_id.name
            buckets = self._cert_bucket(doc, today)
            if state and state not in buckets:
                continue
            if not state and 'renewed' in buckets:
                # Renewed rows are history; they show under their own chip.
                continue
            if dept and emp.department_id.id not in allowed:
                continue
            if job and emp.job_id.id != job:
                continue
            if needle and needle not in fold(emp.name) \
                    and needle not in fold(doc.name):
                continue
            rows.append(doc)
        rows.sort(key=lambda d: (_RANK.get(d.training_state, 5),
                                 d.expiry_date or fields.Date.to_date(
                                     '9999-12-31'),
                                 fold(d.employee_id.sudo().name)))
        total = len(rows)
        pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        page = min(max(int(filters.get('page') or 1), 1), pages)
        shown = rows[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'counts': counts,
            'headline': self._cert_headline(counts),
            'tiles': [{'key': k, 'count': counts.get(k, 0)}
                      for k in TILE_KEYS],
            'renewed': counts.get('renewed', 0),
            'rows': [d._pb_cert_payload() for d in shown],
            'total': total,
            'page': page,
            'pages': pages,
            'departments': sorted(
                [{'id': k, 'name': v} for k, v in departments.items()],
                key=lambda r: fold(r['name'])),
            'jobs': sorted([{'id': k, 'name': v} for k, v in jobs.items()],
                           key=lambda r: fold(r['name'])),
            'renew_before': self._renew_before(),
        }

    @api.model
    def _renew_before(self):
        from .training_common import P_RENEW_BEFORE
        return number(self.env, P_RENEW_BEFORE, 60)

    @api.model
    def _cert_headline(self, counts):
        """"214 certificates. 12 expire within 30 days, 3 have expired." —
        whole sentences, chosen for their counts (R117)."""
        total = counts.get('total', 0)
        soon = counts.get('expiring_30', 0)
        gone = counts.get('expired', 0)
        if not total:
            return _("No certificates yet.")
        first = _("1 certificate.") if total == 1 \
            else _("%s certificates.", total)
        if soon and gone:
            if soon == 1 and gone == 1:
                second = _("1 expires within 30 days, 1 has expired.")
            elif soon == 1:
                second = _("1 expires within 30 days, %s have expired.", gone)
            elif gone == 1:
                second = _("%s expire within 30 days, 1 has expired.", soon)
            else:
                second = _("%(soon)s expire within 30 days, %(gone)s have "
                           "expired.", soon=soon, gone=gone)
        elif soon:
            second = _("1 expires within 30 days.") if soon == 1 \
                else _("%s expire within 30 days.", soon)
        elif gone:
            second = _("1 has expired.") if gone == 1 \
                else _("%s have expired.", gone)
        else:
            second = _("Nothing expires within 30 days.")
        return '%s %s' % (first, second)

    # =====================================================================
    #  the people picker (everybody, login or not)
    # =====================================================================
    @api.model
    def certificate_people(self, term=''):
        """Accent-blind, company-scoped, capped. Unlike the course picker it
        offers people WITHOUT a login too: a forklift licence belongs to the
        person whether or not they ever sign in."""
        self._require_read()
        needle = fold(term or '')
        rows = self.env['hr.employee'].sudo().search_read(
            [('company_id', 'in', self.env.companies.ids),
             ('active', '=', True)],
            ['name', 'department_id', 'job_title'])
        cap = number(self.env, P_PEOPLE_LIMIT)
        out = []
        for row in rows:
            if needle and needle not in fold(row['name']):
                continue
            out.append({
                'id': row['id'],
                'name': row['name'],
                'department': row['department_id'][1]
                if row.get('department_id') else '',
                'job': row.get('job_title') or '',
            })
        out.sort(key=lambda r: fold(r['name']))
        return out[:cap]

    # =====================================================================
    #  the verbs
    # =====================================================================
    @api.model
    def _cert_doc(self, document_id):
        doc = self.env['pb.employee.document'].sudo().browse(
            as_id(document_id)).exists()
        if not doc or not doc.training_source \
                or doc.company_id.id not in self.env.companies.ids:
            raise UserError(_("That certificate is not here any more."))
        return doc

    @api.model
    def add_certificate(self, payload=None):
        """HR files a certificate or licence for anybody in their companies.

        Verified on the spot — HR is the one looking at it — through the
        vault's own path (`_pb_training_verify`), never a direct write.
        """
        self._require_write()
        payload = payload or {}
        emp = self.env['hr.employee'].sudo().browse(
            as_id(payload.get('employee_id'))).exists()
        if not emp or emp.company_id.id not in self.env.companies.ids:
            raise UserError(_("Pick the person the certificate belongs to."))
        source = payload.get('source') or 'upload'
        if source not in ('upload', 'statutory'):
            source = 'upload'
        upload = None
        if payload.get('file_b64'):
            try:
                upload = (payload.get('file_name') or '',
                          base64.b64decode(payload['file_b64']))
            except (binascii.Error, ValueError, TypeError):
                raise UserError(_("That file could not be read. Try "
                                  "attaching it again."))
        doc = self.env['pb.training.certificate']._create_upload(
            emp, payload, upload, source)
        doc._pb_training_verify()
        return {'id': doc.id,
                'message': _("%(name)s is on %(who)s's record.",
                             name=doc.name, who=emp.name or '')}

    @api.model
    def verify_certificate(self, document_id):
        self._require_write()
        doc = self._cert_doc(document_id)
        doc._pb_training_verify()
        return {'message': _("%s is marked as checked.", doc.name)}

    @api.model
    def assign_refresher(self, document_id):
        """Put the person on the certificate's course again, now."""
        self._require_write()
        doc = self._cert_doc(document_id)
        return self.env['pb.training.automation']._assign_renewal(
            doc, raise_on_clash=True)

    @api.model
    def act(self, verb, payload=None):
        payload = payload or {}
        if verb == 'add_certificate':
            return self.add_certificate(payload)
        if verb == 'verify_certificate':
            return self.verify_certificate(payload.get('document_id'))
        if verb == 'assign_refresher':
            return self.assign_refresher(payload.get('document_id'))
        return super().act(verb, payload)

    # =====================================================================
    #  what the Overview and the Numbers read
    # =====================================================================
    @api.model
    def _cert_overview(self):
        counts = self._cert_counts()
        return {k: counts.get(k, 0)
                for k in ('expiring_30', 'expired', 'valid', 'no_expiry',
                          'total')}

    @api.model
    def _renewals_open(self):
        return self.env['pb.training.assignment'].sudo().search_count([
            ('company_id', 'in', self.env.companies.ids),
            ('reason', '=', 'renewal'),
            ('state', 'in', ASSIGN_OPEN),
        ])

    @api.model
    def _cert_window(self, days):
        today = fields.Date.today()
        return today, today + timedelta(days=days)
