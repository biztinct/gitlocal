odoo.define('pb_hr_payroll_indonesia.payroll_breadcrumb', function (require) {
    'use strict';

    const { Component } = owl;
    const { useState } = owl.hooks;
    const session = require('web.session');

    class PayrollCountryBreadcrumb extends Component {
        setup() {
            this.state = useState({
                country: session.payroll_country || '',
                countryName: this._getCountryName(session.payroll_country)
            });
        }

        _getCountryName(code) {
            const names = {
                'VN': 'Vietnam',
                'ID': 'Indonesia',
                'IN': 'India'
            };
            return names[code] || '';
        }

        async onChangeCountry() {
            // Redirect to country selector
            window.location.href = '/payroll/country-selector';
        }
    }

    PayrollCountryBreadcrumb.template = 'pb_hr_payroll_indonesia.PayrollCountryBreadcrumb';

    return PayrollCountryBreadcrumb;
});