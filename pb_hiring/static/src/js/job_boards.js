/** @odoo-module **/
import { boardLogo } from "@pb_hiring/js/board_logos";
import { Component, useState, onWillStart } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';
import { registry } from '@web/core/registry';
import { _t } from '@web/core/l10n/translation';
import { ic } from '@pb_import_kit/js/import_icons';

export class HiringJobBoards extends Component {
    static template = 'pb_hiring.JobBoards';
    static props = ['*'];
    boardLogo(key) { return boardLogo(key); }
    setup() {
        this.orm = useService('orm'); this.action = useService('action'); this.notification = useService('notification');
        this.state = useState({roles: [], company: '', can_setup: false, capped: false, query: '', roleId: '',
            view: 'catalogue', catalogue: [], country: '', boardQuery: '', routeFilter: '', guide: null, expires: '',
            panel: null, channel: null, step: 0, values: {}, busy: false, error: '', saved: false,
            confirmed: false, manual: false, externalUrl: '', result: ''});
        onWillStart(() => this.run(async () => {
            const [home, catalogue] = await Promise.all([
                this.orm.call('pb.hiring', 'job_board_home', []),
                this.orm.call('pb.hiring', 'job_board_catalogue', []),
            ]);
            Object.assign(this.state, home); this.state.catalogue = catalogue.boards;
            const id = this.props.action?.context?.pb_role_id;
            if (id && this.state.roles.some(r => r.id === id)) { this.state.view='publish'; this.state.roleId = String(id); await this.loadRole(); }
        }));
    }
    ic(name, size=18) { return ic(name, size); }
    get roles() { const q = this.state.query.toLowerCase(); return this.state.roles.filter(r => `${r.title} ${r.location} ${r.country}`.toLowerCase().includes(q)); }
    get boards() { return (this.state.panel?.rows || []).filter(r => ['board','social'].includes(r.kind) && r.name.toLowerCase().includes(this.state.boardQuery.toLowerCase())); }
    get catalogueBoards() {
        const q=this.state.boardQuery.toLowerCase();
        return this.state.catalogue.filter(b => (!this.state.country || !b.countries.length || b.countries.includes(this.state.country))
            && (!this.state.routeFilter || b.route === this.state.routeFilter)
            && `${b.name} ${b.audience} ${b.country_label}`.toLowerCase().includes(q));
    }
    routeLabel(route) { return {api:_t('Account connection'), partner:_t('Partner onboarding'), feed:_t('Job feed'), discovery:_t('Search discovery')}[route] || _t('Manual posting'); }
    switchView(view) { this.state.view=view; this.state.guide=null; this.state.boardQuery=''; this.state.error=''; }
    guide(key) { return this.run(async () => {
        this.state.guide = await this.orm.call('pb.hiring','job_board_guide',[key]);
    }); }
    saveSetup() { return this.run(async () => {
        const g=this.state.guide;
        const values={enabled:g.enabled,onboarding_stage:g.onboarding_stage,onboarding_note:g.onboarding_note};
        if(g.route === 'feed') values.feed_enabled=g.feed_enabled;
        this.state.guide=await this.orm.call('pb.hiring','job_board_setup',[g.key,values]);
        this.state.catalogue=(await this.orm.call('pb.hiring','job_board_catalogue',[])).boards;
        if(this.state.roleId) this.state.panel=await this.orm.call('pb.hiring','job_board_detail',[Number(this.state.roleId)]);
        this.notification.add(_t('Setup saved. This does not send a provider request or activate an API connection.'),{type:'success'});
    }); }
    chooseFeed(row) {
        this.state.channel=row; this.state.step=4; this.state.result='';
        const date=new Date(); date.setDate(date.getDate()+30);
        this.state.expires=row.feed_expires || `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
    }
    selectFeed(selected) { return this.run(async () => {
        const id=this.state.channel.id;
        this.state.panel=await this.orm.call('pb.hiring','job_board_feed_select',[id,selected,this.state.expires]);
        this.state.channel=this.state.panel.rows.find(r=>r.id===id);
        this.state.result=selected ? _t('Included in the feed. The provider must accept and publish the job before it is live on the board.')
            : _t('Removed from the feed. A previously published listing may remain until the provider refreshes its feed.');
    }); }
    closeManual() { return this.run(async () => {
        await this.orm.call('pb.hiring','act',['p7_close',{role_channel_id:this.state.channel.id}]);
        await this.loadRole();
    }); }
    get careers() { return this.state.panel?.rows.find(r => r.kind === 'careers'); }
    get canPost() { return this.state.panel && !this.state.panel.confidential && ['setup','open'].includes(this.state.panel.state); }
    get automatic() { return !!this.state.channel?.connection.ready && !this.state.manual; }
    get pending() { return ['queued','pending'].includes(this.state.channel?.delivery_state); }
    get complete() { const v=this.state.values; return !!(v.title?.trim() && v.location?.trim() && v.description?.trim()); }
    get packedAdvert() { const v=this.state.values; return `${v.title}\n${v.location}\n\n${v.description}\n\nApply: ${this.state.channel?.link || ''}`; }
    get submitLabel() {
        if (!this.automatic) return _t('Record live posting');
        return this.state.channel.api_managed ? _t('Send update to board') : _t('Send job to board');
    }
    async run(fn) {
        if(this.state.busy) return;
        this.state.busy=true; this.state.error='';
        try { await fn(); } catch(e) { this.state.error=e.data?.message || e.message || _t('This step could not be completed.'); }
        finally { this.state.busy=false; }
    }
    async loadRole() {
        this.state.panel = this.state.roleId ? await this.orm.call('pb.hiring','job_board_detail',[Number(this.state.roleId)]) : null;
        this.state.channel=null; this.state.step=0; this.state.result='';
    }
    chooseRole(ev) { this.state.roleId=ev.target.value; return this.run(() => this.loadRole()); }
    refresh() { return this.run(() => this.loadRole()); }
    chooseBoard(row) {
        this.state.channel=row; this.state.step=1; this.state.saved=false; this.state.result='';
        this.state.confirmed=false; this.state.manual=!row.connection.ready;
        this.state.externalUrl=row.external_url || '';
        this.state.values={title:this.state.panel.title, location:this.state.panel.location || this.state.panel.country,
            description:this.state.panel.description, native_apply:true, summary:this.state.panel.title,
            currency:'', salary_min:0, salary_max:0, pay_interval:'Year', work_type:'FullTime', arrangement:'OnSite',
            location_id:'',category_id:'',product_id:'', ...row.draft};
    }
    saveDraft() { return this.run(async () => {
        this.state.panel=await this.orm.call('pb.hiring','job_board_save',[this.state.channel.id,this.state.values,'draft']);
        this.state.saved=true;
        this.notification.add(_t('Advert draft saved. Nothing has been published.'),{type:'success'});
    }); }
    review() { if(this.complete) { this.state.step=2; this.state.confirmed=false; } }
    submit() { return this.run(async () => {
        if(!this.state.confirmed || !this.state.panel.on_page || this.pending) return;
        const id=this.state.channel.id;
        if(this.automatic) {
            this.state.panel=await this.orm.call('pb.hiring','job_board_save',[id,{...this.state.values,confirmed:true},this.state.channel.api_managed ? 'update':'publish']);
            this.state.result=_t('Sent to the publishing queue. The board must confirm the listing before it is shown as live.');
        } else {
            const url=new URL(this.state.externalUrl);
            if(!['https:','http:'].includes(url.protocol)) throw new Error(_t('Enter the full live job URL.'));
            await this.orm.call('pb.hiring','job_board_save',[id,this.state.values,'draft']);
            await this.orm.call('pb.hiring','act',['p7_mark_posted',{role_channel_id:id,external_url:this.state.externalUrl}]);
            this.state.panel=await this.orm.call('pb.hiring','job_board_detail',[Number(this.state.roleId)]);
            this.state.result=_t('Manual posting recorded. Applications through its tracked link will be attributed to this board.');
        }
        this.state.channel=this.state.panel.rows.find(r=>r.id===id); this.state.step=3;
    }); }
    publishCareers() { return this.run(async () => {
        await this.orm.call('pb.hiring','act',['p7_publish',{requisition_id:Number(this.state.roleId)}]);
        await this.loadRole();
    }); }
    async copy(text) {
        try { await navigator.clipboard.writeText(text); this.notification.add(_t('Copied'),{type:'success'}); }
        catch { this.state.error=_t('Clipboard access was blocked. Select and copy the text shown on this page.'); }
    }
    connections() { return this.action.doAction('pb_hiring.action_hiring_connections',{additionalContext:{pb_board_setup:true}}); }
    openRole() { return this.action.doAction('pb_hiring.action_pb_hiring_hub',{additionalContext:{pb_role_id:Number(this.state.roleId)}}); }
    manage() { return this.run(async () => {
        const action=await this.orm.call('pb.hiring','board_open',[this.state.channel.id]);
        await this.action.doAction(action,{onClose:()=>this.refresh()});
    }); }
}
registry.category('actions').add('pb_hiring_job_boards', HiringJobBoards);
