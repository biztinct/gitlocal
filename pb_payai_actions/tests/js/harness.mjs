/**
 * PAYAI FIX-1 — a tiny loader that runs the product's own ES modules in node.
 *
 * No browser, no OWL, no bundler: each source file is read from disk, its
 * `import … from "<spec>"` lines are rewritten, and the result is imported.
 *   - a spec listed in `real` is loaded the same way (recursively), from
 *     `<root>/<module>/static/src/<rest>.js` — the bundler's own mapping;
 *   - every other spec becomes a stub from `globalThis.__pb` (OWL hooks that
 *     record what a component asked for, `_t`, a registry, services).
 *
 * `mount(Cls, props, env)` is the part of OWL the tests need: construct, run
 * `setup()`, then await every `onWillStart` callback in order.
 *
 * Usage: `node pb_payai_actions/tests/js/client_fix.test.mjs`
 *        (PB_SRC_ROOT=<dir> loads the product files from another tree, e.g.
 *        a `git archive` of an older commit, to watch a test fail there.)
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = process.env.PB_SRC_ROOT
    || path.resolve(HERE, "..", "..", "..");
const OUT = fs.mkdtempSync(path.join(os.tmpdir(), "pb-js-harness-"));

// ------------------------------------------------------------------ stubs
const hookCtx = { current: null };

function sprintf(text, ...args) {
    let i = 0;
    const flat = args.length === 1 && args[0] && typeof args[0] === "object"
        ? args[0] : null;
    return String(text)
        .replace(/%\((\w+)\)s/g, (_m, k) => (flat ? String(flat[k]) : ""))
        .replace(/%s/g, () => String(args[i++]));
}

class StubComponent {
    constructor(props, env) {
        this.props = props || {};
        this.env = env || {};
    }
    setup() {}
}

function makeRegistry() {
    const cats = new Map();
    const category = (name) => {
        if (!cats.has(name)) {
            const content = {};
            const cat = {
                content,
                add(key, value, opts = {}) {
                    content[key] = [opts.sequence || 50, value];
                    return cat;
                },
                get(key, dflt) { return key in content ? content[key][1] : dflt; },
                contains(key) { return key in content; },
                remove(key) { delete content[key]; },
                getAll() {
                    return Object.values(content).sort((a, b) => a[0] - b[0])
                        .map((x) => x[1]);
                },
                category,
            };
            cats.set(name, cat);
        }
        return cats.get(name);
    };
    return { category };
}

const pb = {
    services: {},
    patches: [],
    hookCtx,
    registry: makeRegistry(),
};
globalThis.__pb = pb;

const KNOWN = {
    Component: StubComponent,
    useState: (x) => x,
    useRef: () => ({ el: null }),
    useEffect: () => {},
    markup: (x) => x,
    onWillStart: (fn) => hookCtx.current && hookCtx.current.willStart.push(fn),
    onMounted: (fn) => hookCtx.current && hookCtx.current.mounted.push(fn),
    onWillUnmount: () => {},
    onWillUpdateProps: () => {},
    useService: (name) => pb.services[name],
    _t: sprintf,
    patch: (target, obj) => {
        Object.setPrototypeOf(obj, Object.getPrototypeOf(obj) === Object.prototype
            ? target : Object.getPrototypeOf(obj));
        pb.patches.push({ target, obj });
    },
    get registry() { return pb.registry; },
    isMacOS: () => false,
    user: { userId: 2, context: {} },
    featuresState: () => null,
    featureGate: () => ({ shown: true, locked: false, text: "" }),
    publishPlace: () => {},
    clearPlace: () => {},
    resolveLensAccess: async () => null,
    ic: () => "",
    initials: () => "",
    money: (a) => String(a),
    when: (w) => String(w),
};

pb.stub = (spec) => new Proxy({}, {
    get(_t, name) {
        if (name in KNOWN) { return KNOWN[name]; }
        if (spec === "@web/core/network/rpc" && name === "rpc") {
            return (...args) => pb.rpc(...args);
        }
        if (/^[A-Z][A-Z0-9_]+$/.test(String(name))) { return String(name); }
        if (/^[A-Z]/.test(String(name))) {
            // an unknown class: a component or a dialog
            return class extends StubComponent {};
        }
        return () => null;
    },
});
pb.rpc = async () => { throw new Error("no rpc stub"); };

// ----------------------------------------------------------------- loader
function specToFile(spec) {
    const m = /^@([^/]+)\/(.+)$/.exec(spec);
    if (!m) { throw new Error(`not a module spec: ${spec}`); }
    return path.join(ROOT, m[1], "static", "src", `${m[2]}.js`);
}

const done = new Map();

function transform(src, real) {
    const rewrite = (names, spec) => {
        if (real.includes(spec)) {
            return `import {${names}} from ${JSON.stringify(build(spec, real))};`;
        }
        const fields = names.split(",").map((n) => n.trim()).filter(Boolean)
            .map((n) => n.replace(/\s+as\s+/, ": ")).join(", ");
        return `const {${fields}} = globalThis.__pb.stub(${JSON.stringify(spec)});`;
    };
    return src
        .replace(/^import\s*\{([^}]*)\}\s*from\s*"([^"]+)";?/gm,
                 (_m, names, spec) => rewrite(names, spec))
        .replace(/^import\s+(\w+)\s+from\s*"([^"]+)";?/gm,
                 (_m, name, spec) => `const ${name} = globalThis.__pb.stub(${JSON.stringify(spec)});`);
}

function build(spec, real) {
    if (done.has(spec)) { return done.get(spec); }
    const file = specToFile(spec);
    const out = path.join(OUT, `${spec.replace(/[^\w]+/g, "_")}.mjs`);
    const url = pathToFileURL(out).href;
    done.set(spec, url);
    fs.writeFileSync(out, transform(fs.readFileSync(file, "utf-8"), real));
    return url;
}

/** Import one product module; `real` lists the specs NOT to stub. */
export async function load(spec, real = []) {
    return import(build(spec, [spec, ...real]));
}

/** Construct, `setup()`, then every `onWillStart` in order — OWL's order. */
export async function mount(Cls, props = {}, env = {}, { start = true } = {}) {
    const hooks = { willStart: [], mounted: [] };
    hookCtx.current = hooks;
    const comp = new Cls(props, env);
    comp.setup();
    hookCtx.current = null;
    if (start) {
        for (const fn of hooks.willStart) { await fn(); }
    }
    return comp;
}

// ---------------------------------------------------------------- asserts
let failures = 0;
let passes = 0;
export function check(ok, label, detail = "") {
    if (ok) {
        passes += 1;
        console.log(`  ok   ${label}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${label}${detail ? ` — ${detail}` : ""}`);
    }
}
export function summary() {
    console.log(`${passes} passed, ${failures} failed`);
    fs.rmSync(OUT, { recursive: true, force: true });
    process.exitCode = failures ? 1 : 0;
}
