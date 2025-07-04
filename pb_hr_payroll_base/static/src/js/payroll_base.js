/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

// Multi-Country Payroll Dashboard Component
export class PayrollDashboard extends Component {
    setup() {
        this.orm = this.env.services.orm;
        this.action = this.env.services.action;
    }

    async onCountryChange(country) {
        try {
            const dashboard = await this.orm.call(
                "payroll.dashboard",
                "get_or_create_dashboard",
                [country]
            );
            
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: `${country} Payroll Dashboard`,
                res_model: 'payroll.dashboard',
                view_mode: 'form',
                res_id: dashboard,
                target: 'current'
            });
        } catch (error) {
            console.error('Error switching country:', error);
        }
    }

    async refreshStatistics() {
        // Refresh dashboard statistics
        await this.orm.call(
            "payroll.dashboard",
            "_compute_statistics",
            [this.props.record.resId]
        );
        
        // Reload the view
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'reload'
        });
    }
}

PayrollDashboard.template = "pb_hr_payroll_base.PayrollDashboard";

registry.category("components").add("PayrollDashboard", PayrollDashboard);

// Country Selector Widget
export class CountrySelector extends Component {
    setup() {
        this.availableCountries = ['VN', 'ID', 'IN', 'SG', 'MY'];
    }

    onCountrySelect(country) {
        this.props.onSelect(country);
    }
}

CountrySelector.template = "pb_hr_payroll_base.CountrySelector";

registry.category("components").add("CountrySelector", CountrySelector);