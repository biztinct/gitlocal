# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Generic document field-extraction service + retry job (Phase D §3.2).

Product-neutral: it knows nothing about banks. A consumer passes a field schema
and attachment ids, the service resolves a purposed AI provider (doc_ocr) from
pb_payroll_ai_insights, runs its vision method, and returns a normalized result.
A deterministic post-processor callable always runs last — it is the no-AI
fallback / normalization layer (C1 doctrine: every AI path degrades gracefully).
"""

import json
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class BizDocOcr(models.AbstractModel):
    _name = 'biz.doc.ocr'
    _description = 'Document OCR Service'

    # ------------------------------------------------------------- service
    @api.model
    def _extract(self, schema, attachment_ids, post_processor=None):
        """Extract fields from document images per a schema.

        Underscore-PRIVATE on purpose: this sudo-reads the given attachments and
        returns their content to the caller — as a public method it would be an
        arbitrary-attachment exfiltration endpoint over call_kw. Python-only
        (C18.24/25); consumers gate access on their own record before calling.

        schema = {'fields': [{'name','label','type':'char|digits|code','hint'}],
                  'doc_kinds': [...]}
        Returns {'fields': {name: {'value','confidence'}}, 'doc_kind',
                 'raw_text', 'provider', 'error'}.

        ``post_processor(result_dict) -> result_dict`` (optional) runs LAST, even
        when there is no provider — it is where a deterministic layer parses OCR
        prose / normalizes / validates.
        """
        fields_spec = (schema or {}).get('fields', [])
        doc_kinds = (schema or {}).get('doc_kinds', [])
        result = {'fields': {}, 'doc_kind': False, 'raw_text': '',
                  'provider': 'none', 'error': False}

        config = self.env['payroll.ai.config'].get_config_for_purpose('doc_ocr')
        provider = None
        if config:
            try:
                provider = config.get_provider()
            except Exception as e:  # guarded-import / config failure
                result['error'] = str(e)

        # No provider (or no vision) → degrade to the deterministic layer only.
        if not provider or not provider.supports_vision():
            if not result['error']:
                result['error'] = (_("No document-OCR provider configured.")
                                   if not provider
                                   else _("The configured provider cannot read documents."))
            return self._finish(result, post_processor)

        result['provider'] = config.provider_type
        images, err = self._collect_images(attachment_ids, provider)
        if err:
            result['error'] = err
            return self._finish(result, post_processor)
        if not images:
            result['error'] = _("No document to read.")
            return self._finish(result, post_processor)

        prompt = self._build_prompt(fields_spec, doc_kinds)
        try:
            raw = provider.generate_vision(
                prompt, images, max_tokens=(config.max_tokens or 1500))
        except Exception as e:
            _logger.warning("biz.doc.ocr: vision call failed: %s", e)
            result['error'] = str(e)
            return self._finish(result, post_processor)

        result['raw_text'] = raw or ''
        # Tesseract returns PROSE — leave fields for the post-processor. Every
        # other vision provider is asked for strict JSON.
        if config.provider_type != 'tesseract':
            try:
                parsed = provider._parse_json_response(raw)
            except Exception:
                parsed = {}
                result['error'] = _("Could not parse structured output from the provider.")
            self._normalize(result, parsed, fields_spec)
        return self._finish(result, post_processor)

    # ------------------------------------------------------------- helpers
    def _finish(self, result, post_processor):
        if post_processor:
            try:
                out = post_processor(result)
                if isinstance(out, dict):
                    result = out
            except Exception as e:  # a broken post-processor must not crash
                _logger.exception("biz.doc.ocr: post_processor failed")
                result['error'] = result.get('error') or str(e)
        return result

    def _collect_images(self, attachment_ids, provider):
        """Return (images, error). images = [{'mime','data_b64'}]."""
        ids = [int(a) for a in (attachment_ids or []) if a]
        atts = self.env['ir.attachment'].sudo().browse(ids)
        images = []
        for att in atts:
            if not att.datas:
                continue
            mime = att.mimetype or 'image/png'
            if mime == 'application/pdf' and not provider.accepts_pdf():
                return [], _(
                    "This provider cannot read PDFs directly — upload a JPG or "
                    "PNG image of the document.")
            data = att.datas
            if isinstance(data, bytes):
                data = data.decode()
            images.append({'mime': mime, 'data_b64': data})
        return images, False

    def _build_prompt(self, fields_spec, doc_kinds):
        lines = [
            "You are a precise document data-extraction engine.",
            "Read the attached document image(s) and extract the fields below.",
            "Respond with STRICT JSON ONLY — no prose, no markdown fences.",
            "",
            "Shape:",
            '{"doc_kind": <one of the kinds below or null>,',
            ' "fields": { <field_name>: {"value": <string or null>,'
            ' "confidence": <number 0..1>} } }',
            "",
            "Fields:",
        ]
        for f in fields_spec:
            hint = (" — %s" % f['hint']) if f.get('hint') else ""
            lines.append("- %s (%s)%s" % (
                f.get('name'), f.get('type', 'char'), hint))
        if doc_kinds:
            lines.append("")
            lines.append("Possible doc_kind values: %s" % ", ".join(doc_kinds))
        lines.append("")
        lines.append("Use null and confidence 0 for anything not present. "
                     "Digits fields must contain digits only.")
        return "\n".join(lines)

    def _normalize(self, result, parsed, fields_spec):
        """Fold a parsed JSON blob into the canonical result shape."""
        if not isinstance(parsed, dict):
            return
        raw_fields = parsed.get('fields')
        if not isinstance(raw_fields, dict):
            # provider returned a flat {name: value} blob
            raw_fields = {k: v for k, v in parsed.items() if k != 'doc_kind'}
        result['doc_kind'] = parsed.get('doc_kind') or result.get('doc_kind')
        for f in fields_spec:
            name = f.get('name')
            cell = raw_fields.get(name)
            if isinstance(cell, dict):
                value = cell.get('value')
                conf = cell.get('confidence')
            else:
                value = cell
                conf = None
            if value in (None, ''):
                continue
            try:
                conf = float(conf) if conf is not None else 0.0
            except (TypeError, ValueError):
                conf = 0.0
            result['fields'][name] = {
                'value': ('' if value is None else str(value)).strip(),
                'confidence': max(0.0, min(1.0, conf)),
            }


class BizDocOcrJob(models.Model):
    _name = 'biz.doc.ocr.job'
    _description = 'Document OCR Job'
    _order = 'id desc'

    res_model = fields.Char(string='Model', required=True, index=True)
    res_id = fields.Integer(string='Record ID', required=True, index=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ], default='pending', required=True, index=True)
    attempts = fields.Integer(default=0)
    payload = fields.Text(help='JSON request context (schema / attachment ids).')
    result = fields.Text(help='JSON extraction result.')
    error = fields.Text()
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, index=True)

    _MAX_ATTEMPTS = 3

    def run(self):
        """Run each job inline: delegate to the consumer's OCR hook.

        The consumer record (``res_model``/``res_id``) must implement
        ``_biz_doc_ocr_run(job)`` — it calls ``biz.doc.ocr.extract`` with its own
        schema + post_processor, applies the result to itself, and returns the
        result dict. Keeps the engine ignorant of any domain model.
        """
        for job in self:
            job.write({'attempts': job.attempts + 1, 'state': 'running'})
            try:
                target = self.env[job.res_model].browse(job.res_id)
                if not target.exists() or not hasattr(target, '_biz_doc_ocr_run'):
                    job.write({'state': 'failed',
                               'error': 'consumer %s has no _biz_doc_ocr_run' % job.res_model})
                    continue
                res = target._biz_doc_ocr_run(job) or {}
                failed = bool(res.get('error')) and not res.get('fields')
                job.write({
                    'result': json.dumps(res),
                    'error': res.get('error') or False,
                    'state': 'failed' if failed else 'done',
                })
            except Exception as e:
                _logger.exception("biz.doc.ocr.job %s failed", job.id)
                job.write({'state': 'failed', 'error': str(e)})
        return True

    @api.model
    def cron_retry(self):
        """Re-attempt pending jobs and failed jobs under the attempt cap."""
        jobs = self.search([
            '|', ('state', '=', 'pending'),
            '&', ('state', '=', 'failed'), ('attempts', '<', self._MAX_ATTEMPTS),
        ], limit=50)
        for job in jobs:
            try:
                with self.env.cr.savepoint():
                    job.run()
            except Exception:
                _logger.exception("biz.doc.ocr.job cron: job %s", job.id)
        return True
