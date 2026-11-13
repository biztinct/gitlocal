import hashlib
import re
from datetime import timedelta

from odoo import fields, http
from odoo.http import request
from odoo.addons.website.controllers.main import Website
from werkzeug.utils import redirect


INTERESTS = ('Custom software', 'Workflow automation', 'Connected business systems',
             'Websites & e-commerce', 'Not sure yet')
LEGACY_ROUTES = {
    '/operations': '/solutions#operations',
    '/sales': '/solutions#sales',
    '/productivity': '/solutions#automation',
    '/website-design-e-commerce': '/solutions#digital',
    '/restaurant-and-cafe': '/solutions#industries',
    '/education-and-coaching': '/solutions#industries',
    '/transport-and-fleet': '/solutions#industries',
    '/clinic-and-hospital': '/solutions#industries',
    '/hotel-management': '/solutions#industries',
    '/building-and-construction': '/solutions#industries',
    '/event-management': '/solutions#industries',
    '/contactus-thank-you': '/contactus/thanks',
}


def is_biztinct():
    target = request.env['ir.config_parameter'].sudo().get_param(
        'biztinct_website.website_id', '0')
    return str(request.website.id) == target


def render_page(page, title, description, **values):
    context = dict(page=page, title=title, description=description, year=fields.Datetime.now().year,
                   interests=INTERESTS, form={}, errors={}, consent_checked=False, **values)
    response = request.render('biztinct_website.' + page, context)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Cache-Control'] = 'no-store' if page == 'contact' else 'no-cache'
    return response


class BiztinctWebsite(Website):
    @http.route()
    def web_login(self, *args, **kw):
        response = super().web_login(*args, **kw)
        if is_biztinct() and getattr(response, 'template', None) == 'web.login':
            response.template = 'biztinct_website.login'
            response.qcontext.update(
                page='login', title='Sign in to Biztinct',
                description='Sign in to your Biztinct account.', year=fields.Datetime.now().year,
            )
        return response

    @http.route()
    def index(self, **kw):
        if not is_biztinct():
            return super().index(**kw)
        return render_page('home', 'Custom software. Better business flow.',
                           'Biztinct builds custom software, automates manual work and connects '
                           'your business systems around the way you work.')

    @http.route('/solutions', type='http', auth='public', website=True, sitemap=True)
    def solutions(self, **kw):
        if not is_biztinct():
            return request.not_found()
        return render_page('solutions', 'Solutions shaped around your business',
                           'Custom software, business automation, connected operations and '
                           'websites for businesses and not-for-profit organisations.')

    @http.route('/approach', type='http', auth='public', website=True, sitemap=True)
    def approach(self, **kw):
        if not is_biztinct():
            return request.not_found()
        return render_page('approach', 'A better way to build',
                           'Discover how Biztinct combines custom development with established '
                           'business functionality to create software that fits.')

    @http.route('/contactus', type='http', auth='public', website=True,
                methods=['GET', 'POST'], sitemap=True)
    def contact(self, **kw):
        if not is_biztinct():
            return request.env['ir.http']._serve_page() or request.not_found()
        errors, values = {}, {}
        if request.httprequest.method == 'POST':
            if kw.get('website_url'):
                return redirect('/contactus/thanks', code=303)
            limits = {'name': 120, 'email': 254, 'company': 160, 'phone': 50,
                      'interest': 60, 'message': 6000}
            for key, limit in limits.items():
                value = str(kw.get(key, '')).strip()
                if len(value) > limit:
                    errors[key] = 'Please keep this field under %s characters.' % limit
                values[key] = value[:limit]
            if not values['name']:
                errors['name'] = 'Please enter your name.'
            if (not re.fullmatch(r'[^\s<>@,;:]+@[^\s<>@,;:]+\.[^\s<>@,;:]+', values['email'])
                    or '\r' in values['email'] or '\n' in values['email']):
                errors['email'] = 'Please enter a valid email address.'
            if not values['message']:
                errors['message'] = 'Tell us a little about what you have in mind.'
            if values['interest'] not in INTERESTS:
                errors['interest'] = 'Please choose an option.'
            if kw.get('consent') != 'yes':
                errors['consent'] = 'Please confirm that we can contact you about your enquiry.'
            if not errors:
                # Use the proxy's real client address only on the local nginx hop.
                address = request.httprequest.remote_addr or ''
                if address in ('127.0.0.1', '::1'):
                    address = request.httprequest.headers.get('X-Real-IP', address)
                source = hashlib.sha256((request.db + ':' + address).encode()).hexdigest()
                # Serialise a client's submissions so parallel posts cannot bypass the limit.
                lock = int(source[:15], 16)
                request.env.cr.execute('SELECT pg_advisory_xact_lock(%s)', [lock])
                contact_model = request.env['biztinct.contact'].sudo()
                recent = fields.Datetime.now() - timedelta(minutes=10)
                if contact_model.search_count([('source_hash', '=', source),
                                               ('create_date', '>=', recent)]) >= 5:
                    errors['general'] = 'Please wait a few minutes before sending another enquiry. '
                    errors['general'] += 'You can also email ash@biztinct.com directly.'
                else:
                    contact_model.create(dict(values, website_id=request.website.id,
                                              source_hash=source))
                    return redirect('/contactus/thanks', code=303)
        response = render_page('contact', 'Let’s make things work better',
                               'Talk to Biztinct about custom software, automation or a better '
                               'connected business. Contact Ash at ash@biztinct.com.')
        response.qcontext.update(form=values, errors=errors, consent_checked=kw.get('consent') == 'yes')
        if errors:
            response.status_code = 400
        return response

    @http.route('/contactus/thanks', type='http', auth='public', website=True, sitemap=False)
    def thanks(self, **kw):
        if not is_biztinct():
            return request.not_found()
        return render_page('thanks', 'Thank you for getting in touch',
                           'Your enquiry has been saved. Thank you for contacting Biztinct.')

    @http.route('/privacy', type='http', auth='public', website=True, sitemap=True)
    def privacy(self, **kw):
        if not is_biztinct():
            return request.not_found()
        return render_page('privacy', 'Your enquiry and privacy',
                           'How Biztinct handles the information you share through the contact form.')

    @http.route(list(LEGACY_ROUTES), type='http', auth='public', website=True, sitemap=False)
    def legacy(self, **kw):
        if not is_biztinct():
            return request.env['ir.http']._serve_page() or request.not_found()
        return redirect(LEGACY_ROUTES[request.httprequest.path.rstrip('/')], code=301)

    @http.route('/biztinct/mail-setup', type='http', auth='user', sitemap=False)
    def mail_setup(self, **kw):
        if not request.env.user.has_group('base.group_system'):
            return request.not_found()
        server = request.env.ref('biztinct_website.gmail_server')
        return redirect('/web#id=%s&model=ir.mail_server&view_type=form' % server.id, code=303)

    @http.route('/biztinct/enquiries', type='http', auth='user', sitemap=False)
    def enquiries(self, **kw):
        if not request.env.user.has_group('base.group_system'):
            return request.not_found()
        action = request.env.ref('biztinct_website.contact_action')
        return redirect('/web#action=%s' % action.id, code=303)

    @http.route()
    def sitemap_xml_index(self, **kw):
        if not is_biztinct():
            return super().sitemap_xml_index(**kw)
        paths = ('/', '/solutions', '/approach', '/contactus', '/privacy')
        xml = '<?xml version="1.0" encoding="UTF-8"?>'
        xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        xml += ''.join('<url><loc>https://biztinct.com%s</loc></url>' % path for path in paths)
        xml += '</urlset>'
        return request.make_response(xml, [('Content-Type', 'application/xml; charset=utf-8')])
