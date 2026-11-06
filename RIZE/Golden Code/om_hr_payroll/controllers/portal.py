from odoo import http, _
from odoo.osv import expression
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from collections import OrderedDict
from odoo.http import request
from pudb import set_trace

class CustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)

        if 'payslip_count' in counters:
            payslip_count = request.env['hr.payslip'].search_count(self._get_payslips_domain()) \
                if request.env['hr.payslip'].check_access_rights('read', raise_exception=False) else 0
            values['payslip_count'] = payslip_count
        return values
    # ------------------------------------------------------------
    # My Payslips
    # ------------------------------------------------------------

    def _payslip_get_page_view_values(self, payslip, access_token, **kwargs):
        values = {
            'page_name': 'payslip',
            'payslip': payslip,
        }
        return self._get_page_view_values(payslip, access_token, values, 'my_payslips_history', False, **kwargs)

    def _get_payslips_domain(self):
        employee = request.env['hr.employee'].search([('user_id', '=', request.env.user.id)], limit=1)
        return [
            ('employee_id', '=', employee.id),
            ('state', 'in', ('done', 'cancel')),
        ]

    def _get_payslip_searchbar_sortings(self):
        return {
            'date': {'label': _('Date'), 'order': 'date_to desc'},
            'name': {'label': _('Name'), 'order': 'name desc'},
            'state': {'label': _('Status'), 'order': 'state'},
        }

    @http.route(['/my/payslips', '/my/payslips/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_payslips(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        #set_trace()
        values = self._prepare_my_payslips_values(page, date_begin, date_end, sortby, filterby)

        # pager
        pager = portal_pager(**values['pager'])

        # content according to pager and archive selected
        payslips = values['payslips'](pager['offset'])
        request.session['my_payslips_history'] = payslips.ids[:100]

        values.update({
            'payslips': payslips,
            'pager': pager,
        })
        return request.render("om_hr_payroll.portal_my_payslips", values)  # Create this template

    def _prepare_my_payslips_values(self, page, date_begin, date_end, sortby, filterby, domain=None, url="/my/payslips"):
        values = self._prepare_portal_layout_values()
        Payslip = request.env['hr.payslip']

        domain = expression.AND([
            domain or [],
            self._get_payslips_domain(),
        ])

        searchbar_sortings = self._get_payslip_searchbar_sortings()

        # default sort by order
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        if date_begin and date_end:
            domain += [('date_to', '>', date_begin), ('date_to', '<=', date_end)]

        values.update({
            'date': date_begin,
            'payslips': lambda pager_offset: (
                Payslip.search(domain, order=order, limit=self._items_per_page, offset=pager_offset)
                if Payslip.check_access_rights('read', raise_exception=False) else
                Payslip
            ),
            'page_name': 'payslip',
            'pager': {
                "url": url,
                "url_args": {'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
                "total": Payslip.search_count(domain) if Payslip.check_access_rights('read', raise_exception=False) else 0,
                "page": page,
                "step": self._items_per_page,
            },
            'default_url': url,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return values

    @http.route(['/my/payslips/<int:payslip_id>'], type='http', auth="public", website=True)
    def portal_my_payslip_detail(self, payslip_id, access_token=None, report_type=None, download=False, **kw):
        #set_trace()
        try:
            payslip_sudo = self._document_check_access('hr.payslip', payslip_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        if report_type in ('html', 'pdf', 'text'):
            return self._show_report(model=payslip_sudo, report_type=report_type, report_ref='om_hr_payroll.action_report_payslip', download=download)

        values = self._payslip_get_page_view_values(payslip_sudo, access_token, **kw)
        return request.render("om_hr_payroll.portal_payslip_page", values)  # Create this template