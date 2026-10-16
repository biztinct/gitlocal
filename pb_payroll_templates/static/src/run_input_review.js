/** @odoo-module **/
import { Component, useState, onWillStart } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { patch } from '@web/core/utils/patch';
import { Dialog } from '@web/core/dialog/dialog';
import { ConfirmationDialog } from '@web/core/confirmation_dialog/confirmation_dialog';
import { _t } from '@web/core/l10n/translation';
import { PayrunWizard } from '@pb_payrun_wizard/js/payrun_wizard';
import { PbPayruns } from '@pb_payruns/js/payruns';
import { columnLetter } from './monthly_review';

const normalize = v => String(v ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const STATUS = {pending: _t('Choose what happens next'), excel: _t('Excel only · enter again next payroll'),
    same: _t('Matches the record'), saved: _t('Saved for future payrolls'), once: _t('This payroll only'),
    approval: _t('Record update awaiting approval'), blocked: _t('Needs attention')};

export class RunInputReview extends Component {
    static template = 'pb_payroll_templates.RunInputReview';
    static components = {Dialog};
    static props = {runId: Number, close: Function};
    setup() {
        this.orm = useService('orm'); this.dialog = useService('dialog'); this.action = useService('action');
        this.state = useState({data: null, busy: false, error: '', sheet: 0, query: '', field: '', filter: 'all', page: 0, selected: {}, note: ''});
        onWillStart(() => this.load());
    }
    async load() {
        this.state.busy = true; this.state.error = '';
        try { this.state.data = await this.orm.call('pb.payroll.templates', 'run_input_changes', [this.props.runId]); this.state.selected = {}; }
        catch (e) { this.state.error = e.data?.message || e.message || _t('The review could not be loaded. Try refreshing.'); }
        finally { this.state.busy = false; }
    }
    get sheet() { return this.state.data?.sheets[this.state.sheet]; }
    key(row, col) { return `${row.line_id}:${col.id}`; }
    status(cell) { return STATUS[cell.decision] || ''; }
    value(v) { return v === null || v === undefined || v === '' ? '—' : typeof v === 'number' ? v.toLocaleString(undefined, {maximumFractionDigits: 6}) : String(v); }
    letter(i) { return columnLetter(i + 2); }
    get stats() {
        const s = {pending: 0, excel: 0, saved: 0, once: 0, approval: 0, people: 0};
        for (const sheet of this.state.data?.sheets || []) {
            for (const row of sheet.rows) { let changed = false; for (const c of Object.values(row.cells)) {
                if (c.decision in s) s[c.decision]++; changed ||= c.changed;
            } s.people += Number(changed); }
        }
        return s;
    }
    matches(cell) {
        return !!cell && (this.state.filter === 'all' || this.state.filter === 'changed' && cell.changed || this.state.filter === cell.decision);
    }
    get columns() {
        const q = normalize(this.state.field);
        return (this.sheet?.columns || []).filter(c => (!q || normalize(c.label + ' ' + c.code).includes(q)) &&
            (this.state.filter === 'all' || this.sheet.rows.some(r => this.matches(r.cells[c.id]))));
    }
    get matchingRows() {
        const q = normalize(this.state.query);
        return (this.sheet?.rows || []).filter(r => (!q || normalize(r.name + ' ' + r.code).includes(q)) && this.columns.some(c => this.matches(r.cells[c.id])));
    }
    get rows() { return this.matchingRows.slice(this.state.page * 30, (this.state.page + 1) * 30); }
    get pages() { return Math.max(1, Math.ceil(this.matchingRows.length / 30)); }
    get selected() { return Object.keys(this.state.selected).filter(k => this.state.selected[k]); }
    get canDecide() { return this.state.data?.can_decide && !this.state.busy; }
    toggle(row, col) { const k = this.key(row, col); this.state.selected[k] = !this.state.selected[k]; }
    selectVisible() {
        for (const row of this.matchingRows) for (const col of this.columns) {
            if (row.cells[col.id]?.decision === 'pending' && !row.cells[col.id].payroll_changed && !row.cells[col.id].not_computed) this.state.selected[this.key(row, col)] = true;
        }
    }
    selectColumn(col) {
        for (const row of this.matchingRows) {
            if (row.cells[col.id]?.decision === 'pending' && !row.cells[col.id].payroll_changed && !row.cells[col.id].not_computed) this.state.selected[this.key(row, col)] = true;
        }
    }
    async download() {
        this.state.error = '';
        try {
            const data = await this.orm.call('pb.payroll.templates', 'export_run_input_changes', [this.props.runId, this.sheet.id]);
            const bytes = Uint8Array.from(atob(data.file_b64), c => c.charCodeAt(0));
            const url = URL.createObjectURL(new Blob([bytes], {type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}));
            const a = document.createElement('a'); a.href = url; a.download = data.filename; a.click(); URL.revokeObjectURL(url);
        } catch (e) { this.state.error = e.data?.message || e.message || _t('The review could not be downloaded.'); }
    }
    openRecords() {
        const configId = this.sheet.config_id;
        this.props.close();
        this.action.doAction('pb_records.action_pb_records_desk', {additionalContext: {records_config_id: configId}});
    }
    changeSheet(ev) { this.state.sheet = Number(ev.target.value); this.state.selected = {}; this.state.page = 0; }
    setFilter(filter) { this.state.filter = filter; this.state.page = 0; }
    decide(decision) {
        const keys = this.selected;
        if (!keys.length || !this.canDecide) return;
        this.dialog.add(ConfirmationDialog, {
            title: decision === 'future' ? _t('Keep these values for future payrolls?') : _t('Use these values only in this payroll?'),
            body: decision === 'future'
                ? _t('%s selected values will be sent through your record-update approval route. Once approved, they become employee or contract records used by future payrolls. This payroll’s computed payslips stay as they are.', keys.length)
                : _t('%s selected values will stay specific to this payroll. Employee and contract records stay as they are. This decision is visible to other payroll reviewers.', keys.length),
            confirmLabel: decision === 'future' ? _t('Keep for future payrolls') : _t('This payroll only'),
            confirm: () => this.apply(keys, decision),
        });
    }
    async apply(keys, decision) {
        this.state.busy = true; this.state.error = '';
        try {
            this.state.data = await this.orm.call('pb.payroll.templates', 'decide_run_inputs',
                [this.props.runId, this.sheet.id, this.sheet.revision, keys, decision, this.state.note]);
            this.state.selected = {}; this.state.note = ''; this.state.page = 0;
        } catch (e) { this.state.error = e.data?.message || e.message || _t('The choice could not be saved. Refresh the review and try again.'); }
        finally { this.state.busy = false; }
    }
}

class RunInputReviewAction extends Component {
    static template = 'pb_payroll_templates.RunInputReviewAction';
    static components = {RunInputReview}; static props = ['*'];
    setup() { this.action = useService('action'); }
    get runId() { return this.props.action.params.run_id; }
    close() { this.action.doAction({type: 'ir.actions.act_window', res_model: 'hr.payslip.run', res_id: this.runId, views: [[false, 'form']]}); }
}
registry.category('actions').add('pb_payroll_input_changes', RunInputReviewAction);

patch(PayrunWizard.prototype, {
    // This addon owns the durable choice. The basic wizard still works on
    // databases where Payroll Templates is not installed.
    get sheetOnce() { return true; },
    get sheetContinueLabel() { return _t('Compute with this file'); },
    openInputChanges() { this.dialog.add(RunInputReview, {runId: this.state.summary.run_id}); },
});
patch(PbPayruns.prototype, {
    openInputChanges(b) { this.action.doAction({type: 'ir.actions.client', tag: 'pb_payroll_input_changes', params: {run_id: b.id}}); },
});
