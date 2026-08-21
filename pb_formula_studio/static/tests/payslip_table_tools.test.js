/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";
import {
    applyPayslipTableBorder,
    deletePayslipTableColumn,
    deletePayslipTableRow,
    insertPayslipTableColumn,
    insertPayslipTableRow,
    payslipTableContext,
} from "@pb_formula_studio/js/payslip_table_tools";

describe.current.tags("desktop");

function tableFixture() {
    const host = document.createElement("div");
    host.innerHTML = `
        <table><tbody>
            <tr><th style="background-color: rgb(241, 245, 249)">Label</th><th>Value</th></tr>
            <tr><td>Basic salary</td><td><span data-token="1">10</span></td></tr>
        </tbody></table>`;
    document.body.appendChild(host);
    return { host, table: host.querySelector("table") };
}

test("rows can be added above and below without copying live cell content", () => {
    const { host, table } = tableFixture();
    const selected = table.rows[1].cells[1];
    const above = insertPayslipTableRow(selected, false);
    const below = insertPayslipTableRow(selected, true);

    expect(table.rows.length).toBe(4);
    expect(above.tagName).toBe("TD");
    expect(above.textContent).toBe("");
    expect(below.textContent).toBe("");
    expect(table.querySelectorAll("[data-token]").length).toBe(1);
    host.remove();
});

test("columns can be inserted on either side and preserve header cells", () => {
    const { host, table } = tableFixture();
    const selected = table.rows[1].cells[0];
    insertPayslipTableColumn(selected, false);
    const after = insertPayslipTableColumn(selected, true);

    expect(table.rows[0].cells.length).toBe(4);
    expect(table.rows[1].cells.length).toBe(4);
    expect(table.rows[0].cells[0].tagName).toBe("TH");
    expect(after.tagName).toBe("TD");
    host.remove();
});

test("row and column deletion return a safe neighbouring cell", () => {
    const { host, table } = tableFixture();
    const afterRowDelete = deletePayslipTableRow(table.rows[0].cells[0]);
    expect(table.rows.length).toBe(1);
    expect(afterRowDelete).toBe(table.rows[0].cells[0]);

    const afterColumnDelete = deletePayslipTableColumn(table.rows[0].cells[0]);
    expect(table.rows[0].cells.length).toBe(1);
    expect(afterColumnDelete).toBe(table.rows[0].cells[0]);
    host.remove();
});

test("editing a nested table never changes its outer table", () => {
    const { host, table } = tableFixture();
    table.rows[1].cells[0].innerHTML = "<table><tbody><tr><td>Nested A</td><td>Nested B</td></tr></tbody></table>";
    const nested = table.rows[1].cells[0].querySelector("table");
    const nestedCell = nested.rows[0].cells[0];
    const context = payslipTableContext(nestedCell);

    expect(context.table).toBe(nested);
    insertPayslipTableColumn(nestedCell, true);
    expect(nested.rows[0].cells.length).toBe(3);
    expect(table.rows[0].cells.length).toBe(2);
    host.remove();
});

test("border presets can target a whole table and restore defaults", () => {
    const { host, table } = tableFixture();
    const selected = table.rows[1].cells[0];

    expect(applyPayslipTableBorder(selected, "table", "light")).toBe(5);
    expect(table.style.borderStyle).toBe("solid");
    expect(table.style.borderWidth).toBe("1px");
    expect(table.style.borderCollapse).toBe("collapse");
    expect(Array.from(table.querySelectorAll("th, td")).every(cell =>
        cell.style.borderStyle === "solid" && cell.style.borderWidth === "1px")).toBe(true);

    applyPayslipTableBorder(selected, "table", "default");
    expect(table.style.border).toBe("");
    expect(table.style.borderCollapse).toBe("");
    expect(Array.from(table.querySelectorAll("th, td")).every(cell =>
        cell.style.border === "")).toBe(true);
    host.remove();
});

test("no-border preset can target one cell without changing its table", () => {
    const { host, table } = tableFixture();
    const selected = table.rows[1].cells[0];

    expect(applyPayslipTableBorder(selected, "cell", "none")).toBe(1);
    expect(selected.style.border).toBe("none");
    expect(table.rows[1].cells[1].style.border).toBe("");
    expect(table.style.border).toBe("");
    host.remove();
});
