/** @odoo-module **/

/**
 * Small DOM kernel for the Payslip Studio rich editor.
 *
 * These helpers deliberately know nothing about OWL.  The contenteditable
 * subtree is browser-owned, so table editing stays synchronous and testable
 * without asking the virtual DOM to reconcile cells that users created.
 */

function rowsFor(table) {
    return table
        ? Array.from(table.rows || []).filter(row => row.closest("table") === table)
        : [];
}

function emptyCellLike(source) {
    const cell = document.createElement(source && source.tagName === "TH" ? "th" : "td");
    for (const name of ["colspan", "rowspan", "scope"]) {
        const value = source && source.getAttribute(name);
        if (value) cell.setAttribute(name, value);
    }
    if (source && source.style) cell.style.cssText = source.style.cssText;
    cell.innerHTML = "<br>";
    return cell;
}

function blankSplitCell(source) {
    const cell = emptyCellLike(source);
    cell.removeAttribute("colspan");
    cell.removeAttribute("rowspan");
    return cell;
}

function hasMeaningfulContent(cell) {
    return Array.from(cell.childNodes).some(node =>
        node.nodeType === Node.TEXT_NODE
            ? Boolean(node.textContent.trim())
            : node.nodeName !== "BR");
}

function appendMergedContent(cell, neighbour) {
    const sourceHasContent = hasMeaningfulContent(neighbour);
    if (!sourceHasContent) return;
    if (!hasMeaningfulContent(cell)) cell.innerHTML = "";
    else cell.appendChild(document.createElement("br"));
    while (neighbour.firstChild) cell.appendChild(neighbour.firstChild);
}

const BORDER_PRESETS = {
    light: "1px solid #E2E8F0",
    standard: "1px solid #94A3B8",
    strong: "2px solid #475569",
};

const BORDER_STYLE_PROPERTIES = [
    "border", "border-width", "border-style", "border-color", "border-image",
];

function cleanEmptyStyle(element) {
    if (element && !element.getAttribute("style")) element.removeAttribute("style");
}

export function payslipTableContext(cell) {
    const row = cell && cell.closest && cell.closest("tr");
    const table = row && row.closest("table");
    if (!cell || !row || !table || cell.closest("table") !== table) return null;
    const rows = rowsFor(table);
    const rowIndex = rows.indexOf(row);
    const cellIndex = Array.from(row.cells).indexOf(cell);
    if (rowIndex < 0 || cellIndex < 0) return null;
    return {
        cell, row, table, rows, rowIndex, cellIndex,
        columnCount: Math.max(0, ...rows.map(item => item.cells.length)),
    };
}

export function insertPayslipTableRow(cell, after = false) {
    const context = payslipTableContext(cell);
    if (!context) return null;
    const newRow = document.createElement("tr");
    const sources = Array.from(context.row.cells);
    for (const source of sources) newRow.appendChild(emptyCellLike(source));
    context.row.parentNode.insertBefore(newRow, after ? context.row.nextSibling : context.row);
    return newRow.cells[Math.min(context.cellIndex, newRow.cells.length - 1)] || null;
}

export function insertPayslipTableColumn(cell, after = false) {
    const context = payslipTableContext(cell);
    if (!context) return null;
    let selected = null;
    for (const row of context.rows) {
        const cells = Array.from(row.cells);
        const source = cells[Math.min(context.cellIndex, cells.length - 1)] || context.cell;
        const newCell = emptyCellLike(source);
        const insertAt = Math.min(context.cellIndex + (after ? 1 : 0), cells.length);
        row.insertBefore(newCell, row.cells[insertAt] || null);
        if (row === context.row) selected = newCell;
    }
    return selected;
}

export function deletePayslipTableRow(cell) {
    const context = payslipTableContext(cell);
    if (!context) return null;
    if (context.rows.length <= 1) {
        context.table.remove();
        return null;
    }
    const fallbackRow = context.rows[context.rowIndex + 1] || context.rows[context.rowIndex - 1];
    context.row.remove();
    return fallbackRow.cells[Math.min(context.cellIndex, fallbackRow.cells.length - 1)] || null;
}

export function deletePayslipTableColumn(cell) {
    const context = payslipTableContext(cell);
    if (!context) return null;
    if (context.columnCount <= 1) {
        context.table.remove();
        return null;
    }
    for (const row of context.rows) {
        if (row.cells[context.cellIndex]) row.cells[context.cellIndex].remove();
    }
    const remaining = Array.from(context.row.cells);
    return remaining[Math.min(context.cellIndex, remaining.length - 1)] || null;
}

export function deletePayslipTable(cell) {
    const context = payslipTableContext(cell);
    if (!context) return false;
    context.table.remove();
    return true;
}

export function mergePayslipTableCellRight(cell) {
    const context = payslipTableContext(cell);
    if (!context) return null;
    const neighbour = context.row.cells[context.cellIndex + 1];
    if (!neighbour || neighbour.rowSpan !== context.cell.rowSpan) return null;
    appendMergedContent(context.cell, neighbour);
    context.cell.colSpan += neighbour.colSpan;
    neighbour.remove();
    return context.cell;
}

export function mergePayslipTableCellDown(cell) {
    const context = payslipTableContext(cell);
    if (!context) return null;
    const targetRow = context.rows[context.rowIndex + context.cell.rowSpan];
    const neighbour = targetRow && targetRow.cells[context.cellIndex];
    if (!neighbour || neighbour.colSpan !== context.cell.colSpan) return null;
    appendMergedContent(context.cell, neighbour);
    context.cell.rowSpan += neighbour.rowSpan;
    neighbour.remove();
    return context.cell;
}

export function splitPayslipTableCell(cell) {
    const context = payslipTableContext(cell);
    if (!context) return null;
    const columnSpan = context.cell.colSpan;
    const rowSpan = context.cell.rowSpan;
    if (columnSpan <= 1 && rowSpan <= 1) return null;

    context.cell.removeAttribute("colspan");
    context.cell.removeAttribute("rowspan");
    let current = context.cell;
    for (let index = 1; index < columnSpan; index++) {
        const blank = blankSplitCell(context.cell);
        current.after(blank);
        current = blank;
    }
    for (let rowOffset = 1; rowOffset < rowSpan; rowOffset++) {
        const row = context.rows[context.rowIndex + rowOffset];
        if (!row) continue;
        const before = row.cells[context.cellIndex] || null;
        for (let columnOffset = 0; columnOffset < columnSpan; columnOffset++) {
            row.insertBefore(blankSplitCell(context.cell), before);
        }
    }
    return context.cell;
}

export function applyPayslipTableBorder(cell, scope = "table", preset = "default") {
    const context = payslipTableContext(cell);
    if (!context || !["cell", "table"].includes(scope)
            || !["default", "none", ...Object.keys(BORDER_PRESETS)].includes(preset)) return 0;
    const cells = context.rows.flatMap(row => Array.from(row.cells));
    const targets = scope === "cell" ? [context.cell] : [context.table, ...cells];
    for (const target of targets) {
        for (const property of BORDER_STYLE_PROPERTIES) target.style.removeProperty(property);
        if (preset === "none") target.style.borderStyle = "none";
        else if (preset !== "default") target.style.border = BORDER_PRESETS[preset];
        cleanEmptyStyle(target);
    }
    if (scope === "table") {
        if (preset === "default") context.table.style.removeProperty("border-collapse");
        else context.table.style.borderCollapse = "collapse";
        cleanEmptyStyle(context.table);
    }
    return targets.length;
}
