"""Feeds expose only selected public adverts for the current website/company."""
import hmac
from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
from ..services.board_feeds import render_feed
from ..services.board_catalogue import FEED_KEYS


class HiringBoardFeeds(http.Controller):
    @http.route('/hiring/job-feed/<int:website_id>/<int:channel_id>/<string:token>.xml',
                type='http', auth='public', website=True, methods=['GET'], sitemap=False)
    def feed(self, website_id, channel_id, token, **kwargs):
        site = request.website
        if site.id != website_id:
            return request.not_found()
        channel = request.env['pb.hiring.channel'].sudo().browse(channel_id).exists()
        if (not channel or channel.company_id != site.company_id or not channel.active
                or not channel.feed_enabled or channel.key not in FEED_KEYS or not channel.feed_token
                or not hmac.compare_digest(channel.feed_token, token)):
            return request.not_found()
        try:
            body = render_feed(channel.key, channel._feed_items(site))
        except UserError:
            return request.not_found()
        return request.make_response(body, headers=[('Content-Type', 'application/xml; charset=utf-8'),
                                                    ('Cache-Control', 'no-store'),
                                                    ('X-Robots-Tag', 'noindex'),
                                                    ('X-Content-Type-Options', 'nosniff')])
