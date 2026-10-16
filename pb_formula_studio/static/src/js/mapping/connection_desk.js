/** @odoo-module **/
import { Component, useState, onWillUpdateProps } from "@odoo/owl";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { JourneyBoard } from "./journey_board";
import { srcLabel } from "../source_vocab";
import { formatComponentValue } from "../value_format";

const MODEL = "pb.formula.studio";
export class ConnectionDesk extends Component {
    static template = "pb_formula_studio.ConnectionDesk";
    static components = { JourneyBoard };
    static props = { data: Object, configId: Number, componentId: {type:Number, optional:true},
        onOpenDoor: Function, onRefresh: Function, onNewRule: Function };
    setup() {
        this.orm = useService("orm"); this.notif = useService("notification");
        this.state = useState({q:"", filter:"all", selected:this.props.componentId || 0, tab:"sources",
            busy:false, error:"", trace:null, priority:null, draft:null, kind:"", role:"", storage:""});
        // OWL t-set scopes can inherit the component. Keep all mutations on it.
        for (const name of Object.getOwnPropertyNames(ConnectionDesk.prototype)) {
            const d = Object.getOwnPropertyDescriptor(ConnectionDesk.prototype, name);
            if (name !== "constructor" && name !== "setup" && typeof d.value === "function") this[name] = this[name].bind(this);
        }
        this.select(this.selected);
        useHotkey("escape", () => { if(this.state.busy)return; this.state.trace=null;this.state.priority=null;this.state.draft=null; });
        onWillUpdateProps((next) => {
            if (next.configId !== this.props.configId) {
                this.state.selected = 0; this.state.q = ""; this.state.priority = null; this.state.trace = null;
            }
            const row = next.data.components.find(r => r.id === this.state.selected) || next.data.components[0];
            if (row) { this.state.selected = row.id; this.state.kind = row.value_kind; this.state.role = row.net_role || ""; this.state.storage = ""; }
        });
    }
    get rows() { return this.props.data.components || []; }
    get selected() { return this.rows.find(r => r.id === this.state.selected) || this.rows[0] || null; }
    get filtered() {
        const q = this.state.q.trim().toLocaleLowerCase();
        return this.rows.filter(r => (!q || `${r.name} ${r.code} ${r.col}`.toLocaleLowerCase().includes(q)) &&
            (this.state.filter === "all" || (this.state.filter === "missing" ? this.isMissing(r) : r.sources.length > 1)));
    }
    get missingCount() { return this.rows.filter(r => this.isMissing(r)).length; }
    get multipleCount() { return this.rows.filter(r => r.sources.length > 1).length; }
    get sampleName() { const p=this.props.data; return (p.samples.find(s => s.id === p.preview.sample_id) || {}).name || ""; }
    isMissing(row) { return row.type === "input" && row.sources[0].kind === "none"; }
    label(kind) { return srcLabel(kind); }
    kindLabel(kind) { return (this.props.data.kinds.find(k => k.value === kind) || {}).label || kind; }
    laneLabel(k) { return {api:_t("Connected systems"),excel:_t("Spreadsheets"),records:_t("Employee & contract records")}[k]; }
    value(row) { return formatComponentValue(row, this.props.data.preview.values[row.col], this.props.data.config.currency); }
    select(row) { if (!row) return; this.state.selected=row.id; this.state.kind=row.value_kind; this.state.role=row.net_role || ""; this.state.storage=""; this.state.error=""; }
    trap(ev) {
        if(ev.key!=="Tab")return;
        const nodes=[...ev.currentTarget.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex="0"]')].filter(el=>el.getClientRects().length);
        const first=nodes[0],last=nodes[nodes.length-1];
        if(ev.shiftKey && document.activeElement===first){ev.preventDefault();last?.focus();}
        else if(!ev.shiftKey && document.activeElement===last){ev.preventDefault();first?.focus();}
    }
    open(mode) { const r=this.selected; this.props.onOpenDoor({mode, focus:r ? r.code : "", componentId:r ? r.id : 0}); }
    async run(action) {
        if (this.state.busy) return;
        this.state.busy=true; this.state.error="";
        try { await action(); } catch(e) { this.state.error=e.data?.message || e.message || _t("This change could not be saved. Try again."); }
        finally { this.state.busy=false; }
    }
    async saveSetup() {
        await this.run(async () => {
            await this.orm.call(MODEL,"mapping_component_setup",[this.props.configId,this.selected.id,this.state.kind,this.state.role,this.state.storage || null]);
            await this.props.onRefresh(); this.notif.add(_t("Component setup saved."),{type:"success"});
        });
    }
    pickStorage(storage) { this.state.storage=storage; this.state.kind=storage === "text" ? "text" : "money"; if(storage === "text")this.state.role=""; }
    kindChanged(ev) { this.state.kind=ev.target.value; if (!this.props.data.kinds.find(k=>k.value===this.state.kind)?.money) this.state.role=""; }
    get roleOptions() { const money=this.props.data.kinds.find(k=>k.value===this.state.kind)?.money; return this.props.data.pay_roles.filter(r=>money || !r.key || ["info","information","ignore"].includes(r.key)); }
    async trace() {
        await this.run(async()=> { const data=await this.orm.call(MODEL,"journey_data",[this.props.configId]);
            if (!data.ok) throw new Error(_t("The journey could not be loaded."));
            this.state.trace={data, id:this.selected.id}; });
    }
    traceDoor(door) { this.state.trace=null; this.props.onOpenDoor(door); }
    async priorities() {
        const p=this.props.data.priority;
        this.state.priority={order:[...p.order], affected:null, token:p.token};
        await this.reviewPriority();
    }
    async reviewPriority() {
        const p=this.state.priority; if(!p)return;
        const order=[...p.order]; p.affected=null;
        await this.run(async()=> { const result=await this.orm.call(MODEL,"mapping_priority_preview",[this.props.configId,order]);
            if(this.state.priority===p && p.order.join()===order.join()) {p.affected=result.affected;p.token=result.token;} });
    }
    async moveLane(index, delta) {
        const order=this.state.priority.order, to=index+delta;
        if(to<0 || to>=order.length || this.state.busy)return;
        [order[index],order[to]]=[order[to],order[index]]; await this.reviewPriority();
    }
    async savePriority() {
        const p=this.state.priority; if(!p || !p.affected)return;
        await this.run(async()=> { await this.orm.call(MODEL,"mapping_priority_save",[this.props.configId,p.order,p.token]);
            this.state.priority=null; await this.props.onRefresh();
            this.notif.add(_t("Source order saved for this scheme."),{type:"success"}); });
    }
    newComponent() { this.state.draft={name:"", kind:"money", storage:""}; this.state.error=""; }
    async createComponent() {
        if(!this.state.draft?.name.trim())return;
        await this.run(async()=> { const d=this.state.draft;
            const result=await this.orm.call(MODEL,"mapping_component_create",[this.props.configId,d.name,d.kind,d.storage || null]);
            this.state.selected=result.rule_id; this.state.draft=null; await this.props.onRefresh();
            this.notif.add(_t("Component created. Choose its source next."),{type:"success"}); });
    }
}
