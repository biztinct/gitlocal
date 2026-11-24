/** @odoo-module **/
import { Component, markup, onWillStart, onWillUnmount, onMounted, useState, useSubEnv } from '@odoo/owl';
import { _t } from "@web/core/l10n/translation";
import { formatFloat } from '@web/core/utils/numbers';
const { DateTime } = luxon;
import { registry } from '@web/core/registry';
import { patch } from '@web/core/utils/patch';
import { useService } from '@web/core/utils/hooks';
import { FormViewDialog } from '@web/views/view_dialogs/form_view_dialog';
import { View, getDefaultConfig } from '@web/views/view';
import { PremiumRecordForm } from '@pb_form_studio/js/record_form';
import { PbMission } from '@pb_mission/js/pb_mission';
import { WfDock } from '@pb_mission/js/pb_dock';
import { PbSchedule } from '@pb_schedule/js/pb_schedule';
import { PbShiftPatterns } from '@pb_shift_patterns/js/patterns_board';
import { PbOtDesk } from '@pb_hr_workforce/js/pb_ot_desk';
import { ic } from '@pb_import_kit/js/import_icons';
import { HubBackChip, hubBack } from '@pb_hub/js/hub_nav';
import { PbSettingsHub, SETTINGS_CATEGORIES } from '@pb_settings/js/settings_hub';

const MODEL = 'pb.workforce.workspace';
const GROUPS = [
    {label:'Overview', keys:['overview','today']},
    {label:'Roster', keys:['schedule','rosters']},
    {label:'Shifts & patterns', keys:['shifts','patterns']},
    {label:'People', keys:['people']},
    {label:'Rules & calendars', keys:['policies','rates','ceilings','calendars','holidays']},
    {label:'Timesheets', keys:['time','overtime','close']},
    {label:'Connections', keys:['connectors']},
    {label:'More', keys:['timeoff','approvals','field','insights']},
];
// When the guided Workforce setup screen (`pb_workforce_setup`) is installed
// setup has its own home, so the daily menu keeps only daily work (owner
// ruling R3, WFSETUP P5a). The setup-only lenses stay registered — other
// screens still link to them — they are just not listed in the tabs or in
// "More". Without that module the menu above is unchanged.
const TRIMMED_GROUPS = [
    {label:'Overview', keys:['overview','today']},
    {label:'Roster', keys:['schedule','rosters']},
    {label:'Timesheets', keys:['time','overtime','close']},
    {label:'More', keys:['timeoff','approvals','field','insights']},
];
const SETUP_ONLY = ['shifts','patterns','people','policies','rates','ceilings','calendars','holidays','connectors'];
const STUDIO_TAG = 'pb_workforce_setup_studio';
export function setupStudioInstalled(){return registry.category('actions').contains(STUDIO_TAG);}
// Every label below is translated WHEN IT IS SHOWN (WFSETUP P5c): a `_t` in a
// module-level constant runs before the user's translations are loaded. The
// English group label stays the group's identity (comparisons, keys); the
// screen shows `groupLabel(label)`.
export function groupLabel(label){
    const labels={'Overview':_t("Overview"),'Roster':_t("Roster"),'Shifts & patterns':_t("Shifts & patterns"),
        'People':_t("People"),'Rules & calendars':_t("Rules & calendars"),'Timesheets':_t("Timesheets"),
        'Connections':_t("Connections"),'More':_t("More")};
    return labels[label]||label;
}
export function lensLabels(){return {overview:_t("Factory overview"),today:_t("Today"),schedule:_t("Roster board"),
    rosters:_t("Review roster"),shifts:_t("Shift library"),patterns:_t("Recurring patterns"),people:_t("People & assignments"),
    policies:_t("Attendance policies"),rates:_t("Overtime definitions"),ceilings:_t("Overtime ceilings"),
    calendars:_t("Working calendars"),time:_t("Attendance & hours"),overtime:_t("Overtime approvals"),
    close:_t("Close & send to payroll"),connectors:_t("Data connectors"),setup:_t("Guided setup")};}
const COPY_KEYS = ['shifts','people','policies','rates','ceilings','calendars','connectors','rosters'];
function copy(){return {
    shifts:[_t("Shifts that fit the working day."),_t("Define times and breaks once, then use them in recurring patterns and the roster.")],
    people:[_t("The right schedule for every person."),_t("Review workplace, working calendar, attendance group and calculation policy. Use recurring patterns to assign repeating shifts.")],
    policies:[_t("Clear rules. Explainable hours."),_t("Review shift boundaries, unpaid breaks and additional lateness deductions. Draft policies do not calculate attendance.")],
    rates:[_t("Define how overtime is paid."),_t("Rates and eligibility belong here. Actual overtime is reviewed and approved under Timesheets.")],
    ceilings:[_t("Keep overtime within the agreed limits."),_t("These are the existing ceiling settings used by overtime approval. Zero means a limit is not enforced.")],
    calendars:[_t("Working days, rest days and holidays."),_t("Maintain the working calendars assigned to employees. Keep their normal hours aligned with shift calculation rules.")],
    connectors:[_t("Attendance, connected."),_t("Invite IT and check each source. Collection continues while record issues are reviewed in Payobook.")],
    rosters:[_t("Review the planned work."),_t("Suggested shifts remain drafts until reviewed and published. Open a row for its policy, evidence and calculation preview.")],
};}
/** A count in the user's language (2,402 / 2.402), from the web client's own formatter. */
function fmtNum(n){return formatFloat(Number(n)||0,{digits:[false,0]});}

export class WorkforcePanel extends Component {
    static template = 'pb_workforce_workspace.Panel';
    static components = {PremiumRecordForm, View, HubBackChip};
    static props = {mode:{type:String,optional:true}, '*':true};
    setup() {
        this.dialog=useService('dialog');
        this.orm = useService('orm'); this.action = useService('action'); this.notify = useService('notification');
        this.ctx = useService('wf_context');this.settingsBack=hubBack(this.props);
        this.state = useState({loading:true,error:'',data:null,preferences:null,search:'',offset:0,editor:null,
            location:null, locationName:'',drafts:false, busy:false});
        this.leaveGuard=()=>this.guard();
        this.mode = this.props.mode || this.props.action?.context?.pb_workspace_section || 'setup'; this.form = null;
        this.ready = f => {this.form=f;}; this.saved = () => this.load();
        this.recordContext = {};
        this.off = this.ctx.onChange(() => { if (['overview','rosters'].includes(this.mode) && !this.state.editor) this.load(); });
        useSubEnv({config:{...getDefaultConfig(),noBreadcrumbs:true}});
        onWillStart(async () => {
            this.state.preferences=await this.orm.call(MODEL,'preferences',[]);
            this.recordContext={default_company_id:this.state.preferences.company_id};
            if (this.env.pbWorkforce) {
                this.state.location=this.env.pbWorkforce.location;
                this.state.locationName=this.env.pbWorkforce.locationName || '';
                this.state.drafts=!!this.env.pbWorkforce.drafts;
                this.env.pbWorkforce.guard=this.leaveGuard;
            }
            await this.load();
            if (this.env.pbWorkforce?.recordId && this.state.data?.model) {
                this.state.editor={id:this.env.pbWorkforce.recordId,name:this.state.data.label};
                this.env.pbWorkforce.recordId=null;
            }
        });
        onWillUnmount(() => {this.off(); if(this.env.pbWorkforce?.guard===this.leaveGuard) this.env.pbWorkforce.guard=null;});
    }
    icon(name,size=18){return ic(name,size);}
    get heading(){
        if(this.mode==='overview')return _t("Every workplace. One view.");
        return copy()[this.mode]?.[0] || _t("Build a working week that works.");
    }
    get description(){
        if(this.mode==='overview')return _t("Review coverage by workplace, then move into the roster or employee assignments.");
        return copy()[this.mode]?.[1] || _t("One setup, connected to the roster, attendance and payroll. Review each step before going live.");
    }
    get eyebrow(){return this.state.preferences?.company || _t("Workforce");}
    get adoptionText(){return this.state.preferences.enabled
        ? _t("Enabled for this company. Attendance and payroll rules are managed separately.")
        : _t("Use grouped navigation for this company. Existing rules and employee schedules stay as they are.");}
    get adoptionButton(){return this.state.preferences.enabled ? _t("Use previous navigation") : _t("Enable unified workspace");}
    stat(value,missing){
        if(value===null)return missing==='module' ? _t("Not installed") : _t("Unavailable");
        if(value===undefined)return _t("Unavailable");
        return fmtNum(value);
    }
    get weekLine(){
        const d=this.state.data||{};
        return _t("Roster counts for %(from)s to %(to)s. Grouped by each employee’s assigned workplace.",
            {from:this.day(d.week_start),to:this.day(d.week_end)});
    }
    day(iso){
        const d=iso?DateTime.fromISO(iso):null;
        return d&&d.isValid?d.toFormat('ccc d LLL'):(iso||'');
    }
    /** "<b>12</b> people" — the number bold, the sentence one translated piece. */
    bold(n){return markup(`<b>${fmtNum(n)}</b>`);}
    peopleCount(n){return _t("%s people",this.bold(n));}
    draftCount(n){return _t("%s draft shifts",this.bold(n));}
    otherCount(n){return _t("%s other roster rows",this.bold(n));}
    get recordsLine(){return _t("%s records",fmtNum(this.state.data?.total||0));}
    get pagerLine(){
        const total=this.state.data?.total||0;
        return _t("%(from)s–%(to)s of %(total)s",{from:fmtNum(total?this.state.offset+1:0),
            to:fmtNum(Math.min(this.state.offset+40,total)),total:fmtNum(total)});
    }
    get workplaceName(){return this.state.locationName || _t("Not assigned");}
    rowName(row){return row.name || _t("Record");}
    get notInstalledLabel(){return _t("Not installed");}
    get isOverview(){return ['overview','setup'].includes(this.mode);}
    get fields(){return Object.entries(this.state.data?.fields||{}).filter(([k])=>k!=='id'&&k!=='name');}
    get available(){return new Set((this.state.data?.catalogs||[]).map(c=>c.key));}
    async load(){
        const seq=this.seq=(this.seq||0)+1;
        this.state.loading=true; this.state.error='';
        try{
            const data=this.isOverview ? await this.orm.call(MODEL,'overview',[this.ctx.state.weekStart]) :
                await this.orm.call(MODEL,'catalog',[this.mode],{search:this.state.search,offset:this.state.offset,
                    location_id:this.state.location,week_start:this.mode==='rosters'?this.ctx.state.weekStart:null,drafts:this.state.drafts});
            if(seq===this.seq)this.state.data=data;
        }catch(e){if(seq===this.seq)this.state.error=e.data?.message||e.message||_t("Unable to load. Please retry.");}
        finally{if(seq===this.seq)this.state.loading=false;}
    }
    async guard(){return this.form ? this.form.guardLeave() : true;}
    async back(){
        if(await this.guard()){this.state.editor=null;this.load();}
    }
    async open(row){if(await this.guard())this.state.editor={id:row.id,name:row.name||_t("Record")};}
    create(){this.dialog.add(FormViewDialog,{resModel:this.state.data.model,
        context:{...this.recordContext,pb_premium_record:true},title:_t("New: %s",this.state.data.label),
        onRecordSaved:async(record)=>{await this.load();this.state.editor={id:record.resId,name:record.data?.name||this.state.data.label};}});}
    async go(key,location=null,drafts=false){
        if(this.env.pbWorkforce){await this.env.pbWorkforce.go(key,location,drafts);}
        else if (COPY_KEYS.includes(key) || key === 'setup') await this.action.doAction('pb_workforce_workspace.action_workspace_setup',{additionalContext:{pb_workspace_section:key,pb_back:this.props.action?.context?.pb_back}});
        else await this.action.doAction('pb_mission.action_pb_workforce',{additionalContext:{pb_shell_lens:key}});
    }
    async location(row,key){
        if(this.env.pbWorkforce){this.env.pbWorkforce.locationName=row.name;await this.go(key,row.id);}
    }
    async clearLocation(){this.state.location=null;this.state.locationName='';this.state.offset=0;await this.load();}
    async search(ev){this.state.search=ev.target.value;this.state.offset=0;await this.load();}
    async page(delta){this.state.offset=Math.max(0,this.state.offset+delta*40);await this.load();}
    format(value,meta,key){
        if(value===false||value===null||value===undefined)return meta.type==='boolean'?_t("No"):_t("Not set");
        if(meta.type==='many2one')return value[1];
        if(meta.type==='selection')return meta.selection?.find(s=>s[0]===value)?.[1]||value;
        if(meta.type==='boolean')return value?_t("Yes"):_t("No");
        if(['start_hour','end_hour'].includes(key)){const m=Math.round(value*60);return `${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`;}
        if(meta.type==='float')return formatFloat(Number(value),{digits:[false,2],trailingZeros:false});
        if(meta.type==='integer')return fmtNum(value);
        if(meta.type==='date'){const d=DateTime.fromISO(value);return d.isValid?d.toFormat('d LLL yyyy'):String(value);}
        return String(value);
    }
    async toggle(){
        this.state.busy=true;
        try{await this.orm.write('res.company',[this.state.preferences.company_id],
            {pb_workforce_workspace_enabled:!this.state.preferences.enabled});window.location.reload();}
        catch(e){this.state.error=e.data?.message||e.message;this.state.busy=false;}
    }
}

const extraKeys=['overview','setup',...COPY_KEYS];
for(const key of extraKeys){registry.category('pb_mission_lens').add(key,{
    key,get label(){return lensLabels()[key];},icon:key==='connectors'?'plug':key==='people'?'users':key==='overview'?'layoutGrid':'sliders',
    Component:WorkforcePanel,props:{mode:key,embedded:true},groups:['hr_attendance.group_hr_attendance_officer'],
    features:{department:false,week:['overview','rosters'].includes(key),person:false,day:false,search:false},
},{sequence:95});}
registry.category('actions').add('pb_workforce_setup',WorkforcePanel);
registry.category(SETTINGS_CATEGORIES).add('workforce_workspace',{
    key:'workforce_workspace',group:'hr',icon:'calendar',get label(){return _t("Workforce setup");},
    get blurb(){return _t("Shifts, people, recurring rosters, calculation rules and attendance connections in one place.");},
    groups:['hr_attendance.group_hr_attendance_officer'],
    cards:[{id:'setup',xmlid:'pb_workforce_workspace.action_workspace_setup',icon:'compass',
        get label(){return _t("Set up Workforce");},
        get sub(){return _t("Follow the guided setup or return to an individual setting. Administrators can enable the unified workspace here.");}}],
},{sequence:39});

patch(PbMission.prototype,{
    setup(){
        super.setup(...arguments);
        this.workspace=useState({enabled:false,company:'',can_configure:false});
        const owner=this;
        this.workspaceEnv={get enabled(){return owner.workspace.enabled;},location:null,locationName:'',drafts:false,guard:null,
            go:async(key,location=null,drafts=false,recordId=null)=>{
                if(this.workspaceEnv.guard && !await this.workspaceEnv.guard())return;
                this.workspaceEnv.location=location;this.workspaceEnv.drafts=drafts;this.workspaceEnv.recordId=recordId;
                if(location===null)this.workspaceEnv.locationName='';
                this.setLens(key);
            }};
        useSubEnv({pbWorkforce:this.workspaceEnv});
        onWillStart(async()=>{
            Object.assign(this.workspace,await this.orm.call(MODEL,'preferences',[]));
            if(this.workspace.enabled && !this.props.action?.context?.pb_shell_lens && this.state.lens==='today' && this.state.allowed?.overview)this.state.lens='overview';
            if(!this.workspace.enabled && extraKeys.includes(this.state.lens) && this.state.lens!=='setup')this.state.lens='today';
            // With the setup screen installed, a remembered setup lens (or, in
            // the grouped menu, a setup-only lens) is not in the menu: start on
            // the overview / today instead. A deep link to one still opens it.
            const asked=this.props.action?.context?.pb_shell_lens;
            if(setupStudioInstalled() && !asked && (this.state.lens==='setup' || (this.workspace.enabled && SETUP_ONLY.includes(this.state.lens))))
                this.state.lens=this.workspace.enabled && this.state.allowed?.overview!==false ? 'overview' : 'today';
        });
    },
    get workspaceTrimmed(){return setupStudioInstalled();},
    get setupLabel(){return this.workspaceTrimmed ? _t("Workforce setup") : _t("Guided setup");},
    get reviewRosterShown(){return !this.workspaceTrimmed || !!this.workspace.review_rows || this.state.lens==='rosters';},
    async setLens(key){
        if(this.workspace?.enabled && this.workspaceEnv.guard && key !== this.state.lens && !await this.workspaceEnv.guard())return;
        return super.setLens(key);
    },
    get lenses(){return super.lenses.filter(l=>this.workspace?.enabled || !extraKeys.includes(l.key));},
    get workspaceGroups(){
        const trimmed=this.workspaceTrimmed;
        const groups=trimmed?TRIMMED_GROUPS:GROUPS;
        const hidden=new Set(trimmed?[...SETUP_ONLY,'setup',...(this.reviewRosterShown?[]:['rosters'])]:['setup']);
        const visible=new Set(this.lenses.map(l=>l.key).filter(k=>!hidden.has(k)));
        const listed=new Set([...GROUPS,...groups].flatMap(g=>g.keys));
        return groups.map(g=>({...g,title:groupLabel(g.label),keys:(g.label==='More'?[...g.keys,...this.lenses.filter(l=>!listed.has(l.key)&&!hidden.has(l.key)).map(l=>l.key)]:g.keys).filter(k=>visible.has(k))})).filter(g=>g.keys.length);
    },
    // A lens reached by a deep link that is not in the trimmed menu (the
    // rotation editor from setup step 2, say) lights no tab.
    get workspaceGroup(){return this.workspaceGroups.find(g=>g.keys.includes(this.state.lens))||(this.workspaceTrimmed?null:this.workspaceGroups[0]);},
    get workspaceSubnav(){const labels={...lensLabels(),timeoff:_t("Time off"),approvals:_t("Approvals"),field:_t("Field"),insights:_t("Insights")};return (this.workspaceGroup?.keys||[]).map(key=>({key,label:labels[key]||this.lenses.find(l=>l.key===key)?.label}));},
    async workspaceNavigate(key){
        if(this.workspaceEnv.guard && !await this.workspaceEnv.guard())return;
        this.workspaceEnv.location=null;this.workspaceEnv.locationName='';this.workspaceEnv.drafts=false;
        this.setLens(key);
    },
});

// Existing doors open the same record editor inside the unified workspace.
// Standalone/legacy screens retain their original behavior.
patch(PbSchedule.prototype,{
    openTemplate(row){
        if(this.env.pbWorkforce?.enabled){return this.env.pbWorkforce.go('shifts',null,false,row?.id);}
        return super.openTemplate(...arguments);
    },
});
patch(PbOtDesk.prototype,{
    openConfig(id){
        if(this.env.pbWorkforce?.enabled){return this.env.pbWorkforce.go('rates',null,false,id);}
        return super.openConfig(...arguments);
    },
});
patch(PbShiftPatterns.prototype,{
    setup(){super.setup(...arguments); onMounted(()=>{if(this.env.pbWorkforce?.enabled)this.kit.ui.panel=false;});},
    get makeTitle(){return this.workspacePattern ? _t("Create roster drafts") : super.makeTitle;},
    get workspaceMakeLabel(){return this.workspacePattern ? _t("Create roster") : _t("Make drafts");},
    get workspaceMakeDraftsLabel(){return this.workspacePattern ? _t("Create roster drafts") : _t("Make drafts");},
    async makeDrafts(){if(this.workspacePattern && !this.state.make?.preview)return this.check();return super.makeDrafts(...arguments);},
    get workspacePattern(){return !!this.env.pbWorkforce?.enabled;},
    workspaceCell(cell,row){
        const d = row.cycle_start ? new Date(row.cycle_start+'T12:00:00') : null;
        if(d)d.setDate(d.getDate()+cell.i);
        // the user's language, not the browser's (luxon follows the user's settings)
        const label=d?DateTime.fromJSDate(d).toFormat('ccc'):_t("Day %s",cell.i+1);
        if(cell.off)return _t("%s · Rest",label);
        const t=this.state.templates.find(t=>t.code===cell.code);
        return `${label} · `+(t?`${t.start}–${t.end}`:cell.name||cell.code);
    },
    reviewWorkspaceDrafts(){return this.env.pbWorkforce.go('rosters',null,true);},
});

// Leave room for the working surface on a phone; the existing button still opens the dock.
patch(WfDock.prototype,{
    setup(){
        super.setup(...arguments);
        const media=window.matchMedia('(max-width: 767px)');
        const collapse=()=>{if(this.env.pbWorkforce?.enabled && media.matches)this.state.collapsed=true;};
        onMounted(collapse);media.addEventListener('change',collapse);
        onWillUnmount(()=>media.removeEventListener('change',collapse));
    },
});

// Settings keeps its familiar entries; adopted companies arrive at the same editors.
patch(PbSettingsHub.prototype,{
    setup(){
        super.setup(...arguments);this.workforceUnified=false;
        onWillStart(async()=>{this.workforceUnified=(await this.orm.call(MODEL,'preferences',[])).enabled;});
    },
    openCard(card){
        const targets={
            'pb_attendance_policy.action_policy':'policies',
            'pb_attendance_policy.action_employee_policy':'people',
            'pb_hr_workforce.action_shift_planning_no_filter':'rosters',
            'resource.action_resource_calendar_form':'calendars',
            'pb_clock.action_clock_connectors':'connectors',
        };
        const section=targets[card.xmlid];
        if(this.workforceUnified && section)return super.openCard({...card,xmlid:undefined,tag:'pb_workforce_setup',
            context:{...card.context,pb_workspace_section:section}});
        return super.openCard(...arguments);
    },
});
