"""Company-bound DocuSign authentication and envelope lifecycle."""
import base64
import hashlib
import json
import time
from datetime import timedelta
from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services import docusign as ds
from ..services.connection_crypto import encrypt, decrypt


class DocuSignConnection(models.Model):
    _inherit = 'pb.hiring.connection'

    def _ds_auth(self, force=False):
        self.ensure_one()
        cfg = self._config()
        secrets = json.loads(decrypt(self.env, self.sudo().credentials))
        environment = cfg.get('environment', '')
        host = ds.auth_host(environment)
        if not force and secrets.get('access_token') and secrets.get('expires_at', 0) > time.time() + 120:
            return secrets['access_token'], ds.api_base(secrets['base_uri'], environment)
        assertion = ds.jwt_assertion(cfg.get('client_id'), cfg.get('user_id'), environment, secrets.get('private_key', ''))
        token = ds.request('POST', 'https://' + host + '/oauth/token',
            data={'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'assertion': assertion}).json()
        access = token.get('access_token')
        if not isinstance(access, str) or not access:
            raise UserError(_('DocuSign did not return an access token.'))
        info = ds.request('GET', 'https://' + host + '/oauth/userinfo',
                          headers={'Authorization': 'Bearer ' + access}).json()
        accounts = [a for a in info.get('accounts', []) if a.get('account_id') == cfg.get('account_id')]
        if len(accounts) != 1 or info.get('sub', '').lower() != cfg.get('user_id', '').lower():
            raise UserError(_('The DocuSign user does not have access to the configured account.'))
        base = ds.api_base(accounts[0].get('base_uri', ''), environment)
        secrets.update(access_token=access, base_uri=accounts[0]['base_uri'],
                       expires_at=time.time() + min(int(token.get('expires_in', 3600)), 3600))
        self.sudo().write({'credentials': encrypt(self.env, json.dumps(secrets))})
        return access, base

    def _ds_http(self, method, path, **kwargs):
        token, base = self._ds_auth()
        account = quote(self._config()['account_id'], safe='')
        return ds.request(method, base + '/accounts/' + account + path,
                          headers={'Authorization': 'Bearer ' + token}, **kwargs)

    def _check_docusign(self):
        self._ds_auth(force=True)
        self._ds_http('GET', '/envelopes', params={'from_date': fields.Date.today().isoformat(), 'count': 1})
        return _('DocuSign account and API access verified. Enable, then test a draft, signatures and signed-PDF filing with approved test recipients. Webhook delivery still needs that test.')

    def _ds_callback(self):
        return self._card()['callback']

    def _ds_receive(self, data):
        payload = data.get('data')
        if not isinstance(payload, dict) or str(payload.get('accountId', '')) != self._config().get('account_id'):
            return
        envelope_id = payload.get('envelopeId')
        if not isinstance(envelope_id, str):
            return
        offers = self.env['pb.hiring.offer'].sudo().search([
            ('company_id', '=', self.company_id.id), ('pb_sign_connection_id', '=', self.id),
            ('pb_envelope_id', '=', envelope_id), ('pb_sign_status', 'in', ['draft', 'pending'])])
        # A webhook is a wake-up signal only. The authenticated API supplies
        # status, recipient evidence and documents; replay cannot sign an offer.
        offers.write({'pb_sign_refresh_requested': True,
                      'pb_sign_note': _('DocuSign update received; verification queued.')})


class DocuSignSetup(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def connection_save(self, provider, values):
        self._require_write()
        if provider == 'docusign' and isinstance(values, dict):
            row = self.env['pb.hiring.connection']._for_company(provider, self.env.company)
            cfg = row._config() if row else {}
            environment = values.get('environment', cfg.get('environment', ''))
            if environment and environment not in ('demo', 'production'):
                raise ValidationError(_('Select demo or production for DocuSign.'))
            changed = any(k in values and str(values[k] or '').strip() != cfg.get(k, '')
                          for k in ('environment', 'account_id', 'user_id', 'client_id'))
            if changed and row and self.env['pb.hiring.offer'].sudo().search_count([
                    ('pb_sign_connection_id', '=', row.id), ('pb_sign_status', 'in', ['draft', 'pending'])]):
                raise UserError(_('Finish or cancel active DocuSign envelopes before changing the account, sender or environment.'))
        result = super().connection_save(provider, values)
        if provider == 'docusign':
            row = self.env['pb.hiring.connection']._for_company(provider, self.env.company)
            secrets = json.loads(decrypt(self.env, row.credentials))
            for key in ('access_token', 'expires_at', 'base_uri'):
                secrets.pop(key, None)
            row.write({'credentials': encrypt(self.env, json.dumps(secrets))})
        return result


class DocuSignOffer(models.Model):
    _inherit = 'pb.hiring.offer'

    pb_sign_refresh_requested = fields.Boolean(readonly=True, copy=False)

    def action_prepare_esign(self):
        self._sign_gate()
        self._sign_lock()
        if self.pb_envelope_id:
            return self.action_open_esign()
        if self.state not in ('hr_ok', 'sent', 'accepted'):
            raise UserError(_('Complete offer sign-off before preparing a signature request.'))
        why = self.requisition_id.sudo()._offer_block_reason()
        if why:
            raise UserError(why)
        conn = self.env['pb.hiring.connection']._for_company('docusign', self.company_id)
        if not conn:
            raise UserError(_('Set up DocuSign in Hiring connections first.'))
        conn._ready()
        if not self.attachment_id:
            self.action_prepare_letter()
        raw = self.attachment_id.sudo().raw
        if not raw or not raw.startswith(b'%PDF') or len(raw) > 10 * 1024 * 1024:
            raise UserError(_('Prepare a PDF offer letter no larger than 10 MB first.'))
        reference = self._sign_reference()
        # Persistent metadata search complements the provider transaction ID,
        # whose de-duplication window is only seven days.
        existing = conn._ds_http('GET', '/envelopes', params={
            'custom_field': 'payobook_reference=' + reference,
            'from_date': (self.create_date - timedelta(days=1)).isoformat() + 'Z',
            'include': 'custom_fields', 'count': 100}).json()
        matches = [d for d in existing.get('envelopes', []) if self._ds_reference(d) == reference]
        if len(matches) > 1 or existing.get('nextUri'):
            raise UserError(_('Reconcile matching DocuSign envelopes before preparing another draft.'))
        digest = hashlib.sha256(raw).hexdigest()
        if matches:
            envelope_id = matches[0]['envelopeId']
            # Do not associate a recovered envelope with a subsequently changed PDF.
            if self._ds_custom(matches[0]).get('payobook_pdf_sha256') != digest:
                raise UserError(_('A DocuSign envelope already exists for a different PDF. Reconcile it in DocuSign before continuing.'))
        else:
            signers = [{'recipientId': str(i), 'name': r['name'], 'email': r['email'],
                        'routingOrder': str(i)} for i, r in enumerate(self._sign_recipients(), 1)]
            callback = conn._ds_callback()
            if not callback.startswith('https://'):
                raise UserError(_('Configure the company public HTTPS address before preparing DocuSign envelopes.'))
            payload = {'emailSubject': ('Offer ' + self.name + ' ' + reference)[:100],
                'status': 'created', 'transactionId': reference,
                'documents': [{'documentId': '1', 'name': 'Offer letter', 'fileExtension': 'pdf',
                               'documentBase64': base64.b64encode(raw).decode()}],
                'recipients': {'signers': signers},
                'customFields': {'textCustomFields': [
                    {'name': 'payobook_reference', 'value': reference, 'show': 'false'},
                    {'name': 'payobook_pdf_sha256', 'value': digest, 'show': 'false'}]},
                'eventNotification': {'url': callback, 'requireAcknowledgment': 'true',
                    'includeHMAC': 'true', 'deliveryMode': 'SIM',
                    'events': ['envelope-sent', 'envelope-delivered', 'envelope-completed',
                               'envelope-declined', 'envelope-voided'],
                    'eventData': {'version': 'restv2.1', 'format': 'json', 'includeData': []}}}
            envelope_id = conn._ds_http('POST', '/envelopes', json=payload).json().get('envelopeId')
        if not isinstance(envelope_id, str) or not envelope_id:
            raise UserError(_('DocuSign did not return an envelope identifier.'))
        self.sudo().write({'pb_envelope_id': envelope_id, 'pb_sign_connection_id': conn.id,
            'pb_sign_status': 'draft', 'pb_sign_hash': digest, 'pb_sign_reviewed': False,
            'pb_sign_note': _('Draft prepared in DocuSign. Find the offer reference, place signature fields and review it. Send from Payobook after review.')})
        self.message_post(body=_('DocuSign envelope prepared: %s. This action does not send invitations.', envelope_id))
        return self.action_open_esign()

    @staticmethod
    def _ds_custom(document):
        return {f.get('name'): f.get('value') for f in document.get('customFields', {}).get('textCustomFields', [])}

    def _ds_reference(self, document):
        return self._ds_custom(document).get('payobook_reference')

    def action_open_esign(self):
        self._sign_gate()
        conn = self.pb_sign_connection_id.sudo()
        if conn.provider != 'docusign':
            return super().action_open_esign()
        host = 'apps-d.docusign.com' if conn._config().get('environment') == 'demo' else 'apps.docusign.com'
        return {'type': 'ir.actions.act_url', 'url': 'https://' + host + '/send/home', 'target': 'new'}

    def _envelope(self):
        self.ensure_one()
        conn = self.pb_sign_connection_id.sudo()
        if conn.provider != 'docusign':
            return super()._envelope()
        doc = conn._ds_http('GET', '/envelopes/' + quote(self.pb_envelope_id, safe=''),
            params={'include': 'recipients,tabs,custom_fields,documents'}).json()
        if self._ds_custom(doc).get('payobook_pdf_sha256') != self.pb_sign_hash:
            raise UserError(_('The DocuSign document reference does not match the prepared offer.'))
        recipients = doc.get('recipients', {})
        # Extra recipients could disclose a confidential offer. Fail closed,
        # including agents, editors and carbon copies added in the provider UI.
        if any(v for k, v in recipients.items() if isinstance(v, list) and k != 'signers'):
            raise UserError(_('Remove unexpected recipient types from the DocuSign envelope.'))
        signers, tabs = [], []
        for r in recipients.get('signers', []):
            signers.append({'id': r.get('recipientId'), 'email': r.get('email', ''),
                'role': 'SIGNER', 'signingOrder': r.get('routingOrder'),
                'signingStatus': 'SIGNED' if r.get('status') == 'completed' else 'UNSIGNED'})
            for tab in r.get('tabs', {}).get('signHereTabs', []):
                if str(tab.get('optional', 'false')).lower() != 'true':
                    tabs.append({'recipientId': r.get('recipientId'), 'type': 'SIGNATURE'})
        status = {'created': 'draft', 'sent': 'pending', 'delivered': 'pending',
                  'completed': 'completed', 'declined': 'rejected', 'voided': 'cancelled',
                  'deleted': 'cancelled'}.get(doc.get('status'))
        if not status:
            raise UserError(_('DocuSign status requires review in DocuSign before continuing.'))
        expected = {r['email'].lower(): str(r['signingOrder']) for r in self._sign_recipients()}
        if (len(signers) != len(expected) or
                {r['email'].lower(): str(r['signingOrder']) for r in signers} != expected):
            raise UserError(_('DocuSign signers or signing order do not match this offer.'))
        items = [d for d in doc.get('envelopeDocuments', []) if d.get('type') == 'content']
        if len(items) != 1 or str(items[0].get('documentId')) != '1':
            raise UserError(_('This offer expects its single original document in DocuSign.'))
        return {'id': doc.get('envelopeId'), 'externalId': self._ds_reference(doc), 'status': status,
                'recipients': signers, 'fields': tabs,
                'envelopeItems': [{'id': '1'}]}

    def _distribute_esign(self):
        if self.pb_sign_connection_id.provider != 'docusign':
            return super()._distribute_esign()
        return self.pb_sign_connection_id._ds_http('PUT', '/envelopes/' + quote(self.pb_envelope_id, safe=''), json={'status': 'sent'})

    def _signed_esign_pdf(self, document):
        if self.pb_sign_connection_id.provider != 'docusign':
            return super()._signed_esign_pdf(document)
        return self.pb_sign_connection_id._ds_http('GET', '/envelopes/' + quote(self.pb_envelope_id, safe='')
            + '/documents/combined', params={'certificate': 'true'}).content

    def _cancel_esign_provider(self):
        conn = self.pb_sign_connection_id
        if conn.provider != 'docusign':
            return super()._cancel_esign_provider()
        if self.pb_sign_status == 'draft':
            return conn._ds_http('PUT', '/folders/recyclebin', json={'envelopeIds': [self.pb_envelope_id]})
        return conn._ds_http('PUT', '/envelopes/' + quote(self.pb_envelope_id, safe=''),
                            json={'status': 'voided', 'voidedReason': 'Cancelled by the hiring team in Payobook.'})
