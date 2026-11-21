import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';

const source = readFileSync(new URL('../../static/src/interactions/clock.js', import.meta.url), 'utf8')
    .replace(/^import .*;\n/gm, '').replaceAll('export class ', 'class ');
function fixture({ server = 20_000_000, since = server - 20_262_000 } = {}) {
    let now = 50_000_000;
    const nodes = Object.fromEntries(['h', 'm', 's', 'hwrap'].map(k => [k, { textContent: '', classList: { toggle() {} } }]));
    const intervals = [];
    const ctx = vm.createContext({ Interaction: class {}, registry: { category: () => ({ add() {} }) },
        Date: { now: () => now }, Number, Math, String,
        window: { setInterval: (fn, ms) => intervals.push({fn, ms}), clearInterval() {} },
        document: { visibilityState: 'visible' },
    });
    vm.runInContext(source + '\nglobalThis.Clock = PbEwClockLive;', ctx);
    const clock = new ctx.Clock();
    clock.el = { dataset: {state:'in', sinceMs:String(since), serverNowMs:String(server)},
        querySelector: s => nodes[s.match(/data-pbew-(\w+)/)?.[1]] || null };
    clock.registerCleanup = () => {};
    clock.addListener = () => {};
    clock.setup(); clock.start();
    return {nodes, intervals, clock, advance: ms => {now += ms; clock.tick();}};
}
test('seconds tick every second using server time despite a skewed device clock', () => {
    const f = fixture();
    assert.equal(f.intervals[0].ms, 1000);
    assert.deepEqual(['h','m','s'].map(k => f.nodes[k].textContent), ['5','37','42']);
    f.advance(1000);
    assert.equal(f.nodes.s.textContent, '43');
    f.advance(17_000);
    assert.deepEqual(['h','m','s'].map(k => f.nodes[k].textContent), ['5','38','00']);
});
test('returning after a suspended tab catches up rather than counting interval calls', () => {
    const f = fixture(); f.advance(3_600_000);
    assert.deepEqual(['h','m','s'].map(k => f.nodes[k].textContent), ['6','37','42']);
});
test('future timestamps never produce negative elapsed time', () => {
    const f = fixture({server:20_000_000,since:20_060_000});
    assert.deepEqual(['h','m','s'].map(k => f.nodes[k].textContent), ['0','0','00']);
});
