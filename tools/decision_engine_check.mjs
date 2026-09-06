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

console.log(`\n${checks - failures}/${checks} checks passed\n`);
process.exit(failures ? 1 : 0);
