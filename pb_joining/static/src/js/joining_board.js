/** @odoo-module **/
import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "./joining_icons";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbHiringHub } from "@pb_hiring/js/hiring_hub";

const MODEL = "pb.joining.board";
const PEOPLE = "pb_people_hub.action_pb_people_hub";
const STUDIO = "pb_new_hire.action_new_hire_studio";
const groups = ["base.group_user"]; // The probe checks HR, Lifecycle, Hiring and role-specific managers.

export class PbJoiningBoard extends Component {
    static template = "pb_joining.Board";
    static components = { PbFilterLayout };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notify = useService("notification");
        this.state = useState({ head: null, rows: [], total: 0, drawer: null, mode: "", form: {},
            options: {}, msg: "", error: "", code: "", clear: {}, noteKey: "", note: "", busy: false, loaded: false });
        this.epoch = 0;
        this.timers = new Set();
        this.kit = useFilterKit({ model: MODEL, defer: true, noun: _t("people joining"), onChange: () => this.page() });
        onWillStart(async () => {
            this.state.head = await this.call("get_board");
            if (!this.state.head.allowed) return;
            if (this.state.head.steps.to_check) this.kit.initial = {filters: {step:["to_check"]}};
            await this.kit.load();
        });
        onWillUnmount(() => { this.epoch++; this.timers.forEach(clearTimeout); });
    }
    ic(name, size=16) { return ic(name,size); }
    call(method,args=[],kwargs={}) { return this.orm.call(MODEL,method,args,kwargs); }
    get formTitle() {
        return {one:this.state.drawer?.name, day:_t("First-day details"), date:_t("Change the first day"),
            cancel:_t("They are not joining"), invite:_t("Invite someone"), settings:_t("Papers to sign")}[this.state.mode];
    }
    get submitLabel() {
        return this.state.mode==="invite" ? _t("Invite") : this.state.mode==="cancel" ? _t("Close the link") : _t("Save");
    }
    get searchLabel() { return _t("Search by name, job or team"); }
    get stepLabel() { return _t("Where everyone is before day one"); }
    get steps() {
        const rows = [
            ["invited",_t("Invited"),_t("Offer signed. The link has gone out.")],
            ["filling",_t("Filling in"),_t("They have started. Reminders run by themselves.")],
            ["to_check",_t("Ready for you to check"),_t("Everything sent. Nothing is in the employee record yet.")],
            ["added",_t("Ready for day one"),_t("Checked and added as an employee.")],
        ];
        return rows.map(([key,title,sub],i) => {
            const count = this.state.head?.steps[key] || 0;
            return {key,title,sub,n:String(i+1).padStart(2,"0"),count,countLabel:String(count),on:this.kit.isOn("step",key)};
        });
    }
    get glance() {
        const k = this.state.head?.kpis || {};
        return [["joining",_t("joining in the next 30 days"),"",{}],
            ["to_check",_t("waiting for your check"),"",{step:["to_check"]}],
            ["at_risk",_t("at risk of missing first pay"),"rose",{flags:["risk"]}],
            ["pass_on",_t("link to pass on"),"amber",{flags:["pass"]}],
            ["started_week",_t("started filling in this week"),"green",{step:["filling"]}]]
            .map(([key,label,tone,filters]) => ({key,n:k[key]||0,label,tone,run:()=>this.kit.setFilters(filters)}));
    }
    async page(more=false) {
        if (!this.state.head?.allowed) return;
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        const d = await this.call("get_page",[],{filters:q.filters,search:q.search,sort:q.sort,offset,limit:30});
        if (!this.kit.isCurrent(q.seq)) return;
        this.state.rows = more ? [...this.state.rows,...d.rows] : d.rows;
        this.state.total = d.total;
        this.state.loaded = true;
    }
    async refresh() {
        this.state.head = await this.call("get_board");
        await this.page();
    }
    async run(fn) {
        if (this.state.busy) return;
        this.state.busy=true;
        this.state.error="";
        this.state.msg="";
        try { await fn(); }
        catch(e) {
            this.state.error = e.data?.message || e.message || _t("That did not save. Try again.");
            if (!this.state.mode) this.notify.add(this.state.error,{type:"warning"});
        } finally { this.state.busy=false; }
    }
    onKey(ev) { if (ev.key==="Escape") this.closeDrawer(); }
    closeDrawer() { if (!this.state.busy) this.dismiss(); }
    askBack(key) { this.state.noteKey=key; this.state.note=""; }
    dismiss() {
        this.epoch++;
        this.timers.forEach(clearTimeout);
        this.timers.clear();
        Object.assign(this.state,{drawer:null,mode:"",msg:"",error:"",noteKey:"",note:"",code:"",clear:{},form:{}});
    }
    async open(id) {
        this.dismiss();
        const epoch=this.epoch;
        await this.run(async()=>{
            const d=await this.call("get_one",[id]);
            if (epoch===this.epoch) Object.assign(this.state,{drawer:d,mode:"one"});
        });
    }
    review(method,key) {
        const d=this.state.drawer;
        this.run(async()=>{
            const args=[d.id];
            if(key) args.push(key);
            if(method==="send_back") args.push(this.state.note);
            args.push(d.revision);
            const result=await this.call(method,args);
            this.state.drawer=result;
            this.state.msg=result.message || _t("Saved");
            this.state.noteKey="";
            this.state.note="";
            this.state.clear={};
            await this.refresh();
        });
    }
    reveal(item,field) {
        const id=this.state.drawer.id;
        const epoch=this.epoch;
        const key=item.key+"/"+field.key;
        this.run(async()=>{
            const result=await this.call("reveal",[id,item.key,field.key]);
            if(epoch!==this.epoch) return;
            this.state.clear[key]=result.value;
            const timer=setTimeout(()=>{ delete this.state.clear[key]; this.timers.delete(timer); },30000);
            this.timers.add(timer);
        });
    }
    async copy(value) {
        await navigator.clipboard.writeText(value);
    }
    link(method) {
        const id=this.state.drawer.id;
        const epoch=this.epoch;
        this.run(async()=>{
            const r=await this.call(method,[id]);
            if(epoch!==this.epoch) return;
            if (r.url) { await this.copy(r.url); this.state.msg=_t("Link copied."); }
            if (r.code) this.state.code=r.code;
            if (r.message) { await this.copy(r.message); this.state.msg=_t("Message copied. Paste it into WhatsApp or a text."); }
            if (r.sent) this.state.msg=_t("Message sent.");
            this.state.drawer=await this.call("get_one",[id]);
            await this.refresh();
        });
    }
    copyCode() { this.run(async()=>{await this.copy(this.state.code);this.state.msg=_t("Code copied.");}); }
    get codeLabel() { const c=this.state.code; return c.slice(0,3)+" "+c.slice(3); }
    get linkText() {
        const l=this.state.drawer.link;
        return l.mode==="email" ? _t("Link emailed to %s on %s.",l.masked,l.sent_at) :
            _t("This site cannot send email. Pass the link and a code to %s yourself.",this.state.drawer.name.split(" ")[0]);
    }
    itemState(item) {
        if(this.state.drawer.state==="added" && item.state==="accepted") return _t("In the record");
        if(item.state==="later")return item.none ? _t("They do not have one yet") : _t("They will add it later");
        return {empty:_t("Not sent yet"),saved:_t("Sent"),accepted:_t("Accepted"),returned:_t("Sent back to fix")}[item.state];
    }
    startForm(mode) {
        this.state.code=""; this.state.clear={}; this.state.msg=""; this.state.error="";
        this.run(async()=>{
            if(mode==="invite") {
                this.state.drawer=null;
                this.state.options=await this.call("invite_options");
                this.state.form={name:"",first_day:"",payroll_country:"",job_title:"",phone:"",email:"",manager_id:"",department_id:"",lang:"en_US"};
            } else if(mode==="settings") {
                this.state.drawer=null; this.state.form=await this.call("settings");
            } else if(mode==="day") this.state.form={...this.state.drawer.day};
            else this.state.form={date:this.state.drawer.first_day,reason:""};
            this.state.mode=mode;
        });
    }
    submitForm() {
        this.run(async()=>{
            const mode=this.state.mode, f={...this.state.form}, d=this.state.drawer;
            if(mode==="invite") {
                for(const key of ["manager_id","department_id"]) f[key]=Number(f[key])||false;
                const r=await this.call("invite",[f]);
                this.state.drawer=await this.call("get_one",[r.id]);this.state.mode="one";
                this.state.msg=r.mode==="email"?this.linkText:_t("Copy the link and show a code to pass on.");
            } else if(mode==="settings") { await this.call("settings",[f]);this.state.msg=_t("Saved"); }
            else if(mode==="cancel") { await this.call("not_joining",[d.id,f.reason]);this.dismiss(); }
            else {
                this.state.drawer=mode==="day"?await this.call("set_day",[d.id,f]):await this.call("change_first_day",[d.id,f.date,f.reason]);
                this.state.mode="one";this.state.msg=_t("Saved");
            }
            await this.refresh();
        });
    }
    backForm() { if(this.state.drawer){this.state.mode="one";this.state.error="";}else this.dismiss(); }
    openStudioSettings() { return this.action.doAction(STUDIO,{additionalContext:{pb_joining_paper_settings:true}}); }
    openJoiners() { return this.action.doAction(PEOPLE,{additionalContext:{pb_hub_lens:"newjoiners"}}); }
    addEmployee() { this.run(async()=>{const a=await this.call("studio_door",[this.state.drawer.id]);await this.action.doAction(a);}); }
}
const lens={key:"joining",icon:"userPlus",label:_t("Joining"),title:_t("Joining"),Component:PbJoiningBoard,
            groups,probe:{model:MODEL,method:"can_open"}};
registry.category("pb_hiring_hub_lens").add("joining",lens,{sequence:30});
registry.category("pb_people_hub_lens").add("joining",{...lens,feature:"lifecycle"},{sequence:51});
registry.category("actions").add("pb_joining_board",PbJoiningBoard);
registry.category("pb_hub_palette").add("joining_board",{id:"joining_board",label:_t("Joining"),
    sublabel:_t("People who have signed and not yet started"),icon:"userPlus",groups,requires:"pb_joining_board",probe:lens.probe,
    action:{xmlid:PEOPLE,lens:"joining"},keywords:["joining","joiner","new starter"]},{sequence:2510});
// Hiring appends registry lenses after Set-up. Insert our own lens immediately after Offers.
patch(PbHiringHub.prototype,{setup(){
    super.setup(...arguments);
    const lenses=this.config.lenses;
    const index=lenses.findIndex(l=>l.key==="joining");
    if(index>=0){const [joining]=lenses.splice(index,1);lenses.splice(lenses.findIndex(l=>l.key==="offers")+1,0,joining);}
}});
