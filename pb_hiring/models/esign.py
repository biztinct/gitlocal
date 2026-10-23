"""Documenso envelope API. Completion is verified, then filed exactly once."""
import hashlib
import json
from urllib.parse import quote

from odoo import _, fields, models
from odoo.exceptions import UserError


class OfferSigning(models.Model):
    _inherit = 'pb.hiring.offer'

    pb_sign_connection_id = fields.Many2one('pb.hiring.connection', readonly=True, copy=False)
    pb_envelope_id = fields.Char(string='Documenso envelope', readonly=True, copy=False, index=True)
    pb_sign_status = fields.Selection([('draft', 'Draft in Documenso'), ('pending', 'Awaiting signatures'),
        ('completed', 'Signed copy filed'), ('rejected', 'Declined'), ('cancelled', 'Cancelled')], string='Signing status', readonly=True, copy=False)
    pb_sign_hash = fields.Char(readonly=True, copy=False)
    pb_company_signer_id = fields.Many2one('res.users', string='Company counter-signatory', domain="[('share', '=', False)]")
    pb_sign_reviewed = fields.Boolean(string='I reviewed the document, recipients and signature positions in Documenso', copy=False)
    pb_sign_checked_at = fields.Datetime(string='Last signing check', readonly=True, copy=False)
    pb_sign_note = fields.Char(string='Signing update', readonly=True, copy=False)
    pb_sign_attempt = fields.Integer(default=1, readonly=True, copy=False)

    def _sign_gate(self):
        self.ensure_one()
        self.check_access('write')
        self.env['pb.hiring']._require_recruit(self.requisition_id)

    def _sign_reference(self):
        db_uuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid') or self.env.cr.dbname
        return 'PB-' + hashlib.sha256(('%s:%s:%s:%s' % (db_uuid, self.company_id.id, self.id, self.pb_sign_attempt)).encode()).hexdigest()[:24]

    def _sign_lock(self):
        self.env.cr.execute('SELECT id FROM pb_hiring_offer WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset()

    def _sign_recipients(self):
        result = [{'name': self.candidate_name, 'email': self.candidate_email, 'role': 'SIGNER', 'signingOrder': 1}]
        if self.pb_company_signer_id:
            if self.company_id not in self.pb_company_signer_id.company_ids or not self.pb_company_signer_id.email:
                raise UserError(_('Choose a company signatory with an email address and access to this company.'))
            result.append({'name': self.pb_company_signer_id.name, 'email': self.pb_company_signer_id.email, 'role': 'SIGNER', 'signingOrder': 2})
        if any(not r['email'] for r in result):
            raise UserError(_('Every signer needs an email address.'))
        return result

    def action_prepare_esign(self):
        self._sign_gate()
        self._sign_lock()
        if self.pb_envelope_id:
            return self.action_open_esign()
        if self.state not in ('hr_ok', 'sent', 'accepted'):
            raise UserError(_('Complete offer sign-off before preparing a signature request.'))
        conn = self.env['pb.hiring.connection']._for_company('documenso', self.company_id)
        if not conn:
            raise UserError(_('Set up Offer signing in Hiring connections first.'))
        conn._ready()
        if not self.attachment_id:
            self.action_prepare_letter()
        raw = self.attachment_id.sudo().raw
        if not raw or not raw.startswith(b'%PDF'):
            raise UserError(_('Prepare a PDF offer letter first.'))
        reference = self._sign_reference()
        # Recover a draft created before a network interruption instead of
        # sending another request. The deterministic reference is in its title.
        existing = conn._http('GET', '/api/v2/envelope', params={'query': reference, 'perPage': 100}).json().get('data', [])
        existing = [d for d in existing if d.get('externalId') == reference]
        if len(existing) > 1:
            raise UserError(_('Several matching envelopes exist. Reconcile them in Documenso before continuing.'))
        if existing:
            envelope_id = existing[0]['id']
        else:
            payload = {'title': '%s %s' % (self.name, reference), 'type': 'DOCUMENT', 'externalId': reference,
                'visibility': 'ADMIN', 'recipients': self._sign_recipients(),
                'meta': {'signingOrder': 'SEQUENTIAL', 'distributionMethod': 'EMAIL', 'language': 'en'}}
            envelope_id = conn._http('POST', '/api/v2/envelope/create',
                data={'payload': json.dumps(payload)}, files={'files': ('offer.pdf', raw, 'application/pdf')}).json().get('id')
        if not envelope_id or not isinstance(envelope_id, str):
            raise UserError(_('Documenso did not return an envelope identifier.'))
        self.sudo().write({'pb_envelope_id': envelope_id, 'pb_sign_connection_id': conn.id,
            'pb_sign_status': 'draft', 'pb_sign_hash': hashlib.sha256(raw).hexdigest(), 'pb_sign_reviewed': False,
            'pb_sign_note': _('Draft prepared. Place and review the signature fields in Documenso, then send from this offer.')})
        self.message_post(body=_('Documenso draft prepared: %s. No signature invitation sent.', envelope_id))
        return self.action_open_esign()

    def action_open_esign(self):
        self._sign_gate()
        conn = self.pb_sign_connection_id.sudo()
        if not conn:
            raise UserError(_('Prepare the signing draft first.'))
        return {'type': 'ir.actions.act_url', 'url': conn._config()['url'], 'target': 'new'}

    def _envelope(self):
        self.ensure_one()
        return self.pb_sign_connection_id._http('GET', '/api/v2/envelope/' + quote(self.pb_envelope_id, safe='')).json()

    def action_send_esign(self):
        self._sign_gate()
        self._sign_lock()
        why = self.requisition_id.sudo()._offer_block_reason()
        if why:
            raise UserError(why)
        if self.state not in ('hr_ok', 'sent', 'accepted') or not self.pb_envelope_id:
            raise UserError(_('Prepare an agreed offer before sending.'))
        self.pb_sign_connection_id._ready()
        if not self.pb_sign_reviewed:
            raise UserError(_('Review the PDF, signers and signature positions in Documenso and tick the review box.'))
        raw = self.attachment_id.sudo().raw
        if not raw or hashlib.sha256(raw).hexdigest() != self.pb_sign_hash:
            raise UserError(_('The offer PDF changed after the signing draft was created. Reconcile the draft before sending.'))
        document = self._envelope()
        if document.get('externalId') != self._sign_reference():
            raise UserError(_('The envelope does not belong to this offer.'))
        if document.get('status') != 'DRAFT':
            self._sync_esign(document)
            return True
        expected = {r['email'].lower() for r in self._sign_recipients()}
        signers = [r for r in document.get('recipients', []) if r.get('role') == 'SIGNER']
        if {r['email'].lower() for r in signers} != expected or len(signers) != len(expected):
            raise UserError(_('Documenso signers do not match the offer. Correct the draft before sending.'))
        signature_ids = {f.get('recipientId') for f in document.get('fields', []) if f.get('type') in ('SIGNATURE','FREE_SIGNATURE')}
        if any(r['id'] not in signature_ids for r in signers):
            raise UserError(_('Place a signature field for every signer in Documenso.'))
        self.pb_sign_connection_id._http('POST', '/api/v2/envelope/distribute', json={'envelopeId': self.pb_envelope_id})
        self.sudo().write({'pb_sign_status': 'pending', 'state': 'sent', 'sent_on': fields.Datetime.now(),
                          'pb_sign_note': _('Signature invitation sent by Documenso.')})
        self.message_post(body=_('Signature invitation sent through Documenso.'))
        return True

    def action_sync_esign(self):
        self._sign_gate()
        if not self.pb_envelope_id:
            raise UserError(_('Prepare a signing draft first.'))
        return self._sync_esign(self._envelope())

    def _sync_esign(self, document):
        self.ensure_one()
        self.env.cr.execute('SELECT id FROM pb_hiring_offer WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        if document.get('id') != self.pb_envelope_id or document.get('externalId') != self._sign_reference():
            raise UserError(_('The signature response does not match this offer.'))
        status = document.get('status', '').lower()
        if status not in ('draft','pending','completed','rejected','cancelled'):
            raise UserError(_('Unrecognised signing status.'))
        if self.pb_sign_status == 'completed':
            return True
        if status == 'completed':
            expected = {r['email'].lower() for r in self._sign_recipients()}
            signers = [r for r in document.get('recipients', []) if r.get('role') == 'SIGNER']
            if {r['email'].lower() for r in signers} != expected or any(r.get('signingStatus') != 'SIGNED' for r in signers):
                raise UserError(_('The completed envelope does not contain all required signatures.'))
            items = document.get('envelopeItems', [])
            if len(items) != 1:
                raise UserError(_('This offer expects one signed PDF. Review the envelope documents.'))
            content = self.pb_sign_connection_id._http('GET', '/api/v2/envelope/item/' + quote(items[0]['id'], safe='') + '/download', params={'version': 'signed'}).content
            if not content.startswith(b'%PDF'):
                raise UserError(_('Documenso did not return a signed PDF.'))
            if self.state == 'hr_ok':
                self.sudo().write({'state': 'sent'})
            self.sudo().action_record_signed(filename='signed-offer.pdf', content=content, mimetype='application/pdf')
        elif status == 'rejected' and self.state in ('sent','accepted'):
            self.sudo().write({'candidate_decision': 'declined', 'state': 'declined', 'decided_on': fields.Datetime.now()})
            self._tell_recruiter_the_answer()
        self.sudo().write({'pb_sign_status': status, 'pb_sign_checked_at': fields.Datetime.now(),
                          'pb_sign_note': _('Provider status verified: %s', status)})
        return True

    def action_cancel_esign(self):
        self._sign_gate()
        self._sign_lock()
        document = self._envelope()
        self._sync_esign(document)
        if self.pb_sign_status not in ('draft', 'pending'):
            raise UserError(_('Only a draft or pending signature request can be cancelled here.'))
        endpoint = 'delete' if self.pb_sign_status == 'draft' else 'cancel'
        self.pb_sign_connection_id._http('POST', '/api/v2/envelope/' + endpoint, json={'envelopeId': self.pb_envelope_id})
        self.message_post(body=_('Signing envelope %s cancelled; its reference is retained in this history.', self.pb_envelope_id))
        self.sudo().write({'pb_sign_status': 'cancelled', 'pb_sign_note': _('Signature request cancelled.')})
        return True

    def action_restart_esign(self):
        self._sign_gate()
        self._sign_lock()
        if self.pb_sign_status != 'cancelled':
            raise UserError(_('Cancel the existing request before preparing another. Declined offers need a new offer revision.'))
        self.sudo().write({'pb_envelope_id': False, 'pb_sign_connection_id': False,
            'pb_sign_status': False, 'pb_sign_hash': False, 'pb_sign_reviewed': False,
            'pb_sign_attempt': self.pb_sign_attempt + 1})
        return True

    def _check_signing_edit(self):
        if any(r.pb_envelope_id and r.pb_sign_status in ('draft', 'pending', 'completed') for r in self):
            raise UserError(_('Cancel the active signature request before changing this offer. Signed offers require a new revision.'))

    def write(self, vals):
        if set(vals) & {'job_title','start_date','location','reporting_manager_id','line_ids','letter_template_id','pb_company_signer_id'}:
            self._check_signing_edit()
        return super().write(vals)
