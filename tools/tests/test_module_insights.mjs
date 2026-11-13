import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// Execute the actual registration and hub configuration code. Only framework
// hooks/components are stubbed; destinations, props and access gates are real.
const categories = new Map();
const registry = { category(name) {
    if (!categories.has(name)) {
        const rows = new Map();
        categories.set(name, {
            add(key, value) { assert(!rows.has(key), `Duplicate ${name}/${key}`); rows.set(key, value); },
            get: key => rows.get(key), contains: key => rows.has(key),
            getAll: () => [...rows.values()],
        });
    }
    return categories.get(name);
} };
let mounted = [], navigation = [];
const symbols = {
    registry, Component: class {}, _t: s => s,
    useService: () => ({}), useState: value => value,
    onWillStart: () => {}, onMounted: cb => mounted.push(cb),
    openHub: (_, target) => navigation.push(target),
    LIFECYCLE_GATE: ['hr.group_hr_user'], HUB_LENS_GATES: 'gates',
    SETTINGS_CATEGORIES: 'settings', TALENT_LENSES: 'pb_talent_hub_lens',
    LEARNING_LENSES: 'pb_learning_hub_lens',
    PLAN_GATE: [], heroGroups: () => [],
};
function load(path) {
    let source = fs.readFileSync(path, 'utf8');
    const exports = [...source.matchAll(/export (?:const|class|function) (\w+)/g)].map(m => m[1]);
    source = source.replace(/import\s*\{([^}]+)\}\s*from\s*"[^"]+";/g, (_, names) => {
        for (const name of names.split(',').map(s => s.trim())) {
            if (!(name in symbols)) symbols[name] = class {};
        }
        return '';
    }).replace(/export (?=const|class|function)/g, '');
    const result = vm.runInNewContext(`(() => {${source}\nreturn {${exports.join(',')}};})()`, symbols, {filename: path});
    Object.assign(symbols, result);
    return result;
}
const moduleInsights = load('pb_insights/static/src/js/module_insights.js');
const hub = load('pb_insights_hub/static/src/js/insights_hub.js');
for (const name of ['hiring', 'goals', 'budget', 'training']) {
    load(`pb_${name}/static/src/js/${name}_palette.js`);
}
const hiring = load('pb_hiring/static/src/js/hiring_hub.js');
const people = load('pb_people_hub/static/src/js/people_hub.js');
const expenses = load('pb_expenses_hub/static/src/js/expenses_hub.js');
const payroll = load('pb_payhub/static/src/js/pay_hub.js');
load('pb_insights_hub/static/src/js/insights_hub_palette.js');
function setup(Class, context = {}) {
    const instance = new Class(); instance.props = {action: {context}};
    instance.setup(); return instance;
}
const workspace = setup(hiring.PbHiringHub);
const roles = workspace.config.lenses.find(l => l.key === 'roles');
const bank = workspace.config.lenses.find(l => l.key === 'bank');
assert.equal(roles.props.startTab, 'roles');
assert.equal(bank.props.startTab, 'bank');
assert.equal(bank.label, 'Resume bank');
assert.deepEqual([...bank.groups], ['pb_hiring.group_hiring_user']);
assert.equal(roles.probe.method, 'can_open');
assert.equal(workspace.config.lenses.filter(l => l.Component === moduleInsights.PbModuleInsights).length, 1);
assert.equal(workspace.config.lenses.find(l => l.key === 'numbers').props.area, 'hiring');
for (const [Class, area] of [
    [people.PbPeopleHub, 'people'], [expenses.PbExpensesHub, 'expenses'],
    [payroll.PbPayHub, 'payroll'],
]) {
    const lenses = setup(Class).config.lenses;
    assert.equal(lenses.filter(l => l.key === 'insights').length, 1, area);
    assert.equal(lenses.find(l => l.key === 'insights').props.area, area);
}
assert.deepEqual([...setup(hub.PbInsightsHub).config.lenses.map(l => l.key)], ['pulse', 'explorer', 'reports']);
assert.equal(registry.category('pb_hiring_hub_lens').get('numbers').probe.method, 'can_open');
assert.deepEqual([...registry.category('pb_payhub_lens').get('report').groups], [...hub.PAYSLIP_RUN_GATE]);
assert.equal(registry.category('pb_people_hub_lens').get('workforce').feature, 'insights');
assert.equal(registry.category('pb_learning_hub_lens').getAll().filter(l => l.Component === moduleInsights.PbModuleInsights).length, 1);
assert.equal(registry.category('pb_learning_hub_lens').get('numbers').props.area, 'learning');
assert.equal(registry.category('pb_talent_hub_lens').get('goal_numbers').props.area, 'talent');
assert(fs.readFileSync('pb_mission/static/src/js/pb_mission.js', 'utf8')
    .includes('registry.category(MISSION_LENSES).add("insights"'));
for (const [oldLens, destination] of Object.entries(hub.INSIGHT_DESTINATIONS)) {
    mounted = []; navigation = [];
    setup(hub.PbInsightsHub, {pb_lens: oldLens, pb_focus: 'month:current', company_id: 7});
    mounted.forEach(cb => cb());
    assert.equal(navigation.length, 1);
    assert.equal(navigation[0].xmlid, destination.xmlid);
    assert.equal(navigation[0].context.pb_lens, destination.lens);
    assert.equal(navigation[0].context.pb_focus, 'month:current');
    assert.equal(navigation[0].context.company_id, 7);
    assert(registry.category(destination.category).contains(destination.lens));
}
for (const key of ['inshub_workforce', 'inshub_payroll', 'bdg_board', 'bdg_month', 'hiring_analytics', 'goals_numbers', 'training_numbers']) {
    const entry = registry.category('pb_hub_palette').get(key);
    assert(entry, key);
    assert.notEqual(entry.action.xmlid, 'pb_insights_hub.action_pb_insights_hub');
    assert(entry.action.lens, key);
}
console.log('PASS: module insights lenses, report catalogue, legacy routes, search destinations and access gates');
