/** @odoo-module **/
import { describe, expect, test } from "@odoo/hoot";
import { MappingStudio } from "@pb_formula_studio/js/mapping/mapping_studio";

describe.current.tags("desktop");

test("Payroll uses the same show/hide model as other category pills", async () => {
    const host = Object.create(MappingStudio.prototype);
    host.state = {mode: "employee", data: {counts: {}}, busy: false, empPayroll: false, empLane: null, empHiddenLanes: []};
    let loads = 0;
    host.load = async () => loads++;
    const payroll = {role: "payroll", label: "Payroll"};
    const identity = {role: "identity", label: "Identity"};
    expect(host.empLaneVisible(identity)).toBe(true);
    expect(host.empExcludedGroups).toEqual(["Payroll"]);
    const filters = host.empExcludedGroups;
    expect(host.empExcludedGroups).toBe(filters);
    expect(host.empLaneVisible(payroll)).toBe(false);
    await host.toggleEmpLane(payroll);
    expect(host.empLaneVisible(payroll)).toBe(true);
    expect(host.empExcludedGroups).toEqual([]);
    await host.toggleEmpLane(payroll);
    expect(host.empLaneVisible(payroll)).toBe(false);
    await host.toggleEmpLane(identity);
    expect(host.empLaneVisible(identity)).toBe(false);
    await host.showAllEmpLanes();
    expect(host.empLaneVisible(identity)).toBe(true);
    expect(host.empLaneVisible(payroll)).toBe(true);
    expect(loads).toBe(0);
    host.state.busy = true;
    await host.toggleEmpLane(payroll);
    expect(host.empLaneVisible(payroll)).toBe(true);
});
