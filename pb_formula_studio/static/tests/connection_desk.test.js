/** @odoo-module **/
import { describe, expect, test } from "@odoo/hoot";
import { ConnectionDesk } from "@pb_formula_studio/js/mapping/connection_desk";

describe.current.tags("desktop");

function desk(overrides = {}) {
    const component = Object.create(ConnectionDesk.prototype);
    component.props = { data: { can_edit: true, components: [{
        id: 7, type: "input", value_kind: "money", net_role: "info",
        is_contract_component: true, is_text_component: true, ...overrides,
    }], kinds: [{value: "money", money: true}, {value: "quantity"}, {value: "text"}] } };
    const row = component.props.data.components[0];
    component.state = {selected: 7, kind: row.value_kind,
        role: row.net_role, storage: "", storageEditing: false};
    return component;
}

test("Connections contains inputs even when opened with a calculated component", () => {
    const component = desk();
    component.props.data.components.unshift({id: 1, type: "formula"}, {id: 2, type: "constant"});
    component.state.selected = 1;
    expect(component.rows.map(row => row.id)).toEqual([7]);
    expect(component.selected.id).toBe(7);
    expect(component.props.data.components.length).toBe(3); // Journey retains all rows.
});

test("saved text storage is a status and does not reset legacy payroll treatment", () => {
    const component = desk();
    expect(component.savedStorage).toBe("text");
    expect(component.storageMismatch).toBe(true);
    component.pickStorage("text");
    expect(component.state.kind).toBe("money");
    expect(component.state.role).toBe("info");
    expect(component.setupDirty).toBe(false);
});

test("alternative storage stays a draft and discard restores saved settings", () => {
    const component = desk({value_kind: "identifier"});
    component.pickStorage("amount");
    expect(component.savedStorage).toBe("text");
    expect(component.state.kind).toBe("money");
    expect(component.setupDirty).toBe(true);
    component.discardSetup();
    expect(component.state.storage).toBe("");
    expect(component.state.kind).toBe("identifier");
    expect(component.setupDirty).toBe(false);
});

test("adding compatible amount storage preserves a quantity value type", () => {
    const component = desk({is_contract_component: false, value_kind: "quantity"});
    component.pickStorage("amount");
    expect(component.state.kind).toBe("quantity");
    expect(component.storageMismatch).toBe(false);
});

test("read-only and busy views cannot stage storage changes", () => {
    const component = desk();
    component.props.data.can_edit = false;
    component.pickStorage("amount");
    expect(component.setupDirty).toBe(false);
    component.props.data.can_edit = true;
    component.state.busy = true;
    component.pickStorage("amount");
    expect(component.setupDirty).toBe(false);
});

test("correcting a value type need not recreate existing text storage", () => {
    const component = desk();
    component.kindChanged({target: {value: "text"}});
    expect(component.storageMismatch).toBe(false);
    expect(component.state.storage).toBe("");
    expect(component.setupDirty).toBe(true);
});


test("HR context is hidden by default and revealing it does not change data", () => {
    const component = desk({payroll_relevant: true});
    component.props.data.components.push({id: 9, type: "input", payroll_relevant: false, value_kind: "text"});
    expect(component.visibleRows.map(r => r.id)).toEqual([7]);
    component.state.showContext = true;
    component.select(component.props.data.components[1]);
    expect(component.visibleRows.map(r => r.id)).toEqual([7, 9]);
    component.toggleContext({target: {checked: false}});
    expect(component.selected.id).toBe(7);
    expect(component.state.kind).toBe("money");
    expect(component.props.data.components.length).toBe(2);
});
