# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Deterministic VN-bank layer (Phase D §3.3).

The always-on, no-AI normalization/validation layer: a registry of Vietnamese
banks + pure helpers to fold diacritics, resolve a bank name, pull an account
number out of OCR prose, and score name similarity with stdlib difflib. This is
what makes the feature work with Tesseract (prose only) or no provider at all.
"""

import re
import difflib
import unicodedata

from odoo import api, fields, models

# SWIFT/BIC — VN banks carry the VN country code in positions 5-6
_SWIFT_VN = re.compile(r'^[A-Z]{4}VN[A-Z0-9]{2}([A-Z0-9]{3})?$')
_SWIFT_GENERIC = re.compile(r'^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$')
# a VN account number is a bank-specific 6–19 digit string
_ACCOUNT_RUN = re.compile(r'\d{6,19}')


def fold(text):
    """Diacritic-fold + uppercase + whitespace-collapse for robust matching.

    "Ngân hàng Ngoại thương" → "NGAN HANG NGOAI THUONG";
    "Nguyễn Văn Á" ≡ "NGUYEN VAN A".
    """
    if not text:
        return ''
    decomposed = unicodedata.normalize('NFD', str(text))
    stripped = ''.join(c for c in decomposed if not unicodedata.combining(c))
    # Vietnamese đ/Đ do not decompose — map explicitly
    stripped = stripped.replace('đ', 'd').replace('Đ', 'D')
    return re.sub(r'\s+', ' ', stripped).strip().upper()


def name_similarity(a, b):
    """0..100 similarity between two person/holder names (diacritic-insensitive)."""
    fa, fb = fold(a), fold(b)
    if not fa or not fb:
        return 0.0
    return round(difflib.SequenceMatcher(None, fa, fb).ratio() * 100.0, 1)


def extract_account_number(raw_text):
    """Longest 6–19 digit run in OCR prose (used when the provider missed it)."""
    if not raw_text:
        return ''
    runs = _ACCOUNT_RUN.findall(re.sub(r'[ \-.]', '', str(raw_text)))
    return max(runs, key=len) if runs else ''


def swift_ok(swift):
    if not swift:
        return True  # optional
    s = fold(swift).replace(' ', '')
    return bool(_SWIFT_VN.match(s) or _SWIFT_GENERIC.match(s))


def account_ok(number):
    if not number:
        return False
    digits = re.sub(r'\D', '', str(number))
    return 6 <= len(digits) <= 19


class PbBankRegistry(models.Model):
    _name = 'pb.bank.registry'
    _description = 'Vietnam Bank Registry'
    _order = 'short_name, name'

    name = fields.Char(string='Bank Name', required=True, translate=True)
    short_name = fields.Char(string='Short Name', required=True)
    swift_prefix = fields.Char(string='SWIFT Prefix', help='First 4 letters of the BIC.')
    aliases = fields.Char(
        string='Aliases',
        help='Comma-separated alternate names/abbreviations used for matching.')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', index=True)

    @api.model
    def _all_terms(self):
        """{registry_id: [folded terms]} for every active bank."""
        out = {}
        for rec in self.sudo().search([]):
            terms = [rec.name or '', rec.short_name or '']
            terms += (rec.aliases or '').split(',')
            out[rec.id] = [fold(t) for t in terms if t and fold(t)]
        return out

    @api.model
    def match(self, raw_name):
        """Resolve a raw/OCR bank name to a registry record (or empty).

        Token-SUBSET match (order-independent): an alias resolves when all of its
        folded word-tokens appear in the target — so "NGAN HANG TMCP NGOAI THUONG
        VN" resolves to Vietcombank via the "Ngan hang Ngoai thuong" alias even
        with the interposed "TMCP". The most-specific alias (most letters
        matched) wins. Deterministic, no AI.
        """
        target = set(fold(raw_name).split())
        if not target:
            return self.browse()
        best_id, best_score = False, 0
        for rid, terms in self._all_terms().items():
            for t in terms:
                toks = [w for w in t.split() if len(w) >= 2]
                if toks and all(w in target for w in toks):
                    score = sum(len(w) for w in toks)
                    if score > best_score:
                        best_id, best_score = rid, score
        return self.browse(best_id) if best_id else self.browse()
