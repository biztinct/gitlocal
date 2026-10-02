import logging

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home

_logger = logging.getLogger(__name__)


class LoginLanguage(Home):

    @http.route('/web/login', type='http', auth='none', readonly=False)
    def web_login(self, redirect=None, **kw):
        # Get active/installed languages for the dropdown
        response = super().web_login(redirect=redirect, **kw)

        if hasattr(response, 'qcontext'):
            try:
                installed_langs = request.env['res.lang'].sudo().get_installed()
                # installed_langs is a list of tuples: [('en_US', 'English (US)'), ('vi_VN', 'Vietnamese / Tiếng Việt')]
                response.qcontext['languages'] = installed_langs
                response.qcontext['current_lang'] = kw.get('lang', request.env.lang or 'en_US')
            except Exception as e:
                _logger.warning("Could not load languages for login: %s", e)

        # After successful login, update user's language preference
        if request.params.get('login_success') and kw.get('lang'):
            try:
                lang_code = kw['lang']
                # Verify it's a valid installed language
                valid_langs = dict(request.env['res.lang'].sudo().get_installed())
                if lang_code in valid_langs:
                    user = request.env['res.users'].sudo().browse(request.session.uid)
                    if user.exists() and user.lang != lang_code:
                        user.lang = lang_code
                        _logger.info("User %s language set to %s at login", user.login, lang_code)
                    # Also update the session context
                    request.session['context'] = dict(
                        request.session.get('context', {}),
                        lang=lang_code,
                    )
            except Exception as e:
                _logger.warning("Could not set user language on login: %s", e)

        return response
