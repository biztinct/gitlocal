/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { NewHireStudio } from "@pb_new_hire/js/new_hire_studio";
import { StepDocs } from "@pb_new_hire/js/step_docs";
import { DOC_CHOICES, MODEL } from "@pb_new_hire/js/studio_util";

if (!DOC_CHOICES.includes("joining")) DOC_CHOICES.push("joining");
patch(NewHireStudio.prototype, {
    get sendDraft() {
        const draft=super.sendDraft;
        if (this.nh.draft.joining_id) draft.joining_id=this.nh.draft.joining_id;
        return draft;
    },
    refreshDocs() {
        if (!this.nh.draft.joining_id) return super.refreshDocs(...arguments);
        this.later("docs",150,()=>this.ask("docs","details_options",[this.sendDraft],data=>{this.nh.docs=data;}));
    },
    async openOfferDoor() {
        const id=this.props.action?.context?.joining_id || this.props.action?.params?.joining_id;
        if (!id || this.joiningDoorDone) return super.openOfferDoor(...arguments);
        this.joiningDoorDone=true;
        if (this.nh.draft.name && this.nh.draft.joining_id!==id) {
            if (!await this.ask_({title:_t("Keep your unsent hire?"),body:_t("Open this joining in Add employee or carry on with your unsent hire."),
                ok:_t("Open joining"),cancel:_t("Keep unsent hire")})) return;
            this.again();
        }
        await this.bringJoining(id);
    },
    async bringAcross(id) {
        const row=this.nh.offers?.find(o=>o.offer_id===id);
        if (row?.joining?.checked) return this.bringJoining(row.joining.id);
        return super.bringAcross(...arguments);
    },
    async bringJoining(id) {
        const res=await this.orm.call(MODEL,"joining_draft",[id]);
        if (!res.ok) {this.toast(res.message,{kind:"error"});return false;}
        const d=res.draft;
        if (res.offer) {this.nh.offer=res.offer;this.setSource("hire");}
        this.applyOfferPay(d);
        this.patch({...d,wage:d.wage || null});
        if (d.department_id) await this.pickTeam(d.department_id,{initial:true,keepCountry:true});
        const [docs, welcome] = await Promise.all([
            this.orm.call(MODEL, "details_options", [this.sendDraft]),
            this.orm.call(MODEL, "welcome_options", [this.sendDraft]),
        ]);
        this.nh.docs = docs;
        this.nh.welcome = welcome;
        const keys=["who","role","pay","sched","docs","welcome"];
        for (const key of keys) this.nh.seen[key]=true;
        await this.go(keys.find(k=>this.status(k).state==="warn") || "check");
        this.persist();
        return true;
    },
    status(key) {
        const result=super.status(...arguments);
        if (!this.nh.draft.joining_id || result.state!=="done") return result;
        const lines={who:_t("From Hiring"),role:_t("From Hiring"),pay:_t("From the signed offer"),
            sched:_t("Team defaults"),docs:_t("From %s, checked by you",this.first),welcome:_t("Checklist is ready")};
        if (!this.nh.draft.offer_id && ["who","role","pay"].includes(key))return result;
        return {...result,text:lines[key] || result.text};
    },
});
patch(StepDocs.prototype, {
    options(item) {
        const options=super.options(...arguments);
        if (!item.joining)return options;
        return [{key:"joining",label:item.joining.label,on:true,why:""},...options];
    },
    rowSub(item) {
        if(item.joining && this.choice(item)==="joining")return item.joining.line;
        return super.rowSub(...arguments);
    },
});
