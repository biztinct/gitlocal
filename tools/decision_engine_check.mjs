#!/usr/bin/env node
/**
 * WFPLAN P1 — the twenty numbered facts the Decision Room's engine has to be
 * true about, checked without a browser and without a database.
 *
 *     node tools/decision_engine_check.mjs
 *
 * `pb_decision_room/static/src/js/decision_engine.js` and `decision_format.js`
 * import nothing, so they are loaded HERE EXACTLY AS THEY SHIP — read off disk
 * and handed to the runtime as a data: URL. No copy, no shim, no build step: a
 * check that runs against a transformed copy of the code is a check that can
 * pass while the shipped file is broken.
 *
 * T15 a plan with nothing changed reproduces heads x pay
 * T16 the profit bridge sums EXACTLY to the difference in profit
 * T17 ten people from month 3: December +10, recruiting only in month 3,
 *     and half their capacity in that month
 * T18 a senior hire costs more than a junior one in the same team
 * T19 the stress band holds the plan between softer and stronger demand
 * T20 you can never serve more than 100% of the work, and with no revenue
 *     target there is no revenue to serve
 *
 * Plus the guards that would otherwise only be found on screen: the money
 * formatter's two shapes, the goal ladder, and the state normaliser.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(HERE, "..", "pb_decision_room/static/src/js");

async function load(name) {
    const code = readFileSync(resolve(SRC, name), "utf8");
    const url = "data:text/javascript;base64,"
        + Buffer.from(code, "utf8").toString("base64");
    return import(url);
}

const E = await load("decision_engine.js");
const F = await load("decision_format.js");
const C = await load("decision_charts.js");

// ------------------------------------------------------------------ fixtures
const VND = { symbol: "₫", position: "after", decimals: 0, code: "VND" };
const fmt = F.makeFormat(VND);

/** A small, entirely explicit company: two teams, four roles, round numbers. */
const BASELINE = {
    asof: "2026-09-06",
    headcount: 300,
    source: "test",
    teams: [
        {
            key: "t1", name: "Manufacturing", department_id: 1, revenue: true,
            heads: 200, pay_month_avg: 10000000,
            roles: [
                { key: "r1", name: "Operators", job_id: 1, heads: 160,
                  pay_month_avg: 10000000, level: 1 },
                { key: "r2", name: "Plant director", job_id: 2, heads: 40,
                  pay_month_avg: 40000000, level: 4 },
            ],
        },
        {
            key: "t2", name: "Corporate", department_id: 2, revenue: false,
            heads: 100, pay_month_avg: 20000000,
            roles: [
                { key: "r3", name: "Admin", job_id: 3, heads: 60,
                  pay_month_avg: 15000000, level: 1 },
                { key: "r4", name: "Finance manager", job_id: 4, heads: 40,
                  pay_month_avg: 27500000, level: 3 },
            ],
        },
    ],
};

const FLAT = {
    employer_rate_pct: 23.5, employee_rate_pct: 10.5,
    contribution_cap: 46800000, allowance_pct: 12, ot_multiplier: 1.5,
    night_uplift_pct: 30, work_days: 22, recruit_cost_months: 1,
    severance_months: 1.5, ramp_first_month_pct: 50, attrition_pct_year: 12,
    bonus_month_index: 1, bonus_months: 1, other_fixed_monthly: 0,
    other_pct_revenue: 25, revenue_target: 0, demand_growth_pct: 0,
    pit_ladder: { personal: 11000000, dependent: 3960000,
                  bands: [[5000000, 5], [10000000, 10], [18000000, 15],
                          [32000000, 20], [52000000, 25], [80000000, 30],
                          [0, 35]] },
};

/** A version of the same company with a revenue target, so demand is on. */
const WITH_TARGET = { ...FLAT, revenue_target: 200000000000 };

// -------------------------------------------------------------------- runner
let failures = 0;
let checks = 0;
function ok(id, what, condition, detail = "") {
    checks++;
    if (condition) {
        console.log(`  ok   ${id.padEnd(4)} ${what}`);
        return;
    }
    failures++;
    console.log(`  FAIL ${id.padEnd(4)} ${what}${detail ? "\n         " + detail : ""}`);
}
const near = (a, b, tol) => Math.abs(a - b) <= tol;

console.log("\nThe Decision Room engine\n");

// ---------------------------------------------------------------------- T15
{
    const state = E.defaultState(BASELINE, FLAT);
    const plan = E.compute(BASELINE, FLAT, { ...state, bonusMonths: 0 });
    const expected = BASELINE.teams.reduce(
        (sum, t) => sum + t.roles.reduce(
            (s, r) => s + r.heads * r.pay_month_avg, 0), 0) * 12;
    ok("T15", "an untouched plan reproduces heads x pay within 0.5%",
       near(plan.year.base, expected, expected * 0.005),
       `base ${plan.year.base} vs ${expected}`);
    ok("T15b", "December headcount is the roster",
       plan.year.headcount === 300, `got ${plan.year.headcount}`);
    ok("T15c", "workforce cost is gross + contributions and nothing hidden",
       near(plan.year.people,
            plan.year.gross + plan.year.contributions + plan.year.recruit
            + plan.year.severance + plan.year.learning, 1e-6));
}

// ---------------------------------------------------------------------- T16
{
    const base = E.defaultState(BASELINE, WITH_TARGET);
    const ref = E.compute(BASELINE, WITH_TARGET, base);
    const plan = E.compute(BASELINE, WITH_TARGET, {
        ...base, raise: 7, ot: 12, growth: 15,
        moves: [{ team: "t1", role: null, n: 25, month: 4 }],
    });
    const b = E.bridge(plan, ref);
    const diff = plan.year.profit - ref.year.profit;
    ok("T16", "the profit bridge sums exactly to the difference in profit",
       b.check && near(b.total, diff, Math.abs(diff) * 1e-9),
       `total ${b.total} vs ${diff}`);
    ok("T16b", "and it has the seven steps the room names",
       b.steps.length === 7, `got ${b.steps.length}`);
}

// ---------------------------------------------------------------------- T17
{
    const base = E.defaultState(BASELINE, WITH_TARGET);
    const ref = E.compute(BASELINE, WITH_TARGET, base);
    const plan = E.compute(BASELINE, WITH_TARGET, {
        ...base, moves: [{ team: "t1", role: "r1", n: 10, month: 3 }],
    });
    ok("T17", "ten people from month 3 are ten more in December",
       near(plan.year.headcount - ref.year.headcount, 10, 1e-9),
       `delta ${plan.year.headcount - ref.year.headcount}`);
    ok("T17b", "nobody has arrived in February",
       near(plan.rows[1].heads, ref.rows[1].heads, 1e-9));
    const recruitMonths = plan.rows
        .map((r, i) => (r.recruit - ref.rows[i].recruit > 1 ? i : -1))
        .filter((i) => i >= 0);
    ok("T17c", "recruiting costs land in March and nowhere else",
       recruitMonths.length === 1 && recruitMonths[0] === 2,
       `months ${JSON.stringify(recruitMonths)}`);
    ok("T17d", "recruiting costs one month of their pay",
       near(plan.rows[2].recruit - ref.rows[2].recruit, 10 * 10000000, 1),
       `${plan.rows[2].recruit - ref.rows[2].recruit}`);
    // Half capacity in the arrival month: March's capacity gain must be half
    // of April's, because April is the first month they are fully productive.
    const march = plan.rows[2].capacity - ref.rows[2].capacity;
    const april = plan.rows[3].capacity - ref.rows[3].capacity;
    const marchShare = march / ref.rows[2].capacity;
    const aprilShare = april / ref.rows[3].capacity;
    ok("T17e", "they are half as productive in their first month",
       near(marchShare, aprilShare / 2, 1e-6),
       `march ${marchShare} vs april/2 ${aprilShare / 2}`);
}

// ---------------------------------------------------------------------- T18
{
    const base = E.defaultState(BASELINE, WITH_TARGET);
    const junior = E.compute(BASELINE, WITH_TARGET, {
        ...base, moves: [{ team: "t1", role: "r1", n: 10, month: 2 }],
    });
    const senior = E.compute(BASELINE, WITH_TARGET, {
        ...base, moves: [{ team: "t1", role: "r2", n: 10, month: 2 }],
    });
    ok("T18", "ten senior hires cost more than ten junior ones",
       senior.year.people > junior.year.people,
       `senior ${senior.year.people} vs junior ${junior.year.people}`);
    ok("T18b", "and the contribution cap does not erase the difference",
       senior.year.contributions >= junior.year.contributions);
}

// ---------------------------------------------------------------------- T19
{
    const base = E.defaultState(BASELINE, WITH_TARGET);
    const state = { ...base, growth: 10, ot: 8,
                    moves: [{ team: "t1", role: null, n: 20, month: 3 }] };
    const plan = E.compute(BASELINE, WITH_TARGET, state);
    const band = E.stressBand(BASELINE, WITH_TARGET, state);
    let held = true;
    for (let m = 0; m < 12; m++) {
        if (band.lo.rows[m].revenue > plan.rows[m].revenue + 1e-6
            || plan.rows[m].revenue > band.hi.rows[m].revenue + 1e-6) {
            held = false;
        }
    }
    ok("T19", "softer demand is never above the plan, stronger never below",
       held);
}

// ---------------------------------------------------------------------- T20
{
    const withT = E.compute(BASELINE, WITH_TARGET, {
        ...E.defaultState(BASELINE, WITH_TARGET),
        moves: [{ team: "t1", role: null, n: 80, month: 1 }],
    });
    ok("T20", "you can never serve more than all of the work",
       withT.rows.every((r) => r.coverage <= 1 + 1e-9)
       && withT.year.coverage <= 1 + 1e-9);
    const noT = E.compute(BASELINE, FLAT, E.defaultState(BASELINE, FLAT));
    ok("T20b", "with no revenue target there is no revenue, and coverage is 1",
       noT.year.revenue === 0 && noT.year.coverage === 1
       && noT.rows.every((r) => r.revenue === 0 && r.coverage === 1));
    ok("T20c", "and profit is then simply what the people cost",
       near(noT.year.profit, -(noT.year.people + noT.year.other), 1e-6));
}

// -------------------------------------------------------- the rest of the kit
{
    const state = E.normalizeState({
        target: -5, raise: 999, ot: "nonsense", month: 3, start: 99,
        moves: [{ team: "nope", n: 5, month: 2 },
                { team: "t1", n: 3, month: 40 }],
    }, BASELINE, FLAT);
    ok("N1", "the normaliser clamps, coerces and drops unknown teams",
       state.target === 0 && state.raise === 40 && state.ot === 0
       && state.start === 12 && state.moves.length === 1
       && state.moves[0].month === 12,
       JSON.stringify(state.moves));

    ok("N2", "a bonus month with no bonus is not a bonus",
       E.compute(BASELINE, { ...FLAT, bonus_month_index: 0 },
                 E.defaultState(BASELINE, FLAT)).year.bonus === 0);

    const plan = E.compute(BASELINE, WITH_TARGET,
                           E.defaultState(BASELINE, WITH_TARGET));
    const goals = E.defaultGoals(plan, true);
    const checksOut = E.evaluateGoals(plan, E.normalizeGoals(goals, plan, true),
                                      fmt);
    ok("N3", "the default goals are read off the company's own baseline",
       checksOut.length === 4
       && checksOut.every((c) => typeof c.actualText === "string"),
       checksOut.map((c) => `${c.key}:${c.met}`).join(" "));

    const cumulative = E.series(plan, "profit");
    ok("N4", "the profit line adds up through the year",
       near(cumulative[11], plan.year.profit, 1e-6));
    const monthly = E.series(plan, "coverage");
    ok("N5", "the coverage line is monthly, not cumulative",
       monthly.every((v) => v <= 100 + 1e-9));

    ok("N6", "the tax ladder is progressive and never negative",
       E.taxOn(0, FLAT.pit_ladder) === 0
       && E.taxOn(-1, FLAT.pit_ladder) === 0
       && E.taxOn(20000000, FLAT.pit_ladder)
          > E.taxOn(10000000, FLAT.pit_ladder));
}

// ----------------------------------------------------------- the formatter
{
    ok("F1", "a whole-unit currency reads B / M / k",
       fmt.money(1250000000) === "₫1.25B"
       && fmt.money(840000000) === "₫840M"
       && fmt.money(12500000) === "₫12.5M"
       && fmt.money(950000) === "₫950k",
       [fmt.money(1250000000), fmt.money(840000000), fmt.money(12500000),
        fmt.money(950000)].join(" "));
    const usd = F.makeFormat({ symbol: "$", position: "before", decimals: 2,
                               code: "USD" });
    ok("F2", "a decimal currency reads m / k",
       usd.money(1250000) === "$1.25m" && usd.money(840000) === "$840k"
       && usd.money(1250) === "$1,250",
       [usd.money(1250000), usd.money(840000), usd.money(1250)].join(" "));
    ok("F3", "a negative number wears a real minus sign",
       fmt.money(-1250000000) === "−₫1.25B", fmt.money(-1250000000));
    ok("F4", "the full figure honours the company's own symbol side",
       fmt.exact(1250000000) === "1,250,000,000 ₫", fmt.exact(1250000000));
    ok("F5", "a change is always signed, and 'no change' is not '+0'",
       fmt.signedMoney(1400000000) === "+₫1.4B"
       && fmt.signedMoney(0) === "₫0"
       && fmt.pp(-0.8) === "−0.8 pp"
       && fmt.people(24) === "+24 people"
       && fmt.people(1) === "+1 person",
       [fmt.signedMoney(1400000000), fmt.signedMoney(0), fmt.pp(-0.8),
        fmt.people(24)].join(" "));
}

// =====================================================================
//  WFPLAN P2 — shifts, the helpers behind the detail workspace, the goal
//  finder, the compact money box and the printable brief.
// =====================================================================

/** Shares that do NOT match, so a mismatch has something to show. */
const SKEWED = {
    ...WITH_TARGET,
    shift_evening_pct: 10, shift_night_pct: 5,
    demand_day_pct: 50, demand_evening_pct: 30, demand_night_pct: 20,
};
/** Matching shares and no uplift: Phase 1's arithmetic, exactly. */
const FLAT_SHIFTS = {
    ...WITH_TARGET,
    evening_uplift_pct: 0, night_uplift_pct: 0,
    shift_evening_pct: 25, shift_night_pct: 15,
    demand_day_pct: 60, demand_evening_pct: 25, demand_night_pct: 15,
};

// ---------------------------------------------------------------------- T28
{
    const base = E.defaultState(BASELINE, FLAT_SHIFTS);
    const plan = E.compute(BASELINE, FLAT_SHIFTS, {
        ...base, moves: [{ team: "t1", role: null, n: 30, month: 4 }],
    });
    let conserved = true;
    for (const row of plan.rows) {
        const heads = row.shifts.reduce((t, s) => t + s.heads, 0);
        // The revenue-earning teams only: t1 is the one marked `revenue`.
        if (!near(heads, row.headsByTeam.t1, 1e-6)) { conserved = false; }
    }
    ok("T28", "every revenue-earning head is on exactly one shift",
       conserved);
    ok("T28b", "matching shares serve all of the work, as Phase 1 did",
       near(plan.year.coverage, 1, 1e-9)
       && plan.rows.every((r) => near(r.coverage, 1, 1e-9)),
       `coverage ${plan.year.coverage}`);
    ok("T28c", "and with no uplift there is no premium to pay",
       plan.year.premium === 0);
    const withUplift = E.compute(BASELINE, WITH_TARGET, base);
    const without = E.compute(BASELINE, FLAT_SHIFTS, base);
    ok("T28d", "a night uplift costs money and nothing else moves",
       withUplift.year.premium > 0
       && near(withUplift.year.base, without.year.base, 1e-6)
       && near(withUplift.year.people - without.year.people,
               withUplift.year.premium
               - without.year.premium, 1e-6),
       `premium ${withUplift.year.premium}`);
}

// ---------------------------------------------------------------------- T29
{
    const base = E.defaultState(BASELINE, SKEWED);
    const before = E.compute(BASELINE, SKEWED, base);
    const balanced = E.balanceShifts(BASELINE, SKEWED, base);
    ok("T29", "matching shifts to demand puts the people where the work is",
       balanced.evening === 30 && balanced.night === 20,
       `evening ${balanced.evening} night ${balanced.night}`);
    const after = E.compute(BASELINE, SKEWED, balanced);
    let better = true;
    for (let m = 0; m < 12; m++) {
        for (let i = 0; i < 3; i++) {
            if (after.rows[m].shifts[i].served
                < before.rows[m].shifts[i].served - 1e-6) { better = false; }
        }
    }
    ok("T29b", "and no shift serves less work than it did before", better);
    ok("T29c", "the mismatch really was costing coverage",
       before.year.coverage < after.year.coverage - 1e-9,
       `${before.year.coverage} -> ${after.year.coverage}`);
}

// ---------------------------------------------------------------------- T30
{
    const base = E.defaultState(BASELINE, WITH_TARGET);
    const ref = E.compute(BASELINE, WITH_TARGET, base);
    const plan = E.compute(BASELINE, WITH_TARGET, {
        ...base, evening: 34, night: 22, ot: 10, raise: 4,
        moves: [{ team: "t1", role: null, n: 18, month: 5 }],
    });
    const b = E.bridge(plan, ref);
    const diff = plan.year.profit - ref.year.profit;
    ok("T30", "the bridge still sums exactly once shifts are in the picture",
       b.check && near(b.total, diff, Math.abs(diff) * 1e-9),
       `total ${b.total} vs ${diff}`);
    ok("T30b", "and every step says why in a sentence",
       b.steps.every((s) => typeof s.reason === "string"
                     && s.reason.length > 10),
       b.steps.map((s) => (s.reason || "").length).join(" "));
}

// ---------------------------------------------------------------------- T31
{
    const plan = E.compute(BASELINE, WITH_TARGET, {
        ...E.defaultState(BASELINE, WITH_TARGET), ot: 9, evening: 30,
        moves: [{ team: "t1", role: null, n: 12, month: 2 }],
    });
    const pay = E.payStory(plan);
    ok("T31", "gross less what is withheld is what reaches the employee",
       near(pay.gross - pay.withholding, pay.takehome, 1e-6));
    ok("T31b", "and the total is the whole cost to the business, once",
       near(pay.total, pay.gross + pay.contributions + pay.recruit
            + pay.severance + pay.learning, 1e-6)
       && near(pay.total, plan.year.people, 1e-6));
    // A RELATIVE tolerance: at ₫84 billion a double has about 1e-5 of
    // resolution left, so "adds up exactly" means to the last bit the
    // arithmetic has, not to a fixed number of decimal places.
    ok("T31c", "overtime and premiums are inside gross, not beside it",
       pay.premiums > 0 && pay.overtime > 0
       && near(plan.year.gross, plan.year.base + plan.year.allowance
               + plan.year.overtime + plan.year.premium + plan.year.bonus,
               Math.max(1e-6, plan.year.gross * 1e-9)),
       `premium ${pay.premiums} overtime ${pay.overtime}`);
}

// ---------------------------------------------------------------------- T32
{
    const BIG = {
        ...BASELINE,
        teams: [{ key: "t1", name: "Assembly", department_id: 1,
                  revenue: true, heads: 400, pay_month_avg: 9000000,
                  roles: [{ key: "r1", name: "Operators", job_id: 1,
                            heads: 400, pay_month_avg: 9000000, level: 1 }] },
                BASELINE.teams[1]],
    };
    const base = E.defaultState(BIG, WITH_TARGET);
    const plan = E.compute(BIG, WITH_TARGET, base);
    const goals = E.normalizeGoals(E.defaultGoals(plan, true), plan, true);
    const started = Date.now();
    const room = E.headroom(BIG, WITH_TARGET, base, goals, "t1", fmt);
    const ms = Date.now() - started;
    ok("T32", `headroom on a 400-person team answers fast (${ms} ms)`,
       ms < 150, `${ms} ms over ${room.points.length} points`);
    // The intervals must be EXACTLY the runs of met points, not an
    // approximation of them: a range that claims a point it did not test is
    // a hiring recommendation with a hole in it.
    const runs = [];
    let open = null;
    for (const p of room.points) {
        if (p.met && open === null) { open = p.add; }
        if ((!p.met || p.add === room.points[room.points.length - 1].add)
            && open !== null) {
            const last = p.met ? p.add : open;
            const previous = room.points[room.points.indexOf(p) - 1];
            runs.push([open, p.met ? last
                : (previous ? previous.add : open)]);
            open = null;
        }
    }
    ok("T32b", "its ranges are exactly the runs of points that met the goals",
       JSON.stringify(room.intervals) === JSON.stringify(runs),
       `${JSON.stringify(room.intervals)} vs ${JSON.stringify(runs)}`);
    ok("T32c", "and the scan is bounded and says how it stepped",
       room.max <= 200 && room.step >= 1 && room.points.length <= 61,
       `max ${room.max} step ${room.step} points ${room.points.length}`);
}

// ---------------------------------------------------------------------- T33
{
    // The real company-5 roster when it has been exported, a company of the
    // same SHAPE when it has not — the check is about how long the search
    // takes over thirteen teams of real size, not about whose names are in it.
    let big = null;
    try {
        big = JSON.parse(readFileSync(
            resolve(HERE, "fixtures", "company5_baseline.json"), "utf8"));
    } catch (e) {
        big = {
            asof: "2026-09-06", headcount: 4533, source: "synthetic",
            teams: Array.from({ length: 13 }, (_, t) => ({
                key: `t${t + 1}`, name: `Team ${t + 1}`, department_id: t + 1,
                revenue: t % 4 !== 0, heads: 350 - t * 10,
                pay_month_avg: 9000000 + t * 400000,
                roles: Array.from({ length: 12 }, (_, r) => ({
                    key: `t${t + 1}r${r + 1}`, name: `Role ${r + 1}`,
                    job_id: r + 1, heads: Math.max(1, 30 - r * 2),
                    pay_month_avg: 8000000 + r * 900000,
                    level: (r % 4) + 1,
                })),
            })),
        };
    }
    const source = big.source === "synthetic"
        ? "a company of the same shape" : "the real company-5 roster";
    const base = E.defaultState(big, WITH_TARGET);
    const plan = E.compute(big, WITH_TARGET, base);
    const goals = E.normalizeGoals(E.defaultGoals(plan, true), plan, true);
    const started = Date.now();
    const found = E.candidates(big, WITH_TARGET, base, goals, fmt);
    const ms = Date.now() - started;
    ok("T33", `the goal finder answers in under 400 ms on ${source} (${ms} ms)`,
       ms < 400, `${ms} ms over ${found.count} combinations`);
    ok("T33b", "it offers three directions, each with a plan behind it",
       found.lanes.length === 3
       && found.lanes.every((l) => l.result && Array.isArray(l.checks)),
       found.lanes.map((l) => l.lane).join(" "));
    ok("T33c", "ranked by goals missed first, then by how narrowly",
       found.lanes.every((l) => l.failed
           <= l.checks.filter((c) => !c.met).length + 1e-9));
    const develop = found.lanes.find((l) => l.lane === "develop");
    const hire = found.lanes.find((l) => l.lane === "hire");
    ok("T33d", "the develop lane hires nobody and the hire lane keeps "
       + "productive time",
       (develop.state.moves || []).length === 0
       && hire.state.productivity === base.productivity,
       `develop moves ${JSON.stringify(develop.state.moves)}`);
}

// ---------------------------------------------------------------------- T34
{
    const base = E.defaultState(BASELINE, WITH_TARGET);
    const plan = E.compute(BASELINE, WITH_TARGET, base);
    const goals = E.normalizeGoals({
        margin: { on: true, target: 95 },
        profit: { on: false, target: 0 },
        cost: { on: false, target: 0 },
        coverage: { on: false, target: 0 },
        heads: { on: false, target: 0 },
        overtime: { on: false, target: 0 },
    }, plan, true);
    const found = E.candidates(BASELINE, WITH_TARGET, base, goals, fmt);
    ok("T34", "goals nobody can meet are reported, not hidden",
       found.lanes.length === 3
       && found.lanes.every((l) => l.met === false && l.failed >= 1
                            && l.checks.some((c) => !c.met)),
       found.lanes.map((l) => `${l.lane}:${l.failed}`).join(" "));
    const none = E.candidates(BASELINE, WITH_TARGET, base,
        E.normalizeGoals({
            margin: { on: false, target: 0 }, profit: { on: false, target: 0 },
            cost: { on: false, target: 0 }, coverage: { on: false, target: 0 },
            heads: { on: false, target: 0 },
            overtime: { on: false, target: 0 },
        }, plan, true), fmt);
    ok("T34b", "with nothing switched on the search says so instead of "
       + "guessing", none.enabled === false && none.lanes.length === 0);
}

// ---------------------------------------------------------------------- T35
{
    ok("T35", "the money box reads what a person types",
       F.parseCompact("2,200 B") === 2.2e12
       && F.parseCompact("1.5m") === 1.5e6
       && F.parseCompact("₫950k", "₫") === 950000
       && F.parseCompact("2200b") === 2.2e12
       && F.parseCompact("2.2 t") === 2.2e12
       && F.parseCompact("2200000000000") === 2.2e12,
       [F.parseCompact("2,200 B"), F.parseCompact("1.5m"),
        F.parseCompact("₫950k", "₫"), F.parseCompact("2.2 t")].join(" "));
    ok("T35b", "and refuses what is not a number, without pretending it is 0",
       F.parseCompact("abc") === null && F.parseCompact("") === null
       && F.parseCompact("12x") === null && F.parseCompact("1.2.3") === null,
       String(F.parseCompact("abc")));
    const round = [2.2e12, 950000, 12500000, 1400000000, 0];
    ok("T35c", "what it shows is what it reads back",
       round.every((v) => Math.abs(fmt.parse(fmt.compact(v)) - v)
                   <= Math.max(1, Math.abs(v) * 0.005)),
       round.map((v) => `${fmt.compact(v)}->${fmt.parse(fmt.compact(v))}`)
           .join(" "));
    ok("T35d", "a real minus sign survives the round trip",
       fmt.parse(fmt.compact(-1.25e9)) === -1.25e9,
       `${fmt.compact(-1.25e9)} -> ${fmt.parse(fmt.compact(-1.25e9))}`);
    ok("T35e", "an arrow press moves the unit on screen",
       fmt.step(2.2e12) === 1e9 && fmt.step(950000) === 1e3);
}

// ---------------------------------------------------------------------- T36
{
    const base = E.defaultState(BASELINE, WITH_TARGET);
    const ref = E.compute(BASELINE, WITH_TARGET, base);
    const state = { ...base, raise: 6, ot: 12,
                    moves: [{ team: "t1", role: null, n: 25, month: 4 }] };
    const plan = E.compute(BASELINE, WITH_TARGET, state);
    const goals = E.normalizeGoals(E.defaultGoals(ref, true), ref, true);
    const model = E.briefModel({
        plan, ref, baseline: BASELINE, assumptions: WITH_TARGET, state,
        refState: base, goals, format: fmt,
        planName: "Board draft", comparisonName: "Today",
        assumptionLines: [{ title: "Who this is about", copy: "300 people." }],
    });
    ok("T36", "the brief carries all twelve months",
       model.months.length === 12 && model.months[0].name === "January"
       && model.months[11].name === "December",
       model.months.map((m) => m.name).join(","));
    ok("T36b", "and names every decision that differs from the comparison",
       model.changes.length >= 3
       && model.changes.some((line) => line.includes("Manufacturing"))
       && model.changes.some((line) => line.toLowerCase().includes("overtime")),
       JSON.stringify(model.changes));
    ok("T36c", "with the goals, the outcome, the bridge and every input",
       model.goals.length >= 1 && model.outcome.length === 10
       && model.bridge.length === 7 && model.inputs.length === 15
       && model.assumptions.length === 1
       && model.plan_name === "Board draft",
       `${model.goals.length} ${model.outcome.length} ${model.bridge.length}`);
    ok("T36d", "every value in it is already a finished piece of text",
       model.months.every((m) => typeof m.cost === "string")
       && model.outcome.every((r) => typeof r.plan === "string")
       && typeof model.bridge_total === "string");
}

// =====================================================================
//  WFPLAN P3 — Vietnamese money, the experiment that scales with the team,
//  and the tween that always arrives.
// =====================================================================

// ---------------------------------------------------------------------- T41
{
    const vi = F.makeFormat(VND, "vi_VN");
    ok("T41", "Vietnamese money is said in Vietnamese words",
       vi.compact(2.2e12) === "\u20ab2.200 t\u1ef7"
       && vi.compact(8.4e8) === "\u20ab840 tri\u1ec7u"
       && vi.compact(1.25e7) === "\u20ab12,5 tri\u1ec7u",
       [vi.compact(2.2e12), vi.compact(8.4e8), vi.compact(1.25e7)].join(" "));
    ok("T41b", "and read back, however it is written",
       vi.parse("2.200 t\u1ef7") === 2.2e12
       && vi.parse("840 trieu") === 8.4e8
       && vi.parse("2,2 t\u1ef7") === 2.2e9
       && vi.parse("\u20ab12,5 tri\u1ec7u") === 1.25e7,
       [vi.parse("2.200 t\u1ef7"), vi.parse("840 trieu"),
        vi.parse("2,2 t\u1ef7")].join(" "));
    const trip = [2.2e12, 8.4e8, 1.25e7, 950000, 0];
    ok("T41c", "what a Vietnamese reader sees is what the box reads back",
       trip.every((v) => Math.abs(vi.parse(vi.compact(v)) - v)
                  <= Math.max(1, Math.abs(v) * 0.005)),
       trip.map((v) => `${vi.compact(v)}->${vi.parse(vi.compact(v))}`)
           .join(" "));
    ok("T41d", "percentages and whole figures take the Vietnamese marks too",
       vi.pct(23.5) === "23,5%" && vi.exact(1234567) === "1.234.567 \u20ab",
       `${vi.pct(23.5)} ${vi.exact(1234567)}`);
    ok("T41e", "and English is exactly what it always was",
       fmt.compact(2.2e12) === "\u20ab2,200B"
       && fmt.compact(8.4e8) === "\u20ab840M"
       && fmt.compact(1.25e7) === "\u20ab12.5M"
       && fmt.parse("2,200 B") === 2.2e12 && fmt.pct(23.5) === "23.5%",
       [fmt.compact(2.2e12), fmt.compact(1.25e7), fmt.pct(23.5)].join(" "));
    ok("T41f", "an arrow press still moves the unit on screen in either "
       + "language", vi.step(2.2e12) === 1e9 && vi.step(950000) === 1e3);
}

// ---------------------------------------------------------------------- T42
{
    ok("T42", "one small experiment is one per cent of the team",
       E.experimentSize(4533) === 45 && E.experimentSize(40) === 5
       && E.experimentSize(0) === 5 && E.experimentSize(500) === 5
       && E.experimentSize(2000) === 20 && E.experimentSize(2300) === 25,
       [4533, 40, 0, 500, 2000, 2300].map(E.experimentSize).join(" "));
    ok("T42b", "and it is always a number somebody would say out loud",
       [0, 7, 40, 300, 999, 2401, 4533, 12000].every((h) => {
           const n = E.experimentSize(h);
           return n >= 5 && (n <= 20 || n % 5 === 0);
       }));
    const base = E.defaultState(BASELINE, WITH_TARGET);
    const plan = E.compute(BASELINE, WITH_TARGET, base);
    const n = E.experimentSize(200);            // the Manufacturing team
    const step = E.marginal(BASELINE, WITH_TARGET, base, plan, "t1", n);
    ok("T42c", "the engine costs exactly the number the card offers",
       step && step.n === n
       && Math.abs(step.plan.year.headcount
                   - plan.year.headcount - n) < 1e-6,
       step ? `${step.n} -> ${step.plan.year.headcount
           - plan.year.headcount}` : "no step");
}

// ---------------------------------------------------------------------- T43
{
    const from = [0, 10, 20];
    const to = [100, 110, 120];
    const half = C.tweenSeries(from, to, 0.5, true);
    ok("T43", "a chart travels half way when it is half way",
       half[0] === 50 && half[1] === 60 && half[2] === 70, half.join(" "));
    ok("T43b", "and arrives EXACTLY, not 0.999 of the way there",
       C.tweenSeries(from, to, 1, true) === to
       && C.tweenSeries(from, to, 1.4, true) === to
       && JSON.stringify(C.tweenSeries(from, to, 1, true)) ===
          JSON.stringify(to));
    ok("T43c", "with motion off there is no travel at all",
       C.tweenSeries(from, to, 0.5, false) === to
       && C.tweenSeries(null, to, 0.5, true) === to
       && C.tweenSeries([1, 2], to, 0.5, true) === to,
       "a first draw and a changed length both go straight there");
    ok("T43d", "and the easing starts and ends where it should",
       C.easeOut(0) === 0 && C.easeOut(1) === 1
       && C.easeOut(0.5) > 0.5 && C.easeOut(2) === 1
       && C.easeOut(-1) === 0, `${C.easeOut(0.5)}`);
}

// =====================================================================
//  GROUP Phase 4 — scope, several companies, several currencies
// =====================================================================

/** The single-company scope the room has always drawn, in the new shape. */
const ONE_BLOCK = {
    ...BASELINE,
    single: true,
    blocks: [{ company_id: 1, company: "Payobook Vietnam JSC",
               currency: { code: "VND" }, teams: BASELINE.teams,
               rules: FLAT, headcount: 300 }],
};

/** Two companies, two currencies: one VND, one SGD. */
const SG_RULES = { ...FLAT, employer_rate_pct: 17, employee_rate_pct: 20,
                   contribution_cap: 6800, night_uplift_pct: 0,
                   work_days: 21, pit_ladder: { bands: [] } };
const TWO_BLOCKS = {
    asof: "2026-09-07", headcount: 320, source: "test", single: false,
    mixed: true,
    teams: [
        { key: "c1", name: "Payobook Vietnam JSC", heads: 300,
          pay_month_avg: 16000000, revenue: true, roles: [
              { key: "t1", name: "Manufacturing", job_id: 0, heads: 200,
                pay_month_avg: 10000000, level: 1 },
              { key: "t2", name: "Corporate", job_id: 0, heads: 100,
                pay_month_avg: 20000000, level: 1 },
          ] },
        { key: "c2", name: "Payobook Singapore Pte Ltd", heads: 20,
          pay_month_avg: 8000, revenue: true, roles: [
              { key: "t9", name: "Sales", job_id: 0, heads: 20,
                pay_month_avg: 8000, level: 1 },
          ] },
    ],
    blocks: [],
};
TWO_BLOCKS.blocks = [
    { company_id: 1, company: "Payobook Vietnam JSC",
      currency: { code: "VND" }, teams: [TWO_BLOCKS.teams[0]], rules: FLAT,
      headcount: 300 },
    { company_id: 2, company: "Payobook Singapore Pte Ltd",
      currency: { code: "SGD" }, teams: [TWO_BLOCKS.teams[1]],
      rules: SG_RULES, headcount: 20 },
];

/** One SGD = 18,000 VND, every month, and VND is the board's money. */
const RATES = {
    target: { code: "VND" },
    rows: {
        SGD: Array.from({ length: 12 }, (_v, m) => ({
            month: m + 1, rate: 18000, known: true,
            rate_date: `2026-${String(m + 1).padStart(2, "0")}-28`,
        })),
    },
    unknown: [], known: true,
};

/** The same table with August missing, which is the state that matters. */
const RATES_GAP = {
    ...RATES,
    rows: { SGD: RATES.rows.SGD.map((cell, m) => (
        m === 7 ? { month: 8, rate: 0, known: false, rate_date: "" } : cell)) },
    unknown: [{ code: "SGD", note: "no rate for August" }],
    known: false,
};

// ---------------------------------------------------------------------- T48
{
    // The identity the whole phase rests on: ONE company through the new
    // multi-block path is the same arithmetic, to the last bit.
    const state = { ...E.defaultState(BASELINE, FLAT), raise: 6, ot: 12,
                    moves: [{ team: "t1", role: null, n: 20, month: 4 }] };
    const before = E.compute(BASELINE, FLAT, state);
    const after = E.computeBlocks(ONE_BLOCK, state, { target: {}, rows: {} });
    ok("T48", "one company through the group path is the same numbers",
       after.single === true
       && after.group.year.people === before.year.people
       && after.group.year.profit === before.year.profit
       && after.group.year.headcount === before.year.headcount
       && JSON.stringify(after.group.rows) === JSON.stringify(before.rows),
       `${after.group.year.people} vs ${before.year.people}`);
}

// ---------------------------------------------------------------------- T49
{
    const state = { ...E.defaultState(TWO_BLOCKS, FLAT), target: 0 };
    const run = E.computeBlocks(TWO_BLOCKS, state, RATES);
    const vn = run.blocks[0].plan.year.people;
    const sg = run.blocks[1].plan.year.people;
    ok("T49", "a group total is each company converted, and nothing else",
       near(run.group.year.people, vn + sg * 18000, 1),
       `${run.group.year.people} vs ${vn + sg * 18000}`);
    ok("T49b", "and every company keeps its OWN rules",
       run.blocks[0].rules.employer_rate_pct === 23.5
       && run.blocks[1].rules.employer_rate_pct === 17
       && run.blocks[1].plan.year.contributions > 0);
    ok("T49c", "heads simply add up — a person is not converted",
       run.group.year.headcount
       === run.blocks[0].plan.year.headcount
          + run.blocks[1].plan.year.headcount);
}

// ---------------------------------------------------------------------- T50
{
    const state = { ...E.defaultState(TWO_BLOCKS, FLAT), target: 0 };
    const run = E.computeBlocks(TWO_BLOCKS, state, RATES_GAP);
    const vnAug = run.blocks[0].plan.rows[7].people;
    ok("T50", "a month nobody has priced leaves that company OUT of the total",
       near(run.group.rows[7].people, vnAug, 1),
       `${run.group.rows[7].people} vs ${vnAug}`);
    ok("T50b", "and the company and the months are named, never guessed",
       run.unknown.length === 1 && run.unknown[0].code === "SGD"
       && run.unknown[0].months.length === 1
       && run.unknown[0].months[0] === 7,
       JSON.stringify(run.unknown));
    ok("T50c", "the plan's own rows stay in the company's own money",
       run.blocks[1].plan.rows[7].people > 0
       && run.blocks[1].plan.rows[7].people < 1000000,
       `${run.blocks[1].plan.rows[7].people}`);
}

// ---------------------------------------------------------------------- T51
{
    const shares = E.targetShares(TWO_BLOCKS.blocks);
    ok("T51", "the revenue target is shared by where the pay bill actually is",
       near(shares[0] + shares[1], 1, 1e-9) && shares[0] > shares[1],
       shares.map((s) => s.toFixed(4)).join(" / "));
    const state = { ...E.defaultState(TWO_BLOCKS, FLAT),
                    target: 200000000000 };
    const run = E.computeBlocks(TWO_BLOCKS, state, RATES);
    ok("T51b", "and each company is given its share in its OWN money",
       near(run.blocks[1].target * 18000, 200000000000 * shares[1], 1),
       `${run.blocks[1].target}`);
    ok("T51c", "so the group serves what the group was asked to serve",
       run.group.year.revenue > 0 && run.group.year.coverage <= 1.0000001,
       `${run.group.year.coverage}`);
}

// ---------------------------------------------------------------------- T52
{
    ok("T52", "the board's own money is never converted",
       E.rateFor(RATES, "VND", 3).rate === 1
       && E.rateFor(RATES, "VND", 3).known === true);
    ok("T52b", "a currency with no row at all is unknown, not one for one",
       E.rateFor(RATES, "IDR", 3).known === false
       && E.rateFor(RATES, "IDR", 3).rate === 0);
}

// ---------------------------------------------------------------------- T53
{
    const actuals = {
        available: true, year: 2026,
        months: [
            { month: 1, people: 300,
              by_company: { 1: { cost: 6000000000, currency: "VND",
                                 people: 300 } } },
            { month: 2, people: 305,
              by_company: { 1: { cost: 6200000000, currency: "VND",
                                 people: 305 },
                            2: { cost: 100000, currency: "SGD",
                                 people: 5 } } },
        ],
    };
    const monthly = E.actualSeries(actuals, RATES, false);
    const running = E.actualSeries(actuals, RATES, true);
    ok("T53", "a month with no closed run is nothing, and nothing is not zero",
       monthly[0] === 6000000000 && monthly[2] === null
       && monthly[1] === 6200000000 + 100000 * 18000,
       `${monthly[1]}`);
    ok("T53b", "and the line the stage draws is cumulative",
       running[1] === monthly[0] + monthly[1] && running[2] === null);
    ok("T53c", "people are counted, never converted",
       E.actualPeople(actuals)[1] === 305
       && E.actualPeople(actuals)[5] === null);
}

// ---------------------------------------------------------------------- T54
{
    const plan = E.compute(BASELINE, FLAT, E.defaultState(BASELINE, FLAT));
    const actuals = {
        available: true, year: 2026,
        months: [{ month: 1, people: Math.round(plan.rows[0].heads) + 40,
                   by_company: { 1: { cost: plan.rows[0].people * 1.2,
                                      currency: "VND",
                                      people: Math.round(plan.rows[0].heads)
                                              + 40 } } }],
    };
    const said = E.actualVerdict(plan, actuals, RATES, fmt);
    ok("T54", "the verdict names the month, the gap and the bigger reason",
       said.includes("January") && said.includes("over plan")
       && said.includes("more people"), said);
    const none = E.actualVerdict(plan, { available: false, months: [] },
                                 RATES, fmt);
    ok("T54b", "and with no closed run it says so instead of drawing nothing",
       none.length > 20 && !none.includes("undefined"), none);
}

// ---------------------------------------------------------------------- T55
{
    // The engine's search functions must be able to run a GROUP trial, or the
    // goal finder and the headroom scan would quietly plan one company.
    const state = E.defaultState(TWO_BLOCKS, FLAT);
    const run = (trial) => E.computeBlocks(TWO_BLOCKS, trial, RATES).group;
    const band = E.stressBand(TWO_BLOCKS, FLAT, state, 10, run);
    const direct = run(state);
    ok("T55", "a stress band over a group is a group on both sides",
       band.lo.year.people === direct.year.people
       && band.hi.year.people === direct.year.people,
       "no revenue target, so demand cannot move cost");
    const step = E.marginal(TWO_BLOCKS, FLAT, state, direct, "c2", 5, run);
    ok("T55b", "and five more people in the Singapore entity cost SGD, read "
       + "in VND", step && step.dCost > 0
       && near(step.dCost,
               (E.computeBlocks(TWO_BLOCKS,
                                { ...state, moves: [{ team: "c2", role: null,
                                                      n: 5, month: state.start }] },
                                RATES).group.year.people
                - direct.year.people), 1),
       step ? String(Math.round(step.dCost)) : "no step");
}

console.log(`\n${checks - failures}/${checks} checks passed\n`);
process.exit(failures ? 1 : 0);
