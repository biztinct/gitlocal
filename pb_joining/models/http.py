import logging
import re

from odoo import models
from odoo.http import request

# The framework logs its request line after dispatch and rejected CSRF paths before dispatch.
_JOIN_PATH = re.compile(r'/join/[^\s"\x1b]+')
HEADERS = {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'X-Robots-Tag': 'noindex'}


class JoiningPathFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        if '/join/' in message:
            record.msg = _JOIN_PATH.sub('/join/[private]', message)
            record.args = ()
        return True


for logger_name in ('werkzeug', 'odoo.http'):
    logger = logging.getLogger(logger_name)
    if not any(isinstance(f, JoiningPathFilter) for f in logger.filters):
        logger.addFilter(JoiningPathFilter())


class JoiningHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _post_dispatch(cls, response):
        result = super()._post_dispatch(response)
        if request.httprequest.path.startswith('/join/'):
            response.headers.update(HEADERS)
        return result

    @classmethod
    def _handle_error(cls, exception):
        if request.httprequest.path.startswith('/join/'):
            from ..controllers.joining import JoiningPages
            response = JoiningPages()._problem(request.env._('Open your joining link again and try once more.'))
            response.status_code = getattr(exception, 'code', None) or 500
            response.headers.update(HEADERS)
            return response
        return super()._handle_error(exception)
