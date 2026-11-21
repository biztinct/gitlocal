from odoo import http
from odoo.http import request


class GoogleCalendarNotifications(http.Controller):
    @http.route('/pb/calendar/google/notify', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    def notify(self, **kwargs):
        # Tenant is selected by the deployment's host/dbfilter, never a body
        # parameter. Authentication is the per-channel random token + resource.
        request.env['pb.calendar.google.channel']._receive(request.httprequest.headers)
        # Identical responses avoid exposing subscription existence to callers.
        return request.make_response('', status=204)
