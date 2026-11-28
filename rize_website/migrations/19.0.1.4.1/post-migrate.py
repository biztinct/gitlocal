# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The Rize wordmark becomes the website's logo, where the website still has
the stock "Your Logo" placeholder. The employee pages' top bar
(pb_me_portal_website) shows the website logo, so /my now carries Rize's
brand. A logo somebody already chose is left alone."""
import base64
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools import file_open

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    with file_open('rize_website/static/src/img/rize_logo.png', 'rb') as f:
        logo = base64.b64encode(f.read())
    for site in env['website'].search([]):
        if not site.logo or site.logo == site._default_logo():
            site.logo = logo
            _logger.info('rize_website: Rize logo set on website %s', site.id)
