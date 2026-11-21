import pytz
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import UserError


class InterviewBooking(http.Controller):
    @http.route('/hiring/book/<token>', type='http', auth='public', website=True, methods=['GET','POST'], sitemap=False)
    def book(self, token, **post):
        booking = request.env['pb.hiring.booking'].sudo().search([('token', '=', token)], limit=1)
        if not booking or booking.state not in ('ready', 'booked') or booking.expires_at <= fields.Datetime.now():
            return request.not_found()
        zone_name = post.get('tz') if post.get('tz') in pytz.all_timezones else booking.tz
        zone = pytz.timezone(zone_name)
        error = ''
        if request.httprequest.method == 'POST' and booking.state == 'ready':
            try:
                with request.env.cr.savepoint():
                    booking._book(int(post.get('slot_id', 0)))
            except (UserError, ValueError) as exc:
                error = str(exc) if isinstance(exc, UserError) else 'Choose a time from the list.'
        slots = [{'id': s.id, 'label': pytz.utc.localize(s.start).astimezone(zone).strftime('%a %d %b, %H:%M')}
                 for s in booking.slot_ids if s.start > fields.Datetime.now()]
        response = request.render('pb_hiring.interview_booking_page', dict(
            booking=booking, slots=slots, tz=zone_name, zones=pytz.all_timezones, error=error))
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response
