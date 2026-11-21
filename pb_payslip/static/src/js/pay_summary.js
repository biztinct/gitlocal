/** @odoo-module **/

/** A part-to-whole bar is meaningful only for a reconciled, positive gross. */
export function paySummary(data) {
    const { gross, deductions_total: deductions, net } = data;
    const adjustment = data.adjustment || 0;
    const rounding = Number(data.currency_rounding) > 0 ? Number(data.currency_rounding) : 0.01;
    const finite = [gross, deductions, net, adjustment].every(Number.isFinite);
    const canSplit = finite && gross > 0 && deductions >= 0 && net >= 0
        && deductions <= gross && net <= gross && adjustment === 0
        && Math.abs(gross - deductions - net) < rounding / 2 + Number.EPSILON * Math.abs(gross);
    return {
        canSplit,
        deductionPercent: canSplit ? deductions / gross * 100 : 0,
        netPercent: canSplit ? net / gross * 100 : 0,
    };
}

export function statementMoney(value, data) {
    const amount = Number.isFinite(value) ? value : 0;
    const precision = Number.isInteger(data.currency_precision)
        ? Math.max(0, Math.min(6, data.currency_precision)) : 2;
    const digits = Math.abs(amount).toLocaleString('en-US', {
        minimumFractionDigits: 0, maximumFractionDigits: precision,
    });
    return (amount < 0 ? '−' : '') + (data.currency || '₫') + digits;
}

export function statementChange(value, data) {
    return (value > 0 ? '+' : value < 0 ? '−' : '') + statementMoney(Math.abs(value || 0), data);
}
