const fs = require('fs');
const assert = require('assert/strict');
const { JSDOM } = require(process.env.STUDIO_NODE_MODULES + '/jsdom');
const dom = new JSDOM('<html><body><div id="app"></div></body></html>',
    { runScripts: 'outside-only', pretendToBeVisual: true });
const w = dom.window;
w.eval(fs.readFileSync('web/static/lib/owl/owl.js', 'utf8'));
const owl = w.owl;
class Dummy extends owl.Component {}
Dummy.template = owl.xml`<div/>`;
Dummy.props = ['*'];
const calls = [], destinations = [];
const meta = { measures: [
    { key: 'employees', label: 'Active employee records', note: 'Active today', dimensions: ['department', 'company'], has_time: false, kind: 'count' },
    { key: 'joined', label: 'First contracts started', note: 'By date', dimensions: ['department', 'company'], has_time: true, kind: 'count' },
] };
const rows = [{ key: '1', label: 'Operations', period: '', value: 7, records: 7 }];
const orm = { call: async (model, method, args) => {
    calls.push([model, method, args]);
    if (method === 'catalogue') return [{ area: 'people', label: 'Employee records', xmlid: 'pb_people_hub.action_pb_people_hub', lens: 'employees' }];
    if (method === 'measures') return meta;
    if (method === 'overview') return { tiles: [{ key: 'employees', label: 'Active employee records', value: 7, kind: 'count', note: 'Active today' }] };
    if (method === 'explore') return { label: 'Active employee records', total: 7, kind: 'count', currency: '', note: 'Active today', over: 'total', rows };
} };
const action = {};
const source = fs.readFileSync('pb_insights/static/src/js/module_insights.js', 'utf8')
    .replace(/import\s*\{[^}]+\}\s*from\s*"[^"]+";/g, '')
    .replace(/export (?=const|class|function)/g, '');
const built = w.Function('Component', 'onWillStart', 'useState', 'useService', '_t', 'openHub', 'ic', 'PbInsights',
    `${source}\nreturn {PbModuleInsights};`)(owl.Component, owl.onWillStart, owl.useState,
    key => ({ orm, action })[key], s => s, (_, dest) => destinations.push(dest), () => '', Dummy);
const templates = fs.readFileSync('pb_insights/static/src/xml/module_insights.xml', 'utf8');
const tick = () => new Promise(resolve => w.setTimeout(resolve, 25));
(async () => {
    const app = new owl.App(built.PbModuleInsights, {
        templates, props: { area: 'people', embedded: true },
        env: { services: { orm, action } },
    });
    await app.mount(w.document.getElementById('app'));
    assert(w.document.body.textContent.includes('Overview'));
    assert(w.document.body.textContent.includes('Active employee records'));
    const button = label => [...w.document.querySelectorAll('button')].find(b => b.textContent.trim() === label);
    button('Explorer').click();
    await tick(); await tick();
    assert(calls.some(c => c[1] === 'explore'));
    assert(w.document.body.textContent.includes('Operations'));
    button('Reports').click(); await tick();
    assert(w.document.body.textContent.includes('Employee records'));
    button('Employee records').click(); await tick();
    assert.equal(destinations.at(-1).xmlid, 'pb_people_hub.action_pb_people_hub');
    assert.equal(destinations.at(-1).back.lens, 'insights');
    app.destroy();
    w.close();
    console.log('PASS mounted module Insights: overview, explorer result, original report route and back link');
})().catch(error => { console.error(error); process.exitCode = 1; });
