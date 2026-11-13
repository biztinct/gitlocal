// Run with node --test. Exercises the real standalone page script with a tiny DOM.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.resolve(__dirname, '../../../pb_clock/static/setup/setup.js'), 'utf8');
function page() {
    const elements = new Map();
    const pending = [];
    const deadlines = new Map();
    let timerID = 0;
    const get = id => {
        if (!elements.has(id)) elements.set(id, {hidden: false, textContent: '', className: '', events: {}, attributes: {},
            addEventListener(name, fn) {this.events[name] = fn;},
            setAttribute(name, value) {this.attributes[name] = value;},
            removeAttribute(name) {delete this.attributes[name];}});
        return elements.get(id);
    };
    vm.runInNewContext(source, {
        document: {body: {dataset: {manager: '1', csrf: 'test', backUrl: '/bizapp/action-1/1'}},
            getElementById: get, querySelectorAll: () => []},
        navigator: {userAgent: 'Windows'}, location: {hash: '', origin: 'https://example.invalid'},
        URLSearchParams, AbortController, Date,
        setTimeout(fn) {const id = ++timerID; deadlines.set(id, fn); return id;},
        clearTimeout(id) {deadlines.delete(id);}, setInterval() {},
        fetch(url, options) {return new Promise((resolve, reject) => {
            pending.push({url, options, resolve, reject});
            options.signal.addEventListener('abort', () => reject(Object.assign(new Error('timeout'), {name: 'AbortError'})));
        });},
    });
    const tick = () => new Promise(resolve => setImmediate(resolve));
    const status = {company: 'Test', name: 'PC', state: 'connected', history_from: '2026-09-01', timezone: 'Asia/Ho_Chi_Minh', interval_minutes: 15,
        last_contact: new Date().toISOString().slice(0,19).replace('T',' '), last_read: new Date().toISOString().slice(0,19).replace('T',' '), pending: 0};
    return {get, pending, deadlines, tick, status,
        async answer(data = status) {pending.shift().resolve({ok: true, json: async () => data}); await tick();}};
}
test('manual connection check shows activity, prevents overlap, and renders receipt beside button', async () => {
    const p = page(); await p.answer();
    assert.match(p.get('check-summary').textContent, /Sync received/);
    const request = p.get('refresh').events.click();
    assert.equal(p.get('refresh').disabled, true);
    assert.equal(p.get('refresh').textContent, 'Checking...');
    await p.get('refresh').events.click(); assert.equal(p.pending.length, 1);
    await p.answer({...p.status, pending: 8}); await request;
    assert.equal(p.get('refresh').disabled, false);
    assert.match(p.get('check-details').textContent, /8 records/);
    assert.match(p.get('check-time').textContent, /Checked/);
});
test('timeout is visible locally and a later success clears it', async () => {
    const p = page(); await p.answer();
    const request = p.get('refresh').events.click();
    [...p.deadlines.values()][0](); await request;
    assert.equal(p.get('refresh').disabled, false);
    assert.match(p.get('check-summary').textContent, /timed out/);
    assert.match(p.get('check-result').className, /error/);
    p.pending.shift();
    const retry = p.get('refresh').events.click(); await p.answer(); await retry;
    assert.equal(p.get('check-result').className, 'check-result good');
    assert.match(p.get('check-summary').textContent, /Sync received/);
});
test('unpaired and collection-error states do not claim success', async () => {
    const p = page(); await p.answer({...p.status, state: 'new', last_read: false});
    assert.match(p.get('check-summary').textContent, /Awaiting setup/);
    const request = p.get('refresh').events.click();
    await p.answer({...p.status, needs_attention: true}); await request;
    assert.match(p.get('check-summary').textContent, /collection issue/);
    assert.doesNotMatch(p.get('check-summary').textContent, /Sync received/);
});
