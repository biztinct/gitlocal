"""DocuSign contract and safety tests: no real uploads or invitations."""
import base64
import hashlib
import hmac
import json
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .test_offer import OfferCase
from ..services import docusign as ds
from ..services.connection_crypto import encrypt


@tagged('post_install', '-at_install', 'recruit_connect')
class TestDocuSign(OfferCase):
    def _connection(self):
        conn = self.env['pb.hiring.connection']._for_company('docusign', self.company)
        if not conn:
            conn = self.env['pb.hiring.connection'].create({'provider': 'docusign'})
        conn.write({'enabled': True, 'check_ok': True,
            'settings': {'environment': 'demo', 'client_id': 'client', 'user_id': 'sender', 'account_id': 'account'},
            'credentials': encrypt(self.env, json.dumps({'hmac_key': 'test-hmac'}))})
        return conn

    def _ready_offer(self):
        offer = self._offer()
        conn = self._connection()
        raw = b'%PDF-1.4\nTest offer\n%%EOF'
        attachment = self.env['ir.attachment'].create({'name': 'test.pdf', 'raw': raw,
            'res_model': offer._name, 'res_id': offer.id, 'mimetype': 'application/pdf'})
        offer.write({'state': 'sent', 'attachment_id': attachment.id})
        return offer, conn, raw

    def _envelope_offer(self):
        offer, conn, raw = self._ready_offer()
        offer.write({'pb_envelope_id': 'envelope', 'pb_sign_connection_id': conn.id,
                     'pb_sign_hash': hashlib.sha256(raw).hexdigest(), 'pb_sign_status': 'draft'})
        return offer, conn

    def _document(self, offer, status='created'):
        return {'envelopeId': 'envelope', 'status': status,
            'customFields': {'textCustomFields': [
                {'name': 'payobook_reference', 'value': offer._sign_reference()},
                {'name': 'payobook_pdf_sha256', 'value': offer.pb_sign_hash}]},
            'recipients': {'signers': [{'recipientId': '1', 'email': offer.candidate_email,
                'routingOrder': '1', 'status': 'completed' if status == 'completed' else 'created',
                'tabs': {'signHereTabs': [{'documentId': '1', 'optional': 'false'}]}}]},
            'envelopeDocuments': [{'documentId': '1', 'type': 'content'}]}

    def test_jwt_signature_and_auth_host(self):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode()
        token = ds.jwt_assertion('client', 'sender', 'demo', pem)
        header, payload, signature = token.split('.')
        decode = lambda s: base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))
        private.public_key().verify(decode(signature), (header + '.' + payload).encode(),
                                    padding.PKCS1v15(), hashes.SHA256())
        claims = json.loads(decode(payload))
        self.assertEqual(claims['aud'], 'account-d.docusign.com')
        self.assertEqual(claims['scope'], 'signature impersonation')
        self.assertEqual(claims['exp'] - claims['iat'], 3600)
        with self.assertRaises(UserError): ds.jwt_assertion('c', 'u', 'demo', 'bad key')

    def test_only_verified_docusign_hosts_receive_token(self):
        self.assertEqual(ds.api_base('https://demo.docusign.net', 'demo'), 'https://demo.docusign.net/restapi/v2.1')
        for value in ['https://demo.docusign.net.evil.invalid', 'http://demo.docusign.net',
                      'https://user@demo.docusign.net', 'https://demo.docusign.net/path', 'https://na4.docusign.net']:
            with self.assertRaises(UserError): ds.api_base(value, 'demo')
        with self.assertRaises(UserError): ds.auth_host('arbitrary.invalid')

    def test_auth_checks_account_and_caches_encrypted_token(self):
        conn = self._connection()
        responses = [Mock(json=lambda: {'access_token': 'sensitive-token', 'expires_in': 3600}),
                     Mock(json=lambda: {'sub': 'sender', 'accounts': [{'account_id': 'account', 'base_uri': 'https://demo.docusign.net'}]})]
        with patch.object(ds, 'jwt_assertion', return_value='assertion'), patch.object(ds, 'request', side_effect=responses) as send:
            token, base = conn._ds_auth()
            self.assertEqual(token, 'sensitive-token')
            self.assertEqual(conn._ds_auth(), (token, base))
            self.assertEqual(send.call_count, 2)
        self.assertNotIn('sensitive-token', conn.credentials)
        self.assertNotIn('sensitive-token', str(conn._card()))
        responses[1] = Mock(json=lambda: {'sub': 'sender', 'accounts': [{'account_id': 'other', 'base_uri': 'https://demo.docusign.net'}]})
        with patch.object(ds, 'jwt_assertion', return_value='assertion'), patch.object(ds, 'request', side_effect=responses):
            with self.assertRaises(UserError): conn._ds_auth(force=True)

    def test_draft_only_and_recover_after_lost_response(self):
        offer, conn, raw = self._ready_offer()
        self.env['ir.config_parameter'].sudo().set_param('web.base.url', 'https://payobook.example.invalid')
        with patch.object(type(offer.requisition_id), '_offer_block_reason', return_value=False), \
                patch.object(type(conn), '_ds_http', side_effect=[Mock(json=lambda: {'envelopes': []}),
                Mock(json=lambda: {'envelopeId': 'envelope'})]) as call:
            action = offer.action_prepare_esign()
        payload = call.call_args.kwargs['json']
        self.assertEqual(payload['status'], 'created')
        self.assertEqual(payload['transactionId'], offer._sign_reference())
        self.assertEqual(base64.b64decode(payload['documents'][0]['documentBase64']), raw)
        self.assertEqual(payload['eventNotification']['includeHMAC'], 'true')
        self.assertEqual(action['url'], 'https://apps-d.docusign.com/send/home')
        doc = self._document(offer)
        offer.write({'pb_envelope_id': False, 'pb_sign_status': False})
        with patch.object(type(offer.requisition_id), '_offer_block_reason', return_value=False), \
                patch.object(type(conn), '_ds_http', return_value=Mock(json=lambda: {'envelopes': [doc]})) as call:
            offer.action_prepare_esign()
            self.assertEqual(call.call_count, 1)
        self.assertEqual(offer.pb_envelope_id, 'envelope')

    def test_prepare_requires_approval_before_any_upload(self):
        offer, conn, raw = self._ready_offer()
        with patch.object(type(offer.requisition_id), '_offer_block_reason', return_value='Approval required'), \
                patch.object(type(conn), '_ds_http') as send:
            with self.assertRaises(UserError): offer.action_prepare_esign()
            send.assert_not_called()

    def test_send_requires_review_matching_signers_and_required_tabs(self):
        offer, conn = self._envelope_offer()
        doc = self._document(offer)
        with patch.object(type(offer.requisition_id), '_offer_block_reason', return_value=False), \
                patch.object(type(conn), '_ds_http', return_value=Mock(json=lambda: doc)) as call:
            with self.assertRaises(UserError): offer.action_send_esign()
            call.assert_not_called()
            offer.pb_sign_reviewed = True
            doc['recipients']['signers'][0]['tabs']['signHereTabs'][0]['optional'] = 'true'
            with self.assertRaises(UserError): offer.action_send_esign()
            self.assertFalse(any(c.args[0] == 'PUT' for c in call.call_args_list))
            doc['recipients']['signers'][0]['tabs']['signHereTabs'][0]['optional'] = 'false'
            offer.action_send_esign()
            self.assertEqual(call.call_args.args[:2], ('PUT', '/envelopes/envelope'))
            self.assertEqual(call.call_args.kwargs['json'], {'status': 'sent'})
        self.assertEqual(offer.pb_sign_status, 'pending')

    def test_wrong_recipient_order_extra_cc_document_or_reference_rejected(self):
        offer, conn = self._envelope_offer()
        for mutate in [lambda d: d['recipients']['signers'][0].update(email='outsider@example.com'),
                       lambda d: d['recipients']['signers'][0].update(routingOrder='2'),
                       lambda d: d['recipients'].update(carbonCopies=[{'email': 'outsider@example.com'}]),
                       lambda d: d.update(envelopeDocuments=[]),
                       lambda d: d['customFields']['textCustomFields'][1].update(value='wrong')]:
            doc = self._document(offer)
            mutate(doc)
            with patch.object(type(conn), '_ds_http', return_value=Mock(json=lambda: doc)):
                with self.assertRaises(UserError): offer._envelope()
        doc = self._document(offer)
        doc['customFields']['textCustomFields'][0]['value'] = 'different-offer'
        with patch.object(type(conn), '_ds_http', return_value=Mock(json=lambda: doc)):
            with self.assertRaises(UserError): offer.action_sync_esign()

    def test_completion_files_combined_certificate_once_without_joining(self):
        offer, conn = self._envelope_offer()
        doc = self._document(offer, 'completed')
        with patch.object(type(conn), '_ds_http', return_value=Mock(json=lambda: doc, content=b'%PDF-signed-with-certificate')) as call:
            offer.action_sync_esign()
            attachment = offer.signed_attachment_id
            self.assertEqual(attachment.raw, b'%PDF-signed-with-certificate')
            self.assertEqual(call.call_args.args[:2], ('GET', '/envelopes/envelope/documents/combined'))
            self.assertEqual(call.call_args.kwargs['params'], {'certificate': 'true'})
            offer.action_sync_esign()
            self.assertEqual(offer.signed_attachment_id, attachment)
            self.assertEqual(sum('/documents/combined' in c.args[1] for c in call.call_args_list), 1)
        self.assertEqual(offer.state, 'signed')
        self.assertFalse(offer.employee_id)

    def test_unsigned_completion_or_non_pdf_never_files(self):
        offer, conn = self._envelope_offer()
        doc = self._document(offer, 'completed')
        doc['recipients']['signers'][0]['status'] = 'sent'
        with patch.object(type(conn), '_ds_http', return_value=Mock(json=lambda: doc)) as call:
            with self.assertRaises(UserError): offer.action_sync_esign()
            self.assertEqual(call.call_count, 1)
        doc['recipients']['signers'][0]['status'] = 'completed'
        with patch.object(type(conn), '_ds_http', return_value=Mock(json=lambda: doc, content=b'not PDF')):
            with self.assertRaises(UserError): offer.action_sync_esign()
        self.assertFalse(offer.signed_attachment_id)

    def test_cancel_draft_and_void_pending_keep_audit(self):
        offer, conn = self._envelope_offer()
        for status in ['created', 'sent']:
            doc = self._document(offer, status)
            with patch.object(type(conn), '_ds_http', return_value=Mock(json=lambda: doc)) as call:
                offer.action_cancel_esign()
                self.assertEqual(call.call_args.args[1], '/folders/recyclebin' if status == 'created' else '/envelopes/envelope')
            self.assertEqual(offer.pb_sign_status, 'cancelled')
            self.assertEqual(offer.pb_envelope_id, 'envelope')

    def test_hmac_rejects_tampering_and_queues_only_same_account(self):
        offer, conn = self._envelope_offer()
        data = {'event': 'envelope-completed', 'data': {'accountId': 'account', 'envelopeId': 'envelope'}}
        raw = json.dumps(data).encode()
        signature = base64.b64encode(hmac.new(b'test-hmac', raw, hashlib.sha256).digest()).decode()
        self.assertTrue(ds.valid_hmac('test-hmac', raw, ['', signature]))
        self.assertFalse(ds.valid_hmac('test-hmac', raw + b' ', [signature]))
        self.assertFalse(ds.valid_hmac('', raw, [signature]))
        self.assertFalse(ds.valid_hmac('test-hmac', raw, ['invalid\u00e9']))
        data['data']['accountId'] = 'other'
        conn._ds_receive(data)
        self.assertFalse(offer.pb_sign_refresh_requested)
        data['data']['accountId'] = 'account'
        conn._ds_receive(data)
        self.assertTrue(offer.pb_sign_refresh_requested)
        self.assertFalse(offer.signed_attachment_id)

    def test_active_account_cannot_switch_and_incomplete_setup_cannot_enable(self):
        offer, conn = self._envelope_offer()
        with self.assertRaises(UserError):
            self.env['pb.hiring'].connection_save('docusign', {'account_id': 'other'})
        with self.assertRaises(ValidationError):
            self.env['pb.hiring'].connection_save('docusign', {'environment': 'unknown'})
        card = self.env['pb.hiring'].connection_save('docusign', {})
        self.assertFalse(card['enabled'])
        result = self.env['pb.hiring'].connection_check('docusign')
        self.assertFalse(result['check_ok'])
        self.assertIn('RSA private key', result['note'])
