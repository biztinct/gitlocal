"""Visual import/review/save: geometry and payroll semantics are separate."""
import re

from odoo import api, models, fields, _
from odoo.addons.pb_hr_payroll_formula.models import payslip_document as documents


META_LABELS = {
    'employee_name': ('employee name', 'employees name', 'full name', 'ho ten nhan vien'),
    'employee_id': ('employee id', 'employee code', 'ma nhan vien'),
    'position': ('position', 'job title', 'vi tri'),
    'contract_type': ('contract type', 'loai hd', 'loai hop dong'),
    'date_joined': ('starting date', 'joining date', 'ngay vao cong ty'),
    'date_left': ('resignation date', 'leaving date', 'ngay nghi viec'),
    'department': ('department', 'phong ban'),
}

# These are semantic aliases, not codes tied to a particular tenant. Ambiguous
# allowances remain suggestions: a contract amount may differ from actual pay.
PAY_LABELS = (
    (r'standard working days|ngay cong chuan', r'standard working days|standard days', .97),
    (r'actual working days|ngay cong thuc te', r'paid days|actual working days', .95),
    (r'actual monthly salary|luong thuc te', r'prorated fixed salary|actual monthly salary|actual basic salary', .96),
    (r'gross salary|luong gop', r'monthly fixed basic salary|contract salary|gross salary', .94),
    (r'compulsory social insurance|bhxh', r'employee si\b|social insurance.*employee|employee.*social insurance', .97),
    (r'compulsory health insurance|bhyt', r'employee hi\b|health insurance.*employee|employee.*health insurance', .97),
    (r'un employment insurance|unemployment insurance|bhtn', r'employee ui\b|unemployment insurance.*employee', .97),
    (r'trade union fee|doan phi', r'employee union dues|employee union fee|trade union fee', .96),
    (r'personal income tax|thue tncn', r'pit withheld|personal income tax$', .96),
    (r'number of dependent|so nguoi phu thuoc', r'registered tax dependents|number of dependents', .97),
    (r'final net pay|thuc linh', r'net payment|net pay|net salary', .96),
    (r'transportation allowance|phu cap xang xe', r'transport.*allowance', .76),
    (r'phone allowance|phu cap dien thoai', r'phone allowance', .76),
)


class PayslipDocumentStudio(models.AbstractModel):
    _inherit = 'pb.formula.studio'

    def _document_config(self, config_id, write=False):
        config = self.env['hr.formula.config'].browse(int(config_id)).exists()
        if not config:
            raise ValueError('Configuration not found.')
        config.check_access('write' if write else 'read')
        if write and not self._can_edit():
            raise ValueError('You do not have permission to edit this configuration.')
        return config

    def _document_score(self, label, rule):
        norm = self._payslip_import_norm(label).replace('đ', 'd')
        target = self._payslip_import_norm('%s %s' % (rule.name, rule.code)).replace('đ', 'd')
        # Never treat an employee deduction as an employer contribution, nor
        # infer an FX conversion by changing the currency symbol.
        if ('usd' in norm and 'usd' not in target) or ('vnd' in norm and 'usd' in target):
            return 0.0
        score = self._payslip_rule_score(label, rule)
        for source_re, target_re, alias_score in PAY_LABELS:
            if re.search(source_re, norm) and re.search(target_re, target):
                score = max(score, alias_score)
        return score

    def _document_draft(self, config, document, filename):
        # Client proposals have no authority to bind a component. Start with
        # blank fields, then produce explicit, reviewable suggestions here.
        rules = config.rule_ids.sorted(key=lambda rule: (rule.sequence, rule.id))
        clean = documents.validate_document(document, set(rules.ids), config.PAYSLIP_META_KEYS)
        sections, unmatched, matched = [], [], 0
        for page_index, page in enumerate(clean['pages']):
            section = {'key': 'page-%s' % (page_index + 1), 'label': _('Page %s', page_index + 1),
                       'color_key': 'indigo', 'matches': []}
            for field in page['fields']:
                if field['binding'] == 'text':
                    continue
                field.update(binding='blank', rule_id=False, meta_key='')
                norm = self._payslip_import_norm(field['label']).replace('đ', 'd').replace('employee s', 'employees')
                meta = next((key for key, labels in META_LABELS.items()
                             if any(re.search(r'\b%s\b' % re.escape(label), norm) for label in labels)), '')
                scored = sorted(((self._document_score(field['label'], rule), rule) for rule in rules),
                                key=lambda pair: (-pair[0], pair[1].sequence))
                score, rule = scored[0] if scored else (0, False)
                margin = score - (scored[1][0] if len(scored) > 1 else 0)
                selected = bool(meta or (score >= .88 and margin >= .07))
                if meta:
                    field.update(binding='meta', meta_key=meta, align='left')
                    score = 1.0
                elif selected:
                    field.update(binding='component', rule_id=rule.id)
                    if rule.value_kind not in ('money',):
                        field['format'] = 'auto'
                if selected:
                    matched += 1
                else:
                    unmatched.append(field['label'])
                section['matches'].append({
                    'source_label': field['label'], 'layout_row_id': field['id'],
                    'rule_id': rule.id if rule and score >= .40 and not meta else False,
                    'rule_name': rule.name if rule and not meta else '',
                    'rule_code': rule.code if rule and not meta else '',
                    'meta_key': meta, 'selected': selected, 'confidence': round(score, 3),
                    'reason': (_('Live employee detail') if meta else
                               _('Strong match') if selected else
                               _('No matching source; bind this field in the visual editor') if score < .40 else
                               _('Review the meaning and whether this is an actual or contract amount')),
                })
            sections.append(section)
        return {
            'ok': True, 'filename': str(filename)[:128], 'provider': 'Local PDF geometry',
            'warning': '', 'sections': sections, 'unmatched': unmatched,
            'matched_count': matched, 'document': clean,
            'document_revision': documents.revision(config.payslip_document),
            'header_html': '', 'footer_html': '', 'layout_html': '',
            'layout_preview_html': '', 'theme': {},
            'options': [{'id': rule.id, 'name': rule.name, 'code': rule.code,
                         'col': rule.column_letter} for rule in rules],
            'meta_options': [{'key': key, 'name': key.replace('_', ' ').title()}
                             for key in config.PAYSLIP_META_KEYS],
        }

    @api.model
    def analyse_payslip_template(self, config_id, upload):
        if isinstance(upload, dict) and upload.get('document'):
            try:
                config = self._document_config(config_id, write=True)
                return self._document_draft(config, upload['document'], upload.get('name', 'Payslip'))
            except (ValueError, TypeError, OverflowError) as error:
                return {'ok': False, 'msg': str(error)}
        return super().analyse_payslip_template(config_id, upload)

    @api.model
    def apply_payslip_template(self, config_id, draft):
        if isinstance(draft, dict) and draft.get('document') and draft.get('apply_layout'):
            try:
                config = self._document_config(config_id, write=True)
                if draft.get('document_revision') != documents.revision(config.payslip_document):
                    return {'ok': False, 'msg': _('This design changed while you reviewed the import. Read the file again before replacing it.')}
                document = documents.validate_document(draft['document'], set(config.rule_ids.ids), config.PAYSLIP_META_KEYS)
                matches = {str(match.get('layout_row_id')): match
                           for section in draft.get('sections', []) if isinstance(section, dict)
                           for match in section.get('matches', []) if isinstance(match, dict)}
                placed = 0
                for page in document['pages']:
                    for field in page['fields']:
                        if field['binding'] == 'text':
                            continue
                        match = matches.get(field['id'], {})
                        field.update(binding='blank', rule_id=False, meta_key='')
                        if match.get('selected'):
                            if match.get('meta_key') in config.PAYSLIP_META_KEYS:
                                field.update(binding='meta', meta_key=match['meta_key'])
                            elif match.get('rule_id') in config.rule_ids.ids:
                                field.update(binding='component', rule_id=match['rule_id'])
                            else:
                                continue
                            placed += 1
                config.payslip_document = document
                return {'ok': True, 'created_sections': 0, 'placed': placed}
            except (ValueError, TypeError, OverflowError) as error:
                return {'ok': False, 'msg': str(error)}
        result = super().apply_payslip_template(config_id, draft)
        if result.get('ok') and isinstance(draft, dict) and draft.get('apply_layout'):
            self._document_config(config_id, write=True).payslip_document = False
        return result

    @api.model
    def payslip_studio_data(self, config_id=None, sample_id=None):
        data = super().payslip_studio_data(config_id, sample_id)
        if not data.get('ok'):
            return data
        config = self._document_config(data['config']['id'])
        doc = config.payslip_document
        data.update(document=doc or False, document_revision=documents.revision(doc))
        by_rule = {component['id']: component.get('value') for component in data['rich_components']}
        # Preview metadata prefers the scheme's own typed sample inputs, with
        # descriptive placeholders for facts an anonymous sample doesn't carry.
        meta = {key: key.replace('_', ' ').title() for key in config.PAYSLIP_META_KEYS}
        for key, labels in META_LABELS.items():
            for rule in config.rule_ids:
                norm = self._payslip_import_norm(rule.name)
                if any(norm == label for label in labels) and by_rule.get(rule.id) not in (None, ''):
                    meta[key] = str(by_rule[rule.id])
                    break
        preview_date = fields.Date.context_today(self)
        meta.update(month='%02d' % preview_date.month,
                    month_name=preview_date.strftime('%B').upper(), year=str(preview_date.year))
        data['document_meta'] = meta
        data['document_pages'] = config._payslip_document_render(by_rule, data['config']['currency'], meta)
        data['document_warnings'] = self._document_warnings(doc, by_rule)
        return data

    def _document_warnings(self, document, values=None):
        warnings = []
        for page in (document or {}).get('pages', []):
            for field in page['fields']:
                if field['binding'] == 'blank':
                    warnings.append(_('%s: no live source selected', field['label']))
                if field['rate_rule_id'] and documents.finite((values or {}).get(field['rate_rule_id'])) <= 0:
                    warnings.append(_('%s: exchange rate is missing or not positive', field['label']))
        return warnings

    @api.model
    def save_payslip_document(self, config_id, document, expected_revision=None):
        try:
            config = self._document_config(config_id, write=True)
            if expected_revision != documents.revision(config.payslip_document):
                return {'ok': False, 'msg': _('This design changed in another session. Close the editor and reload before saving.')}
            clean = documents.validate_document(document, set(config.rule_ids.ids), config.PAYSLIP_META_KEYS)
            config.payslip_document = clean
            return {'ok': True, 'revision': documents.revision(clean)}
        except (ValueError, TypeError, OverflowError) as error:
            return {'ok': False, 'msg': str(error)}

    @api.model
    def delete_payslip_template(self, config_id, template_kind):
        config = self._document_config(config_id, write=True)
        if config.payslip_document:
            if template_kind != 'imported':
                return {'ok': False, 'msg': _('Remove the visual document before deleting the section template.')}
            config.payslip_document = False
            return {'ok': True}
        return super().delete_payslip_template(config_id, template_kind)
