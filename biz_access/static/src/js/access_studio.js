/** @odoo-module **/
import { useEffect, onWillUnmount } from '@odoo/owl';
import { patch } from '@web/core/utils/patch';
import { registry } from '@web/core/registry';
import { _t } from '@web/core/l10n/translation';
import { PbAccessBoard } from '@biz_access/js/access_board';
import { PbSidebar } from '@pb_sidebar/js/pb_sidebar';

const todayPlus = (days) => new Date(Date.now() + days * 86400000).toISOString().slice(0, 10);
const clone = (value) => JSON.parse(JSON.stringify(value));
const tabs = [
    ['studio_people', 'users', 'People & assignments'], ['packages', 'layers', 'Profiles'],
    ['roles', 'idCard', 'Roles & permissions'], ['screens', 'compass', 'Screens'],
    ['reviews', 'check', 'Requests & reviews'], ['handovers', 'arrowLeftRight', 'Delegation'],
    ['studio_history', 'clock', 'History'],
];
patch(PbAccessBoard.prototype, {
    setup() {
        super.setup();
        this.studioSeq = 0;
        this.state.workspace = this.props.workspace || this.props.action?.context?.pb_access_workspace || 'hiring';
        this.state.studio = null;
        this.state.studioError = '';
        this.state.studioBusy = false;
        this.state.studioSearch = '';
        this.state.studioPeopleFilter = 'module';
        this.state.studioStatus = 'active';
        this.state.studioSelected = [];
        this.state.studioDialog = null;
        this.state.studioReview = 'requests';
        this.state.studioRequestFilter = 'pending';
        this.state.studioPolicy = null;
        this.state.studioPolicyTab = 'permissions';
        this.state.studioResource = '';
        onWillUnmount(() => { clearTimeout(this.studioTimer); this.studioSeq++; });
        useEffect(() => {
            if (!this.state.studioDialog) return;
            const prior = document.activeElement;
            const dialog = document.querySelector('.pbva-studio-dialog');
            const focusables = () => [...dialog.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),summary')];
            focusables()[0]?.focus();
            const trap = (event) => {
                if (event.key !== 'Tab') return;
                const controls = focusables(), first = controls[0], last = controls[controls.length - 1];
                if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
                if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
            };
            dialog.addEventListener('keydown', trap);
            return () => { dialog.removeEventListener('keydown', trap); prior?.focus(); };
        }, () => [this.state.studioDialog]);
        if (!this.props.action?.context?.pb_lens && !this.props.action?.context?.pb_edit_role) {
            this.state.lens = 'studio_people';
        }
    },
    get lenses() { return tabs.map(([key, icon, label]) => ({ key, icon, label: _t(label) })); },
    get studio() { return this.state.studio || { profiles: [], roles: [], people: [], requests: [], history: [], resources: [], workspaces: [], departments: [], owners: [] }; },
    get studioCanManage() { return Boolean(this.studio.can_manage); },
    get profiles() {
        const ids = this.studio.role_ids;
        return super.profiles.filter(r => !ids || ids.includes(r.id)).map(r => ({...r, area_label: this.studio.workspaces.find(w => w.key === this.state.workspace)?.label || r.area_label}));
    },
    get delegations() { return super.delegations.filter(d => !this.studio.delegation_ids || this.studio.delegation_ids.includes(d.id)); },
    get mine() { return super.mine.filter(r => !this.studio.role_ids || this.studio.role_ids.includes(r.id)); },
    get glance() {
        return [
            {key:'profiles',n:this.studio.profiles.filter(p=>p.active).length,label:_t('active profiles'),tone:'',run:()=>this.setLens('packages')},
            {key:'roles',n:this.profiles.length,label:_t('roles in this view'),tone:'',run:()=>this.setLens('roles')},
            {key:'people',n:this.studio.module_people_count || 0,label:_t('people with module roles'),tone:'',run:()=>this.setLens('studio_people')},
            {key:'requests',n:this.studio.requests.filter(r=>r.state==='pending').length,label:_t('requests awaiting review'),tone:'',run:()=>this.setLens('reviews')},
            {key:'screens',n:this.kpis.entries || 0,label:_t('entries in the full menu'),tone:'',run:()=>this.setLens('screens')},
        ];
    },
    async load() {
        await super.load();
        await this.loadStudio();
    },
    async loadStudio() {
        const seq = ++this.studioSeq;
        try {
            const data = await this.orm.call('pb.access', 'studio_data', [this.state.workspace, this.state.studioSearch]);
            if (seq !== this.studioSeq) return;
            this.state.studio = data;
            this.state.studioError = '';
        } catch (e) {
            if (seq === this.studioSeq) this.state.studioError = this._msg(e, _t('Access Studio could not be loaded.'));
        }
    },
    async setWorkspace(ev) {
        this.state.workspace = ev.target.value;
        this.state.area = '';
        this.state.search = '';
        this.state.studioSelected = [];
        this.state.studioPolicy = null;
        this.state.open = 0;
        await this.reload();
    },
    async studioSearch(ev) {
        this.state.studioSearch = ev.target.value;
        clearTimeout(this.studioTimer);
        this.studioTimer = setTimeout(() => this.loadStudio(), 250);
    },
    get studioPeople() {
        const needle = this.state.studioSearch.toLocaleLowerCase();
        return this.studio.people.filter(p => (!needle || `${p.name} ${p.login}`.toLocaleLowerCase().includes(needle)) &&
            (this.state.studioPeopleFilter !== 'module' || p.in_module) &&
            (this.state.studioPeopleFilter !== 'due' || p.assignments.some(a => a.due)));
    },
    get studioProfiles() {
        const needle = this.state.studioSearch.toLocaleLowerCase();
        return this.studio.profiles.filter(p => (this.state.studioStatus === 'all' || p.active === (this.state.studioStatus === 'active')) &&
            (!needle || `${p.name} ${p.description}`.toLocaleLowerCase().includes(needle)));
    },
    get studioRequests() { return this.studio.requests.filter(r => this.state.studioRequestFilter === 'all' || r.state === this.state.studioRequestFilter); },
    get studioDue() { return this.studio.people.flatMap(p => p.assignments.filter(a => a.due).map(a => ({ ...a, user: p.name, user_id: p.id }))); },
    get studioRoles() { return this.studio.roles.filter(r => r.workspace === this.state.workspace); },
    get studioPickerRoles() {
        const d = this.state.studioDialog;
        const needle = (d?.roleSearch || '').toLocaleLowerCase();
        return this.studio.roles.filter(r => (d?.includeOtherModules || r.workspace === this.state.workspace || d?.form.role_ids.includes(r.id)) &&
            (!needle || r.name.toLocaleLowerCase().includes(needle)));
    },
    get studioAssignable() { return this.studio.profiles.filter(p => p.active); },
    get studioCurrentResource() { return this.studio.resources.find(r => r.key === this.state.studioResource); },
    get studioRule() { return this.state.studioPolicy?.policy[this.state.studioResource]; },
    studioTogglePerson(id) {
        const ids = this.state.studioSelected;
        this.state.studioSelected = ids.includes(id) ? ids.filter(i => i !== id) : [...ids, id];
    },
    studioToggleAll() {
        this.state.studioSelected = this.state.studioSelected.length === this.studioPeople.length ? [] : this.studioPeople.map(p => p.id);
    },
    studioOpenProfile(profile = null, duplicate = false) {
        const form = profile ? clone(profile) : { name: '', description: '', role_ids: [], owner_id: this.board.me?.id || 0,
            review_date: todayPlus(90), auto_department_id: 0 };
        if (duplicate) { delete form.id; delete form.revision; form.name += ' — copy'; form.auto_department_id = 0; }
        this.state.studioDialog = { kind: 'profile', title: form.id ? _t('Edit profile') : _t('New profile'), form, roleSearch: '', includeOtherModules: false, reason: '', error: '' };
    },
    studioToggleRole(id) {
        const form = this.state.studioDialog.form;
        form.role_ids = form.role_ids.includes(id) ? form.role_ids.filter(x => x !== id) : [...form.role_ids, id];
    },
    studioAssign(person = null) {
        const users = person ? [person.id] : this.state.studioSelected;
        if (!users.length) return this.notif.add(_t('Select at least one person.'), { type: 'warning' });
        this.state.studioDialog = { kind: 'assign', title: _t('Review profile assignment'),
            form: { profile_id: this.studioAssignable[0]?.id || 0, users, date_end: '' }, reason: '', error: '' };
    },
    studioRequestExtra(person = null) {
        this.state.studioDialog = { kind: 'extra', title: _t('Request temporary access'), form: {
            user_id: person?.id || this.board.me?.id, role_id: this.studioRoles[0]?.id || 0, date_end: todayPlus(7) }, reason: '', error: '' };
    },
    studioConfirm(kind, title, data) { this.state.studioDialog = { kind, title, form: data, reason: '', error: '' }; },
    studioCompare(profile) {
        this.state.studioDialog = { kind: 'compare', title: _t('Compare profiles'), form: { profile, other_id: this.studio.profiles.find(p => p.id !== profile.id)?.id || 0 } };
    },
    get studioComparison() {
        const form = this.state.studioDialog?.form;
        if (!form?.profile) return [];
        const other = this.studio.profiles.find(p => p.id === Number(form.other_id));
        return this.studio.roles.filter(r => form.profile.role_ids.includes(r.id) || other?.role_ids.includes(r.id))
            .map(r => ({ ...r, left: form.profile.role_ids.includes(r.id), right: Boolean(other?.role_ids.includes(r.id)) }));
    },
    async studioExplain(person) {
        this.state.studioDialog = { kind: 'explain', title: _t('Explain access'), form: { user_id: person.id, user: person.name,
            model: this.studio.resources[0]?.key || '', action: 'read', record_id: '', field_name: '', without_profile: false }, result: null, error: '' };
        if (this.state.studioDialog.form.model) await this.studioRunExplain();
    },
    async studioRunExplain() {
        const d = this.state.studioDialog;
        try {
            d.result = await this.orm.call('pb.access', 'studio_explain', [this.state.workspace, d.form.user_id,
                d.form.model, Number(d.form.record_id) || false, d.form.action, d.form.field_name || false, d.form.without_profile]);
            d.error = '';
        } catch (e) { d.error = this._msg(e, _t('Access could not be explained.')); }
    },
    async studioOpenPolicy(role) {
        try {
            this.state.studioPolicy = await this.orm.call('pb.access', 'studio_role_policy', [this.state.workspace, role.id]);
            this.state.studioResource = this.studio.resources[0]?.key || '';
            this.state.studioPolicyTab = 'permissions';
            this.state.lens = 'policy';
        } catch (e) { this.notif.add(this._msg(e, _t('Policy could not be opened.')), { type: 'danger' }); }
    },
    studioEnableResource() {
        const resource = this.studioCurrentResource;
        this.state.studioPolicy.policy[resource.key] = { read: 'all', create: 'none', write: 'none', unlink: 'none',
            fields: Object.fromEntries(resource.fields.map(f => [f.key, 'view'])), create_fields: resource.fields.filter(f => !f.readonly).map(f => f.key),
            export: false, archive: false, reassign: false, approve: false, download: false, reveal: false,
            department_ids: [], states: [], write_states: [], match: 'all' };
    },
    studioRemoveResource() { delete this.state.studioPolicy.policy[this.state.studioResource]; },
    studioPolicyList(key, value) {
        const row = this.studioRule;
        row[key] = row[key].includes(value) ? row[key].filter(x => x !== value) : [...row[key], value];
    },
    studioReviewPolicy() {
        this.state.studioDialog = { kind: 'policy', title: _t('Review policy changes'), form: clone(this.state.studioPolicy), reason: '', error: '' };
    },
    studioOwners() {
        this.state.studioDialog = { kind: 'owner', title: _t('Module access owners'),
            form: { user_id: this.studio.people[0]?.id || 0, role_ids: [], active: true }, roleSearch: '', includeOtherModules: false, reason: '', error: '' };
    },
    studioOwnerSelect(ev) {
        const id = Number(ev.target.value);
        const owner = this.studio.owners.find(o => o.user_id === id);
        Object.assign(this.state.studioDialog.form, { user_id: id, role_ids: clone(owner?.role_ids || []), active: true });
    },
    studioJson(value) {
        const labels = { read: 'View', create: 'Create', write: 'Edit', unlink: 'Delete', fields: 'Form fields',
            create_fields: 'Fields allowed on create', export: 'Export records', archive: 'Archive', reassign: 'Reassign owner',
            approve: 'Approve / finalise', reveal: 'Reasoned reveal', download: 'Download attachments',
            department_ids: 'Departments', states: 'Visible stages', write_states: 'Editable stages', match: 'Condition matching',
            before: 'Before', after: 'After', count: 'Affected people', people: 'People', profiles: 'Referenced profiles',
            roles: 'Roles', name: 'Name', description: 'Purpose', owner: 'Owner', review_date: 'Next review',
            revision: 'Version', active: 'Active', auto_department: 'Automatic department', members: 'Assigned people',
            note: 'Note', expires: 'Until', conflicts: 'Conflicts', snapshot: 'Published profile', field: 'Field', model: 'Resource' };
        const words = { none: 'No access', own: 'Own records', team: 'Team records', all: 'All allowed records',
            hidden: 'Hidden', masked: 'Masked', view: 'View only', edit: 'View and edit', any: 'Any condition' };
        const fieldLabels = Object.fromEntries(this.studio.resources.flatMap(r => r.fields.map(f => [f.key, f.label])));
        const resourceLabels = Object.fromEntries(this.studio.resources.map(r => [r.key, r.label]));
        const pretty = (data, depth=0) => Object.entries(data || {}).filter(([key]) => (!key.endsWith('_id') && !key.endsWith('_ids') || ['department_ids','role_ids','owner_id','auto_department_id'].includes(key)) && key !== 'workspace' && key !== 'id').map(([key, item]) => {
            const label = ({department_ids:'Departments',role_ids:'Role references',owner_id:'Owner',auto_department_id:'Automatic department'})[key] || labels[key] || fieldLabels[key] || resourceLabels[key] || key.replaceAll('_', ' ');
            const prefix = '  '.repeat(depth) + label + ': ';
            if (key === 'department_ids') return prefix + (item.map(id => this.studio.departments.find(d => d.id === id)?.name || 'Department ' + id).join(', ') || 'All allowed departments');
            if (key === 'role_ids') return prefix + item.map(id => this.studio.roles.find(r => r.id === id)?.name || 'Role ' + id).join(', ');
            if (key === 'owner_id') return prefix + (this.studio.people.find(p => p.id === item)?.name || 'User ' + item);
            if (key === 'auto_department_id') return prefix + (this.studio.departments.find(d => d.id === item)?.name || 'Manual assignment');
            if (Array.isArray(item)) return prefix + (item.map(x => fieldLabels[x] || words[x] || x).join(', ') || 'None');
            if (item && typeof item === 'object') return prefix + '\n' + pretty(item, depth+1);
            return prefix + (typeof item === 'boolean' ? (item ? 'Yes' : 'No') : words[item] || item || 'None');
        }).join('\n');
        return pretty(value);
    },
    studioNames(ids) { return this.studio.people.filter(p => ids.includes(p.id)).map(p => p.name).join(', '); },
    studioFieldOptions() { return this.studio.resources.find(r => r.key === this.state.studioDialog?.form.model)?.fields || []; },
    closeStudio() { if (!this.state.studioBusy) this.state.studioDialog = null; },
    async studioSubmit() {
        const d = this.state.studioDialog;
        if (!d || this.state.studioBusy) return;
        this.state.studioBusy = true;
        d.error = '';
        try {
            const w = this.state.workspace, f = d.form;
            let method, args;
            if (d.kind === 'profile') { method = 'studio_submit_profile'; args = [w, f, d.reason]; }
            if (d.kind === 'assign') { method = 'studio_submit_assignment'; args = [w, Number(f.profile_id), f.users, f.date_end, d.reason]; }
            if (d.kind === 'extra') { method = 'studio_submit_extra'; args = [w, Number(f.user_id), Number(f.role_id), f.date_end, d.reason]; }
            if (d.kind === 'policy') { method = 'studio_submit_policy'; args = [w, f.id, f.revision, f.policy, d.reason]; }
            if (d.kind === 'decide') { method = 'studio_decide'; args = [w, f.id, f.approve, d.reason]; }
            if (d.kind === 'review') { method = 'studio_review_assignment'; args = [w, f.id, f.revision, f.retain === true || f.retain === 'true', d.reason]; }
            if (d.kind === 'revoke_extra') { method = 'studio_revoke_extra'; args = [w, f.id, d.reason]; }
            if (d.kind === 'retire') { method = 'studio_retire_profile'; args = [w, f.id, f.revision, d.reason]; }
            if (d.kind === 'restore') { method = 'studio_restore_policy'; args = [w, f.id, d.reason]; }
            if (d.kind === 'owner') { method = 'studio_set_owner'; args = [w, Number(f.user_id), f.role_ids, f.active, d.reason]; }
            if (d.kind === 'reveal') { method = 'studio_reveal'; args = [f.model, Number(f.record_id), f.field_name, d.reason]; }
            const result = await this.orm.call('pb.access', method, args);
            if (d.kind === 'reveal') { d.result = result; return; }
            this.notif.add(result.message || _t('Saved.'), { type: 'success' });
            this.state.studioDialog = null;
            if (['profile', 'assign', 'extra', 'policy', 'restore'].includes(d.kind)) {
                this.state.lens = 'reviews'; this.state.studioReview = 'requests'; this.state.studioRequestFilter = 'pending';
            }
            this.state.studioSelected = [];
            await this.reload();
            this.env.bus.trigger('PB_SIDEBAR:RELOAD');
        } catch (e) { d.error = this._msg(e, _t('This change could not be saved.')); }
        finally { this.state.studioBusy = false; }
    },
    onKeyDown(ev) {
        if (ev.key === 'Escape' && this.state.studioDialog) { this.closeStudio(); return; }
        super.onKeyDown(ev);
    },
});

// The same workspace appears inside Hiring's existing HubShell submenu.
registry.category('pb_hiring_hub_lens').add('access_studio', {
    key: 'access', icon: 'shield', label: _t('Access & delegation'),
    title: _t('Hiring access'), Component: PbAccessBoard,
    groups: ['base.group_user'], props: { embedded: true, workspace: 'hiring' },
});

// Adding an access submenu must not turn an existing workspace door into an
// expansion-only control. Keep the workspace action and reveal its local doors.
patch(PbSidebar.prototype, {
    onItemClick(item) {
        if (!item.restricted && (item.action_xmlid || item.action_tag) &&
            item.children?.some(child => child.action_xmlid?.startsWith('biz_access.action_studio_'))) {
            this.state.expandedItems = {...this.state.expandedItems, [item.id]: true};
            this.navigateTo(item);
            this.state.calm = false;
            return;
        }
        super.onItemClick(item);
    },
});
