/** @odoo-module **/
// Value type is the shared contract used by Treatment, Studio and printed pay.
export function formatComponentValue(component, value, currency = '', labels = {}) {
    if (value === null || value === undefined || value === '') return '—';
    const c = component || {}, kind = c.value_kind;
    if (c.is_text_component || ['identifier', 'text', 'string', 'date'].includes(kind)) return String(value);
    if (kind === 'boolean') {
        if ([true, 1, '1', 'true', 'True'].includes(value)) return labels.yes || 'Yes';
        if ([false, 0, '0', 'false', 'False'].includes(value)) return labels.no || 'No';
        return String(value);
    }
    const number = Number(value);
    if (!Number.isFinite(number)) return String(value);
    const format = {quantity: 'number', decimal: 'number', integer: 'integer', rate: 'percentage'}[kind] || c.number_format || (kind === 'money' ? 'currency' : 'number');
    const options = {maximumFractionDigits: format === 'currency' || format === 'integer' ? 0 : 2};
    if (format === 'percentage') return (number * 100).toLocaleString('en-US', options) + '%';
    const output = Math.abs(number).toLocaleString('en-US', options);
    return (number < 0 ? '−' : '') + (format === 'currency' ? currency : '') + output;
}
export function componentInputType(c) {
    if (c.is_text_component || ['text', 'identifier', 'boolean'].includes(c.value_kind)) return 'text';
    return c.value_kind === 'date' ? 'date' : 'number';
}
