/** @odoo-module **/
import { useEffect, onWillUnmount } from '@odoo/owl';
import { patch } from '@web/core/utils/patch';
import { registry } from '@web/core/registry';
import { _t } from '@web/core/l10n/translation';
import { PbAccessBoard } from '@biz_access/js/access_board';
import { openHub } from '@pb_hub/js/hub_nav';

const todayPlus = (days) => new Date(Date.now() + days * 86400000).toISOString().slice(0, 10);
const clone = (value) => JSON.parse(JSON.stringify(value));
const tabs = [
    ['people', 'users', 'People & assignments'], ['packages', 'layers', 'Profiles'],
    ['roles', 'idCard', 'Roles & permissions'], ['screens', 'compass', 'Screens'],
    ['reviews', 'check', 'Requests & reviews'], ['handovers', 'arrowLeftRight', 'Delegation'],
    ['studio_history', 'clock', 'History'],
];
patch(PbAccessBoard.prototype, {
    setup() {
        super.setup();
        this.studioSeq = 0;
        this.state.workspace = this.props.workspace || this.props.action?.context?.pb_access_workspace || 'hiring';
        this.state.studioFocus = this.props.focus || '';
        this.state.studio = null;
        this.state.studioError = '';
        this.state.studioBusy = false;
        this.state.studioSearch = '';
        this.state.studioProfileSearch = '';
        this.state.studioPeopleFilter = 'module';
        this.state.studioDirectory = [];
        this.state.studioPerson = null;
        this.state.studioKnownPeople = {};
        this.state.studioMenuReturn = null;
        this.studioPersonSeq = 0;
        this.state.studioStatus = 'active';
        this.state.studioSelected = [];
        this.state.studioDialog = null;
        this.state.studioReview = 'requests';
        this.state.studioRequestFilter = 'pending';
        this.state.studioPolicy = null;
        this.state.studioPolicyTab = 'permissions';
        this.state.studioResource = '';
        this.state.studioRoleSearch = '';
        this.state.studioResourceSearch = '';
        this.studioPolicySeq = 0;
        onWillUnmount(() => { clearTimeout(this.studioTimer); this.studioSeq++; this.studioPersonSeq++; this.passportSeq++; });
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
        if (!this.props.action?.context?.pb_edit_role) {
            const asked = this.props.action?.context?.pb_lens;
            this.state.lens = tabs.some(([key]) => key === asked) ? asked : 'people';
        }
    },
    get studioLocal() { return Boolean(this.props.focus); },
    get passport() {
        const passport = super.passport;
        // The local passport remains a combined read-only account preview.
        // Account-wide role and login changes belong to the central studio.
        return this.studioLocal && passport ? {...passport, can_manage: false,
            roles: passport.roles.map(role => ({...role, can_take_back: false}))} : passport;
    },
    get studioFocus() { return this.studio.focuses?.find(f => f.key === this.state.studioFocus); },
    get lenses() { return tabs.filter(([key]) => !this.studioLocal || ['people', 'packages', 'roles', 'handovers'].includes(key))
        .map(([key, icon, label]) => ({ key, icon, label: _t(this.studioLocal && key === 'roles' ? 'Roles' : label) })); },
    studioOpenCentral(lens = 'people', role = null) {
        return openHub(this.action, { xmlid: 'biz_access.action_pb_access_board', lens,
            context: { pb_access_workspace: role?.workspace || this.state.workspace, pb_studio_role: role?.id || false },
            back: this.props.hub ? { ...this.props.hub, lens: 'access' } : undefined });
    },
    get studio() { return this.state.studio || { profiles: [], roles: [], people: [], requests: [], history: [], resources: [], workspaces: [], departments: [], owners: [] }; },
    get studioCanManage() { return Boolean(this.studio.can_manage); },
    setLens(key) {
        key = key === 'studio_people' ? 'people' : key === 'policy' ? 'roles' : key;
        if (this.studioLocal && ['screens', 'reviews', 'studio_history'].includes(key)) return this.studioOpenCentral(key);
        super.setLens(key);
        if (key === 'roles' && !this.studioLocal && this.studioCanManage && !this.state.studioPolicy && this.studioRoles.length) {
            this.studioOpenPolicy(this.studioRoles.find(r => r.id === this.props.action?.context?.pb_studio_role) || this.studioRoles[0]);
        }
    },
    get studioRoleChoices() {
        const needle = this.state.studioRoleSearch.trim().toLocaleLowerCase();
        return this.studioRoles.filter(r => !needle || r.name.toLocaleLowerCase().includes(needle));
    },
    get studioResourceChoices() {
        const needle = this.state.studioResourceSearch.trim().toLocaleLowerCase();
        return this.studio.resources.filter(r => !needle || r.label.toLocaleLowerCase().includes(needle));
    },
    studioPolicyCell(resource, action) {
        return this.state.studioPolicy?.policy[resource.key]?.[action] || '';
    },
    studioSetScope(resource, action, value) {
        if (!this.state.studioPolicy.policy[resource.key]) {
            this.state.studioPolicy.policy[resource.key] = clone(this.state.studioPolicy.defaults[resource.key]);
        }
        this.state.studioPolicy.policy[resource.key][action] = value;
    },
    studioSelectResource(resource, tab = 'fields') {
        this.state.studioResource = resource.key;
        this.state.studioPolicyTab = tab;
    },
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
            {key:'people',n:this.studio.module_people_count || 0,label:_t('people with module roles'),tone:'',run:()=>this.setLens('people')},
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
            const data = await this.orm.call('pb.access', 'studio_data', [this.state.workspace, this.state.studioSearch, this.state.studioPeopleFilter, this.state.studioFocus || false]);
            if (seq !== this.studioSeq) return;
            let directory = [];
            if (this.state.studioPeopleFilter === 'directory' && this.canManage) {
                directory = await this.orm.call('pb.access', 'people', [this.state.studioSearch]);
                if (seq !== this.studioSeq) return;
            }
            this.state.studioDirectory = directory;
            this.state.studio = data;
            for (const person of [...data.people, ...directory]) this.state.studioKnownPeople[person.id] = person;
            this.state.peopleList = this.studioPeople;
            if (!this.studioCanManage) this.state.studioPeopleFilter = 'all';
            if (this.state.lens === 'people' && !this.state.personId && this.studioPeople.length) {
                await this.loadPassport(this.studioPeople[0].id);
            }
            this.state.studioError = '';
            if (this.state.lens === 'roles' && !this.state.studioPolicy) this.setLens('roles');
        } catch (e) {
            if (seq === this.studioSeq) this.state.studioError = this._msg(e, _t('Access Studio could not be loaded.'));
        }
    },
    async setWorkspace(ev) {
        this.studioPersonSeq++; this.passportSeq++;
        this.state.studio = null;
        this.state.personId = 0; this.state.passport = null; this.state.studioPerson = null;
        this.state.studioKnownPeople = {};
        this.state.studioMenuReturn = null; this.state.studioPeopleFilter = 'module';
        this.state.workspace = ev.target.value;
        this.state.area = '';
        this.state.search = '';
        this.state.studioSelected = [];
        this.state.studioPolicy = null;
        this.state.studioSearch = '';
        this.state.studioProfileSearch = '';
        this.state.studioRoleSearch = '';
        this.state.studioResourceSearch = '';
        this.studioPolicySeq++;
        this.state.open = 0;
        await this.reload();
        if (this.state.lens === 'roles') this.setLens('roles');
    },
    async studioChooseFocus(focus) {
        if (focus.key === this.state.studioFocus || this.state.studioBusy) return;
        this.state.studioFocus = focus.key;
        this.state.studioDialog = null;
        await this.setWorkspace({target: {value: focus.workspace}});
    },
    async studioSearch(ev) {
        this.state.studioSearch = ev.target.value;
        clearTimeout(this.studioTimer);
        this.studioTimer = setTimeout(() => this.loadStudio(), 250);
    },
    get studioPeople() {
        const needle = this.state.studioSearch.toLocaleLowerCase();
        if (this.state.studioPeopleFilter === 'directory' && this.canManage) return this.state.studioDirectory;
        return this.studio.people.filter(p => (!needle || `${p.name} ${p.login}`.toLocaleLowerCase().includes(needle)) &&
            (this.state.studioPeopleFilter !== 'module' || p.in_module) &&
            (this.state.studioPeopleFilter !== 'due' || p.assignments.some(a => a.due)));
    },
    // The legacy passport and Studio assignments now share one selected person.
    async loadPeople() {
        if (!this.state.studio) return;
        if (!this.state.personId && this.studioPeople.length) await this.loadPassport(this.studioPeople[0].id);
    },
    get peopleRows() { return this.studioPeople; },
    async studioFilterPeople(ev) {
        this.state.studioPeopleFilter = ev.target.value;
        this.state.studioSelected = [];
        await this.loadStudio();
    },
    get studioSelectedPerson() { return this.state.studioPerson; },
    get studioCanAssignPerson() {
        const p = this.studioSelectedPerson;
        return this.studioCanManage && p?.kind !== 'employee' && p?.in_company;
    },
    async loadPassport(id) {
        const seq = ++this.studioPersonSeq;
        ++this.passportSeq;
        this.state.personId = id;
        this.state.passport = null;
        this.state.studioPerson = null;
        this.state.passportFailed = '';
        this.state.passportBusy = true;
        try {
            const person = await this.orm.call('pb.access', 'studio_person', [this.state.workspace, id, this.state.studioFocus || false]);
            if (seq !== this.studioPersonSeq) return;
            this.state.studioPerson = person;
            this.state.studioKnownPeople[person.id] = person;
            if (this.canManage || id === this.board.me?.id) {
                await super.loadPassport(id);
            } else {
                // Keep module-owner scope: never call a privileged full-account
                // passport RPC just because its local assignments are visible.
                this.state.passport = {header: person, rail: [], roles: [], equivalent_roles: [],
                    can_manage: false, restricted_preview: true};
            }
        } catch (e) {
            if (seq === this.studioPersonSeq) this.state.passportFailed = this._msg(e, _t('This person could not be loaded.'));
        } finally {
            if (seq === this.studioPersonSeq) this.state.passportBusy = false;
        }
    },
    async studioOpenPassport(person) {
        this.closeStudio();
        this.state.studioMenuReturn = null;
        this.state.lens = 'people';
        await this.loadPassport(person.id);
    },
    async studioManageMenu() {
        if (this.studioLocal) return this.studioOpenCentral('screens');
        const person = this.passport?.header;
        if (!person || !this.canManage) return;
        this.state.studioMenuReturn = {id: person.id, name: person.name};
        await this.seeAs(person);
        this.setLens('screens');
    },
    get studioProfiles() {
        const needle = this.state.studioProfileSearch.toLocaleLowerCase();
        return this.studio.profiles.filter(p => (this.state.studioStatus === 'all' || p.active === (this.state.studioStatus === 'active')) &&
            (!needle || `${p.name} ${p.description}`.toLocaleLowerCase().includes(needle)));
    },
    get studioRequests() { return this.studio.requests.filter(r => this.state.studioRequestFilter === 'all' || r.state === this.state.studioRequestFilter); },
    get studioDue() { return this.studio.due_reviews || []; },
    get studioOwnerPeople() { return this.studio.owner_people || []; },
    get studioRoles() { return this.studio.roles.filter(r => this.studioLocal ? this.studio.role_ids?.includes(r.id) : r.workspace === this.state.workspace); },
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
        const eligible = this.studioPeople.filter(p => p.kind !== 'employee' && p.in_company !== false).slice(0, 100).map(p => p.id);
        this.state.studioSelected = eligible.every(id => this.state.studioSelected.includes(id)) ? [] : eligible;
    },
    studioOpenProfile(profile = null, duplicate = false) {
        if (this.studioLocal) return this.studioOpenCentral('packages');
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
        if (this.studioLocal) return this.studioOpenCentral('roles', role);
        const seq = ++this.studioPolicySeq;
        try {
            const policy = await this.orm.call('pb.access', 'studio_role_policy', [this.state.workspace, role.id]);
            if (seq !== this.studioPolicySeq) return;
            this.state.studioPolicy = policy;
            this.state.studioResource = this.studio.resources[0]?.key || '';
            this.state.studioPolicyTab = 'permissions';
            this.state.lens = 'roles';
        } catch (e) { this.notif.add(this._msg(e, _t('Policy could not be opened.')), { type: 'danger' }); }
    },
    studioEnableResource() {
        const resource = this.studioCurrentResource;
        this.state.studioPolicy.policy[resource.key] = clone(this.state.studioPolicy.defaults?.[resource.key] || { read: 'all', create: 'none', write: 'none', unlink: 'none',
            fields: Object.fromEntries(resource.fields.map(f => [f.key, 'view'])), create_fields: resource.fields.filter(f => !f.readonly).map(f => f.key),
            export: false, archive: false, reassign: false, approve: false, download: false, reveal: false,
            department_ids: [], states: [], write_states: [], match: 'all' });
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
            form: { user_id: this.studioOwnerPeople[0]?.id || 0, role_ids: [], active: true }, roleSearch: '', includeOtherModules: false, reason: '', error: '' };
        this.studioOwnerSelect({target: {value: this.state.studioDialog.form.user_id}});
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
            if (key === 'owner_id') return prefix + (this.studioOwnerPeople.find(p => p.id === item)?.name || 'User ' + item);
            if (key === 'auto_department_id') return prefix + (this.studio.departments.find(d => d.id === item)?.name || 'Manual assignment');
            if (Array.isArray(item)) return prefix + (item.map(x => fieldLabels[x] || words[x] || x).join(', ') || 'None');
            if (item && typeof item === 'object') return prefix + '\n' + pretty(item, depth+1);
            return prefix + (typeof item === 'boolean' ? (item ? 'Yes' : 'No') : words[item] || item || 'None');
        }).join('\n');
        return pretty(value);
    },
    studioNames(ids) { return ids.map(id => this.state.studioKnownPeople[id]?.name || '').filter(Boolean).join(', '); },
    get studioRequestPeople() {
        const people = [...this.studioOwnerPeople];
        for (const person of [this.studioSelectedPerson, this.board.me]) {
            if (person && !people.some(p => p.id === person.id)) people.push(person);
        }
        return people.filter(p => p.kind !== 'employee');
    },
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
                if (this.studioLocal) { await this.studioOpenCentral('reviews'); return; }
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

// The local hubs share the same catalogue, focused on their own workspace.
for (const [category, workspace, title, focus, hub, tag, where] of [
    ['pb_hiring_hub_lens', 'hiring', 'Hiring access', 'hiring.recruitment', {label:'Hiring', xmlid:'pb_hiring.action_pb_hiring_hub'}, 'pb_hiring_hub', _t('Hiring')],
    ['pb_people_hub_lens', 'people', 'People access', 'people.records', {label:'People', xmlid:'pb_people_hub.action_pb_people_hub'}, 'pb_people_hub', _t('People')],
    ['pb_payhub_lens', 'payroll', 'Payroll access', 'payroll.operations', {label:'Payroll', xmlid:'pb_payhub.action_pb_pay_hub'}, 'pb_pay_hub', _t('Payroll')],
]) {
    // RAIL FIT 2026-11-02 (owner): the rail word is ACCESS, the full name is
    // the tooltip, and it is pinned to the foot of the rail with the other
    // set-up items, so a long rail folds it first.
    registry.category(category).add('access_studio', {
        key: 'access', icon: 'shield', label: _t('Access'),
        title: _t('Access & delegation'), pinned: true, Component: PbAccessBoard,
        groups: ['base.group_user'], props: { embedded: true, workspace, focus, hub },
    });
    // Its ⌘K row, registered with the tab so the two cannot drift: the Access
    // home lists the screens inside each menu entry from these rows.
    registry.category('pb_hub_palette').add(`access_${workspace}_tab`, {
        id: `access_${workspace}_tab`, label: _t('Access'), sublabel: where,
        icon: 'shield', groups: ['base.group_user'], requires: tag,
        action: { xmlid: hub.xmlid, lens: 'access' },
        keywords: ['access & delegation', 'who can do what'],
    }, { sequence: 1490 });
}
