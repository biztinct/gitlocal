# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""The page title of a printed report never names the platform.

T1 a report's web preview (`/report/html/...`) carries the report's own name
   as its page title, over HTTP, and no vendor name in that title.
T2 the same page rendered in code (the PDF is made from it): the same title.
T3 one document whose report says how to name it -> the printed name;
   several documents -> the report's name.
T4 a page with nothing to name it -> the neutral "Report"; a report that sets
   its own `title` keeps it — on both the print and the preview layouts.
"""
import re

from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

VENDOR = re.compile('od' + 'oo', re.I)
TITLE = re.compile(r'<title>(.*?)</title>', re.S)


def _title(html):
    if isinstance(html, bytes):
        html = html.decode('utf-8')
    found = TITLE.search(html)
    return found.group(1).strip() if found else None


@tagged('post_install', '-at_install')
class TestReportTitle(TransactionCase):

    def test_t2_rendered_page_title_is_the_report_name(self):
        model = self.env['ir.model']._get('res.partner')
        html, _kind = self.env['ir.actions.report']._render_qweb_html(
            'base.report_ir_model_overview', model.ids)
        title = _title(html)
        self.assertEqual(title, 'Model Overview')
        self.assertFalse(VENDOR.search(title))

    def test_t3_printed_name_for_one_document(self):
        report = self.env['ir.actions.report'].create({
            'name': 'BizDebrand Card', 'model': 'res.partner',
            'report_type': 'qweb-html', 'report_name': 'base.report_irmodeloverview',
            'print_report_name': "'Card - %s' % object.name"})
        partner = self.env['res.partner'].create({'name': 'Title Person'})
        other = self.env['res.partner'].create({'name': 'Other Person'})
        Report = self.env['ir.actions.report']
        self.assertEqual(Report._biz_report_title(report, partner.ids), 'Card - Title Person')
        self.assertEqual(Report._biz_report_title(report, (partner | other).ids),
                         'BizDebrand Card')
        report.print_report_name = 'object.no_such_field'
        data = Report._get_rendering_context(report, partner.ids, {})
        self.assertNotIn('biz_report_title', data,
                         'a name that cannot be worked out never stops a print')

    def test_t4_neutral_fallback_and_own_title_kept(self):
        QWeb = self.env['ir.qweb']
        for layout in ('web.report_layout', 'web.report_preview_layout'):
            plain = _title(str(QWeb._render(layout, {'preview_css': ''})))
            self.assertEqual(plain, 'Report', layout)
            own = _title(str(QWeb._render(layout, {'title': 'My own title',
                                                   'biz_report_title': 'Not this',
                                                   'preview_css': ''})))
            self.assertEqual(own, 'My own title', layout)
            named = _title(str(QWeb._render(layout, {'biz_report_title': 'Payslip - A',
                                                     'preview_css': ''})))
            self.assertEqual(named, 'Payslip - A', layout)
        installed = {code for code, _n in self.env['res.lang'].get_installed()}
        Report = self.env['ir.actions.report']
        for code, word in (('vi_VN', 'Báo cáo'), ('id_ID', 'Laporan')):
            if code in installed:
                self.assertEqual(Report.with_context(lang=code)._biz_default_title(), word)


@tagged('post_install', '-at_install')
class TestReportTitleHttp(HttpCase):

    def test_t1_preview_tab_title(self):
        # its own login: a copied database may have no usable 'admin'
        new_test_user(self.env, login='bizdebrand_reports', password='bizdebrand-Rep-1',
                      groups='base.group_user,base.group_system')
        self.authenticate('bizdebrand_reports', 'bizdebrand-Rep-1')
        model = self.env['ir.model']._get('res.partner')
        res = self.url_open('/report/html/base.report_irmodeloverview/%s' % model.id)
        self.assertEqual(res.status_code, 200)
        title = _title(res.text)
        self.assertEqual(title, 'Model Overview')
        self.assertFalse(VENDOR.search(title or ''))
