# Part of biz_errors — the branded breakdown screen.
# License LGPL-3.
"""The one seam that turns a crash report into a breakdown screen.

WHY ``_get_error_html`` AND NOT ``_get_exception_code_values``. The dispatch in
``http_routing/models/ir_http.py._handle_error`` is::

    code, values = cls._get_exception_code_values(exception)   # transaction may be ABORTED
    request.env.cr.rollback()                                  # cursor usable from here
    if code in (404, 403):  ... _serve_fallback()
    elif code == 500:       values = cls._get_values_500_error(...)
    code, html = cls._get_error_html(request.env, code, values)

``_get_exception_code_values`` runs before the rollback, so an
``ir.config_parameter`` read there can raise ``InFailedSqlTransaction`` — the
very exception being handled may have aborted the transaction.
``_get_error_html`` runs after the rollback and is reached by every status code,
so it is the single correct place to read the brand, mint a reference and blank
the technical values.

Everything here is wrapped in try/except on purpose. A breakdown page that
itself breaks is unrecoverable: the handler has nowhere left to go. A failure in
this module logs a warning and renders the stock page.
"""
import logging
import secrets

from odoo import models
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

#: Crockford base32 without I, L, O and U — unambiguous when read down a phone.
_REF_ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'

#: Last-resort wording. Never a vendor name, never a product we are not.
_NEUTRAL_BRAND = 'this application'

#: The codes this module decorates. 404 is deliberately absent: the website's
#: own 404 page is already branded and is a binding non-goal of this phase.
#: String codes ('page_404', 'protected_403') belong to website's own fallback
#: rendering and are left alone for the same reason.
_SKIP_CODES = (404, 'page_404', 'protected_403')


def _mint_reference():
    """Eight random characters, grouped. Random, never derived.

    The reference must reveal nothing about the failure, the user or the
    database — it is a lookup key for the log, not a fingerprint.
    """
    body = ''.join(secrets.choice(_REF_ALPHABET) for _ in range(8))
    return '%s-%s' % (body[:4], body[4:])


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    # ------------------------------------------------------------------
    # The seam
    # ------------------------------------------------------------------
    @classmethod
    def _get_error_html(cls, env, code, values):
        try:
            if code not in _SKIP_CODES:
                values = cls._biz_error_values(env, code, values)
        except Exception:                                        # noqa: BLE001
            _logger.warning('biz_errors: could not decorate the breakdown page',
                            exc_info=True)
        return super()._get_error_html(env, code, values)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @classmethod
    def _biz_error_values(cls, env, code, values):
        """Mint, log, blank, decide, brand — in that order.

        The order matters twice: the log has to happen before anything is
        removed, and the ``UserError`` question has to be asked before the
        exception object is dropped.
        """
        values = dict(values or {})

        # 1. Mint the reference.
        ref = _mint_reference()

        # 2. Log it beside the stack, before anything is removed. Read the path
        #    defensively: request may be in an odd state by the time we get here.
        path = '-'
        try:
            path = request.httprequest.full_path or request.httprequest.path
        except Exception:                                        # noqa: BLE001
            pass
        _logger.error('biz_errors [%s] %s %s\n%s', ref, code, path,
                      values.get('traceback') or values.get('error_message') or '')

        # 3. Decide error_message BEFORE the exception object goes away.
        #    UserError text is a sentence somebody wrote for a person: keep it.
        #    A werkzeug description is generic framework prose: our own wording
        #    replaces it. Anything else never had a message. Never str(e).
        if not isinstance(values.get('exception'), UserError):
            values.pop('error_message', None)

        # 4. Blank the technical values. Also shut the gate the stock templates
        #    open with `editable or debug`, so a template we have not replaced
        #    still cannot print a crash report.
        for key in ('traceback', 'qweb_exception', 'exception'):
            values.pop(key, None)
        values['editable'] = False
        # ''. NOT False. `debug` is a *string* of comma-separated flags all the
        # way through the platform, and web.conditional_assets_tests asks
        # `'tests' in debug` — which raises TypeError on a bool and takes the
        # whole page down with it. See ER10.
        values['debug'] = ''

        # 5. Add the brand.
        brand_name, brand_color = cls._biz_error_brand(env)
        values['brand_name'] = brand_name
        values['brand_color'] = brand_color
        values['brand_home'] = '/'
        values['error_ref'] = ref

        # The browser tab is a screen too. Left alone, website.layout titles the
        # 4xx family from the template's own name and the tab reads "403 | Rize".
        # `additional_title` is read straight out of the render values
        # (website_templates.xml:108), so setting it here is enough.
        values['additional_title'] = env._('Something went wrong')
        return values

    @classmethod
    def _biz_error_brand(cls, env):
        """The same chain biz_debrand uses, read without depending on it.

        biz_debrand.brand_name -> web_debranding.new_name -> the company name ->
        a neutral phrase. There is no vendor name at the end of this chain.
        """
        name = ''
        color = ''
        try:
            icp = env['ir.config_parameter'].sudo()
            name = (icp.get_param('biz_debrand.brand_name')
                    or icp.get_param('web_debranding.new_name') or '').strip()
            color = (icp.get_param('biz_debrand.theme_color') or '').strip()
        except Exception:                                        # noqa: BLE001
            _logger.warning('biz_errors: could not read the brand parameters',
                            exc_info=True)
        if not name:
            try:
                name = (env.company.name or '').strip()
            except Exception:                                    # noqa: BLE001
                name = ''
        # A colour we cannot vouch for is no colour: the stylesheet has its own
        # safe default and an unvalidated value would be injected into CSS.
        if not (len(color) in (4, 7) and color.startswith('#')
                and all(c in '0123456789abcdefABCDEF' for c in color[1:])):
            color = ''
        return (name or _NEUTRAL_BRAND), color
