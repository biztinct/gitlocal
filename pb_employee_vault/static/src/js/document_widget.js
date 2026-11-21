/** @odoo-module **/
import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Employee360Drawer } from "./employee_360";
class EmployeeDocuments extends Component {
    static props = { ...standardWidgetProps };
    static components = { Employee360Drawer };
    static template = xml`<div><Employee360Drawer t-if="props.record.resId" empId="props.record.resId" embedded="true"/><span t-else="">Save the employee before adding documents.</span></div>`;
}
registry.category("view_widgets").add("pb_employee_documents", { component: EmployeeDocuments });
