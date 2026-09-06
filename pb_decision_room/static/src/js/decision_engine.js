/** @odoo-module **/
/**
 * The Decision Room engine — twelve months of a company, from a handful of
 * levers.
 *
 * Ported from the proof of concept at `design_poc/wfplan/src/core.js`, with two
 * substantive changes and nothing else invented:
 *
 *   1. **The company is real.** The proof of concept carried six hard-coded
 *      divisions and fictional US dollars. This engine is handed the SERVER's
 *      baseline — the company's own teams, roles, headcount and monthly pay, in
 *      the company's own currency — and never scales it. Scaling to "₫1.25B" is
 *      the formatter's job and happens once, on screen.
 *   2. **The assumptions are a record.** Contribution rates, the cap, the
 *      allowance share, the overtime multiplier, working days, recruiting and
 *      severance cost, the bonus month and the income-tax ladder come from
 *      `pb.decision.assumptions`, so a reader can be shown exactly what the
 *      picture believed.
 *
 * Everything else is the proof of concept's semantics, kept deliberately:
 * contributions capped, allowances as a share of base, overtime at a multiplier
 * of the hourly rate, the bonus in its month, recruiting cost in the month a
 * hire arrives, severance in the month a role ends, a new person paid in full
 * but only half productive in their first month, leavers and their backfill,
 * the mild seasonal curve, and the demand model — capacity follows the people
 * who earn revenue, revenue is the smaller of demand and capacity.
 *
 * This file imports NOTHING, so `node tools/decision_engine_check.mjs` can load
 * it exactly as it ships.
 */

/** Mild Vietnamese seasonality. Sums to 12, so a flat year is a flat year. */
export const SEASON = [0.86, 0.78, 0.95, 1.00, 1.02, 1.04,
                       1.02, 1.03, 1.05, 1.08, 1.10, 1.07];

/** What "today" means for the levers the roster cannot tell us. */
export const DEFAULT_ABSENCE = 8;

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const num = (v, fallback = 0) => (Number.isFinite(Number(v)) ? Number(v) : fallback);

export function cloneState(state) {
    return JSON.parse(JSON.stringify(state || {}));
}

// ---------------------------------------------------------------- assumptions
/** Every assumption, with a sane value even when the record is empty. */
export function readAssumptions(a) {
    const raw = a || {};
    return {
        erRate: num(raw.employer_rate_pct, 23.5) / 100,
        eeRate: num(raw.employee_rate_pct, 10.5) / 100,
        cap: Math.max(0, num(raw.contribution_cap, 0)),
        allowance: num(raw.allowance_pct, 12) / 100,
        otMult: num(raw.ot_multiplier, 1.5),
        nightUplift: num(raw.night_uplift_pct, 30) / 100,
        workDays: Math.max(1, num(raw.work_days, 22)),
        recruitMonths: Math.max(0, num(raw.recruit_cost_months, 1)),
        severanceMonths: Math.max(0, num(raw.severance_months, 1.5)),
        ramp: clamp(num(raw.ramp_first_month_pct, 50), 0, 100) / 100,
        attritionYear: Math.max(0, num(raw.attrition_pct_year, 12)),
        bonusMonth: clamp(Math.round(num(raw.bonus_month_index, 1)), 0, 12),
        bonusMonths: Math.max(0, num(raw.bonus_months, 1)),
        otherFixed: Math.max(0, num(raw.other_fixed_monthly, 0)),
        otherPct: num(raw.other_pct_revenue, 25) / 100,
        target: Math.max(0, num(raw.revenue_target, 0)),
        growth: num(raw.demand_growth_pct, 0),
        ladder: raw.pit_ladder && typeof raw.pit_ladder === "object"
            ? raw.pit_ladder : { bands: [] },
    };
}

/** Monthly income tax on one person's taxable pay. Never touches company cost. */
export function taxOn(taxable, ladder) {
    const bands = (ladder && ladder.bands) || [];
    if (!bands.length || taxable <= 0) { return 0; }
    let tax = 0;
    let previous = 0;
    for (const band of bands) {
        const top = num(band[0], 0);
        const rate = num(band[1], 0) / 100;
        const ceiling = top > 0 ? top : Infinity;
        const slice = Math.min(taxable, ceiling) - previous;
        if (slice <= 0) { break; }
        tax += slice * rate;
        previous = ceiling;
        if (!Number.isFinite(ceiling)) { break; }
    }
    return tax;
}

// --------------------------------------------------------------------- state
/** The default plan: the company exactly as it is today. */
export function defaultState(baseline, assumptions) {
    const a = readAssumptions(assumptions);
    const now = new Date();
    return {
        target: a.target,
        growth: a.growth,
        stress: 0,
        raise: 0,
        raiseMonth: 1,
        ot: 0,
        otFrom: 1,
        attritionOn: false,
        backfill: true,
        bonusMonths: a.bonusMonths,
        productivity: 0,
        absence: DEFAULT_ABSENCE,
        start: clamp(now.getMonth() + 2, 1, 12),
        moves: [],
    };
}

/** Everything inside its range, every field present, nothing else carried. */
export function normalizeState(state, baseline, assumptions) {
    const base = defaultState(baseline, assumptions);
    const s = state || {};
    const teams = ((baseline && baseline.teams) || []);
    const teamByKey = Object.fromEntries(teams.map((t) => [t.key, t]));
    const moves = Array.isArray(s.moves) ? s.moves : [];
    return {
        target: Math.max(0, num(s.target, base.target)),
        growth: clamp(num(s.growth, base.growth), -50, 100),
        stress: clamp(num(s.stress, 0), -30, 30),
        raise: clamp(num(s.raise, 0), -20, 40),
        raiseMonth: clamp(Math.round(num(s.raiseMonth, 1)), 1, 12),
        ot: clamp(num(s.ot, 0), 0, 60),
        otFrom: clamp(Math.round(num(s.otFrom, 1)), 1, 12),
        attritionOn: !!s.attritionOn,
        backfill: s.backfill === undefined ? true : !!s.backfill,
        bonusMonths: clamp(num(s.bonusMonths, base.bonusMonths), 0, 4),
        productivity: clamp(num(s.productivity, 0), -20, 40),
        absence: clamp(num(s.absence, DEFAULT_ABSENCE), 0, 40),
        start: clamp(Math.round(num(s.start, base.start)), 1, 12),
        moves: moves
            .filter((m) => m && teamByKey[m.team] && Math.round(num(m.n, 0)))
            .map((m) => ({
                team: m.team,
                role: m.role || null,
                n: Math.round(num(m.n, 0)),
                month: clamp(Math.round(num(m.month, 1)), 1, 12),
            })),
    };
}

/** How many people a move puts into one role, this month. */
function moveShare(move, team, role) {
    if (move.role) { return move.role === role.key ? move.n : 0; }
    const total = team.roles.reduce((sum, r) => sum + r.heads, 0) || 1;
    return move.n * (role.heads / total);
}

// ------------------------------------------------------------------- compute
/**
 * Twelve months of this company under this plan.
 *
 * @param {object} baseline    the server's roster: {teams:[{roles:[…]}], …}
 * @param {object} assumptions the assumptions record
 * @param {object} state       the levers
 * @returns {{rows:Array, year:object, teams:Array}}
 */
export function compute(baseline, assumptions, state) {
    const a = readAssumptions(assumptions);
    const s = normalizeState(state, baseline, assumptions);
    const teams = (baseline && baseline.teams) || [];

    const rows = [];
    const teamOut = teams.map((t) => ({
        key: t.key, name: t.name, revenue: !!t.revenue,
        headsToday: t.heads, heads: new Array(12).fill(0),
        cost: new Array(12).fill(0), year: 0,
    }));
    const revHeads = new Array(12).fill(0);      // paid revenue-earning heads
    const revCapHeads = new Array(12).fill(0);   // the same, ramped
    let revHeadsBase = 0;
    const totals = { hires: 0, cuts: 0, leavers: 0 };

    const attritionRate = s.attritionOn ? (a.attritionYear / 100 / 12) : 0;

    for (let m = 0; m < 12; m++) {
        const row = {
            name: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
                   "Sep", "Oct", "Nov", "Dec"][m],
            index: m, heads: 0, headsByTeam: {}, base: 0, allowance: 0,
            salary: 0, overtime: 0, premium: 0, bonus: 0, contributions: 0,
            recruit: 0, severance: 0, learning: 0, people: 0, gross: 0,
            withholding: 0, takehome: 0, demand: 0, capacity: 0, revenue: 0,
            coverage: 1, other: 0, profit: 0, margin: 0,
        };
        const otHours = (m + 1) >= s.otFrom ? s.ot : 0;

        teams.forEach((team, ti) => {
            let teamHeads = 0;
            let teamCost = 0;
            for (const role of team.roles) {
                // ---- how many people are in this role, this month --------
                let n = role.heads;
                let arriving = 0;
                let leaving = 0;
                for (const move of s.moves) {
                    if (move.team !== team.key) { continue; }
                    const share = moveShare(move, team, role);
                    if (!share) { continue; }
                    if ((m + 1) >= move.month) { n += share; }
                    if ((m + 1) === move.month) {
                        if (share > 0) { arriving += share; }
                        else { leaving += -share; }
                    }
                }
                if (attritionRate && !s.backfill) {
                    n -= role.heads
                        * (1 - Math.pow(1 - attritionRate, m + 1));
                }
                n = Math.max(0, n);

                // ---- what a month of that costs ---------------------------
                const pay = role.pay_month_avg
                    * (1 + ((m + 1) >= s.raiseMonth ? s.raise / 100 : 0));
                const base = n * pay;
                const allowance = base * a.allowance;
                const hourly = pay / (a.workDays * 8);
                const overtime = n * hourly * a.otMult * otHours;
                const premium = 0;   // the shift levers arrive with Phase 2
                const capped = a.cap > 0 ? Math.min(pay, a.cap) : pay;
                const contributions = n * capped * a.erRate;
                const bonus = (a.bonusMonth && (m + 1) === a.bonusMonth)
                    ? base * s.bonusMonths : 0;

                let recruit = arriving * pay * a.recruitMonths;
                const severance = leaving * pay * a.severanceMonths;
                if (attritionRate && s.backfill) {
                    recruit += role.heads * attritionRate * pay
                        * a.recruitMonths;
                }
                if (attritionRate) {
                    totals.leavers += role.heads * attritionRate;
                }
                totals.hires += arriving;
                totals.cuts += leaving;

                // ---- what reaches the employee ---------------------------
                const perPerson = n > 0
                    ? (pay + allowance / n + overtime / n) : 0;
                const employeeIns = capped * a.eeRate;
                const ladder = a.ladder;
                const personal = num(ladder.personal, 0)
                    + num(ladder.dependent, 0);
                const tax = taxOn(perPerson - employeeIns - personal, ladder);
                const withholding = n * (employeeIns + tax);

                const gross = base + allowance + overtime + premium + bonus;

                row.heads += n;
                row.base += base;
                row.allowance += allowance;
                row.salary += base + allowance;
                row.overtime += overtime;
                row.premium += premium;
                row.bonus += bonus;
                row.contributions += contributions;
                row.recruit += recruit;
                row.severance += severance;
                row.gross += gross;
                row.withholding += withholding;

                teamHeads += n;
                teamCost += gross + contributions + recruit + severance;

                if (team.revenue) {
                    // Capacity counts a new arrival at the ramp for the month
                    // they land in: they are paid in full and only partly
                    // productive, and pretending otherwise is the single most
                    // flattering lie a planner can tell.
                    revHeads[m] += n;
                    revCapHeads[m] += n - arriving * (1 - a.ramp);
                    if (m === 0) { revHeadsBase += role.heads; }
                }
            }
            row.headsByTeam[team.key] = teamHeads;
            teamOut[ti].heads[m] = teamHeads;
            teamOut[ti].cost[m] = teamCost;
        });

        row.people = row.gross + row.contributions + row.recruit
            + row.severance + row.learning;
        row.takehome = row.gross - row.withholding;
        rows.push(row);
    }

    // ------------------------------------------------ what the year earns
    const hoursBase = (a.workDays * 8) * (1 - DEFAULT_ABSENCE / 100);
    const target = s.target;
    for (let m = 0; m < 12; m++) {
        const row = rows[m];
        const otHours = (m + 1) >= s.otFrom ? s.ot : 0;
        const hoursNow = (a.workDays * 8 + otHours)
            * (1 - s.absence / 100) * (1 + s.productivity / 100);
        const hoursFactor = hoursBase > 0 ? (hoursNow / hoursBase) : 1;
        const today = target / 12 * SEASON[m];
        if (target > 0) {
            row.demand = today
                * (1 + s.growth / 100 * (m + 1) / 12)
                * (1 + s.stress / 100);
            row.capacity = revHeadsBase > 0
                ? today * (revCapHeads[m] / revHeadsBase) * hoursFactor
                : today * hoursFactor;
            row.revenue = Math.min(row.demand, row.capacity);
            row.coverage = row.demand > 0 ? row.revenue / row.demand : 1;
        } else {
            row.demand = 0;
            row.capacity = 0;
            row.revenue = 0;
            row.coverage = 1;
        }
        row.other = a.otherFixed + row.revenue * a.otherPct;
        row.profit = row.revenue - row.people - row.other;
        row.margin = row.revenue > 0 ? row.profit / row.revenue : 0;
    }

    const sum = (key) => rows.reduce((total, r) => total + r[key], 0);
    const year = {};
    for (const key of ["heads", "base", "allowance", "salary", "overtime",
                       "premium", "bonus", "contributions", "recruit",
                       "severance", "learning", "people", "gross",
                       "withholding", "takehome", "demand", "capacity",
                       "revenue", "other", "profit"]) {
        year[key] = sum(key);
    }
    year.headcount = rows[11] ? rows[11].heads : 0;
    year.headsAvg = year.heads / 12;
    year.coverage = year.demand > 0 ? year.revenue / year.demand : 1;
    year.unserved = Math.max(0, year.demand - year.revenue);
    year.margin = year.revenue > 0 ? year.profit / year.revenue : 0;
    year.costPerHead = year.headsAvg > 0 ? year.people / year.headsAvg : 0;
    year.peopleShare = year.revenue > 0 ? year.people / year.revenue : 0;
    year.peakMonth = rows.reduce(
        (best, r) => (r.people > rows[best].people ? r.index : best), 0);
    year.worstMonth = rows.reduce(
        (worst, r) => (r.profit < rows[worst].profit ? r.index : worst), 0);
    year.hires = Math.round(totals.hires);
    year.cuts = Math.round(totals.cuts);
    year.leavers = Math.round(totals.leavers);

    teamOut.forEach((t) => {
        t.year = t.cost.reduce((total, v) => total + v, 0);
    });

    return { rows, year, teams: teamOut, state: s };
}

// --------------------------------------------------------------------- goals
/**
 * The six things a plan can be asked to be. `value` reads a computed plan;
 * `format` needs the company's formatter, so it is passed in rather than
 * imported — the engine stays free of everything.
 */
export const GOAL_DEFS = {
    margin: {
        key: "margin", label: "Operating margin", short: "Margin",
        sense: "min", unit: "%", step: 0.5, min: -50, max: 80,
        value: (plan) => plan.year.margin * 100,
        format: (v, f) => f.pct(v),
    },
    profit: {
        key: "profit", label: "Operating profit for the year", short: "Profit",
        sense: "min", unit: "money", step: 1, min: -1e15, max: 1e15,
        value: (plan) => plan.year.profit,
        format: (v, f) => f.money(v),
    },
    cost: {
        key: "cost", label: "Workforce cost for the year", short: "Cost",
        sense: "max", unit: "money", step: 1, min: 0, max: 1e15,
        value: (plan) => plan.year.people,
        format: (v, f) => f.money(v),
    },
    coverage: {
        key: "coverage", label: "Demand served", short: "Served",
        sense: "min", unit: "%", step: 0.5, min: 0, max: 100,
        value: (plan) => plan.year.coverage * 100,
        format: (v, f) => f.pct(v),
    },
    heads: {
        key: "heads", label: "People in December", short: "Team size",
        sense: "max", unit: "people", step: 1, min: 0, max: 1e7,
        value: (plan) => plan.year.headcount,
        format: (v, f) => f.int(v) + " people",
    },
    overtime: {
        key: "overtime", label: "Overtime per person", short: "Overtime",
        sense: "max", unit: "h/mo", step: 1, min: 0, max: 60,
        value: (plan) => plan.state.ot,
        format: (v) => `${Math.round(v)} h a month`,
    },
};

export const GOAL_ORDER = ["margin", "profit", "cost", "coverage", "heads",
                           "overtime"];

/** The goals a company starts with, read off its own baseline. */
export function defaultGoals(basePlan, hasTarget) {
    const year = basePlan.year;
    // Rounded AWAY from the baseline, never towards it: "at least this year's
    // profit" must be a goal today's company MEETS, or the room opens with a
    // red pill saying you are ₫0 short of yourself.
    return {
        margin: { on: !!hasTarget, target: 20 },
        profit: { on: !!hasTarget, target: Math.floor(year.profit) },
        cost: { on: true, target: Math.ceil(year.people * 1.1) },
        coverage: { on: !!hasTarget, target: 97 },
        heads: { on: false, target: Math.ceil(year.headcount * 1.1) },
        overtime: { on: false, target: 8 },
    };
}

export function normalizeGoals(input, basePlan, hasTarget) {
    const fallback = defaultGoals(basePlan, hasTarget);
    const given = input || {};
    const out = {};
    for (const key of GOAL_ORDER) {
        const def = GOAL_DEFS[key];
        const raw = given[key] || fallback[key];
        const value = num(raw && raw.target, fallback[key].target);
        out[key] = {
            on: typeof (raw && raw.on) === "boolean" ? raw.on : fallback[key].on,
            target: clamp(def.step === 1 ? Math.round(value) : value,
                          def.min, def.max),
        };
    }
    return out;
}

export function evaluateGoals(plan, goals, format) {
    const out = [];
    for (const key of GOAL_ORDER) {
        const g = goals[key];
        if (!g || !g.on) { continue; }
        const def = GOAL_DEFS[key];
        const actual = def.value(plan);
        const gap = def.sense === "min" ? (g.target - actual)
            : (actual - g.target);
        // A RELATIVE epsilon: at ₫300 billion a double has about 1e-5 of
        // resolution left, and an absolute 1e-8 makes a goal that is exactly
        // met read as missed by nothing at all.
        const epsilon = Math.max(1e-8, Math.abs(g.target) * 1e-9);
        out.push({
            key, def, short: def.short, label: def.label, sense: def.sense,
            actual, target: g.target, gap, met: gap <= epsilon,
            shortfall: Math.max(0, gap) / Math.max(Math.abs(g.target), 1),
            actualText: def.format(actual, format),
            targetText: def.format(g.target, format),
        });
    }
    return out;
}

export function gradeGoals(plan, goals, format) {
    const checks = evaluateGoals(plan, goals, format);
    return {
        checks,
        met: checks.every((c) => c.met),
        failed: checks.filter((c) => !c.met).length,
        score: checks.reduce((total, c) => total + c.shortfall, 0),
    };
}

/** The line the stage draws: cumulative for money, monthly for a percentage. */
export function series(plan, metric) {
    if (metric === "coverage") {
        return plan.rows.map((r) => r.coverage * 100);
    }
    const key = metric === "people" ? "people" : "profit";
    let running = 0;
    return plan.rows.map((r) => (running += r[key]));
}

// ------------------------------------------------------------------- extras
/** The same plan under softer and stronger demand. */
export function stressBand(baseline, assumptions, state, width = 10) {
    const s = normalizeState(state, baseline, assumptions);
    return {
        lo: compute(baseline, assumptions, { ...s, stress: s.stress - width }),
        hi: compute(baseline, assumptions, { ...s, stress: s.stress + width }),
    };
}

/**
 * Why profit is different. Every step is an accounting difference, and they
 * sum EXACTLY to the difference in profit — `check` says so out loud.
 */
export function bridge(plan, ref) {
    const p = plan.year;
    const r = ref.year;
    const steps = [
        ["Revenue delivered", p.revenue - r.revenue,
         "What the team could actually serve"],
        ["Salaries and allowances", -(p.salary - r.salary),
         "Headcount and pay levels"],
        ["Overtime and premiums", -((p.overtime + p.premium)
                                    - (r.overtime + r.premium)),
         "Hours beyond the normal month"],
        ["Bonus", -(p.bonus - r.bonus), "The yearly bonus month"],
        ["Contributions", -(p.contributions - r.contributions),
         "Paid by the business on top of pay"],
        ["Recruiting and severance", -((p.recruit + p.severance + p.learning)
                                       - (r.recruit + r.severance + r.learning)),
         "One-off costs of people joining and leaving"],
        ["Other costs", -(p.other - r.other),
         "Everything that is not people"],
    ].map(([label, value, note]) => ({ label, value, note }));
    const total = steps.reduce((sum, x) => sum + x.value, 0);
    const difference = p.profit - r.profit;
    // A RELATIVE tolerance, because the absolute one is a lie at this size: a
    // double carrying ₫6.5 billion has about 1e-6 of resolution left, so
    // "sums exactly" has to mean "to the last bit the arithmetic has", not to
    // a fixed number of decimal places.
    return {
        start: r.profit, end: p.profit, steps, total,
        check: Math.abs(total - difference)
            <= Math.max(1e-6, Math.abs(difference) * 1e-9),
    };
}

/** Which levers differ from the comparison, the ones that matter first. */
export function changes(state, refState, baseline) {
    const list = [];
    const weight = {
        moves: 6, raise: 5, target: 5, growth: 5, ot: 4, productivity: 4,
        absence: 3, bonusMonths: 3, attritionOn: 3, backfill: 2, stress: 3,
        raiseMonth: 1, otFrom: 1, start: 1,
    };
    const teamName = Object.fromEntries(
        ((baseline && baseline.teams) || []).map((t) => [t.key, t.name]));

    const movesOf = (s) => {
        const out = {};
        for (const m of (s.moves || [])) {
            const key = `${m.team}|${m.role || ""}|${m.month}`;
            out[key] = (out[key] || 0) + m.n;
        }
        return out;
    };
    const a = movesOf(state);
    const b = movesOf(refState);
    for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
        const delta = (a[key] || 0) - (b[key] || 0);
        if (!delta) { continue; }
        const [team, role, month] = key.split("|");
        list.push({
            key: "moves", team, role, month: Number(month), delta,
            teamName: teamName[team] || team,
        });
    }
    for (const key of ["raise", "target", "growth", "ot", "productivity",
                       "absence", "bonusMonths", "stress", "raiseMonth",
                       "otFrom", "start"]) {
        const delta = num(state[key]) - num(refState[key]);
        if (Math.abs(delta) > 1e-9) {
            list.push({ key, delta, from: refState[key], to: state[key] });
        }
    }
    for (const key of ["attritionOn", "backfill"]) {
        if (!!state[key] !== !!refState[key]) {
            list.push({ key, delta: 1, from: refState[key], to: state[key] });
        }
    }
    return list.sort((x, y) => (weight[y.key] || 1) - (weight[x.key] || 1));
}

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
                     "July", "August", "September", "October", "November",
                     "December"];

/** One change, said the way a person would say it. */
export function describeChange(change, format) {
    const f = format;
    switch (change.key) {
        case "moves": {
            // Said as a DIFFERENCE and never as an act. When the comparison is
            // another plan, "letting go of 120 people" would be a sentence
            // about redundancies that nobody is proposing — the plan on screen
            // simply has 120 fewer people in it than the one it is measured
            // against. "Fewer" is true either way round.
            const n = Math.abs(Math.round(change.delta));
            const word = change.delta > 0 ? "more" : "fewer";
            const who = n === 1 ? "person" : "people";
            return `${n} ${word} ${who} in ${change.teamName} `
                + `from ${MONTH_NAMES[(change.month || 1) - 1]}`;
        }
        case "raise":
            return `a ${change.to > 0 ? "" : "cut of "}`
                + `${Math.abs(change.to).toFixed(1)}% `
                + (change.to > 0 ? "salary increase" : "in salaries");
        case "target":
            return `a revenue target of ${f.money(change.to)}`;
        case "growth":
            return `${Math.abs(change.to)}% ${change.to >= 0 ? "more" : "less"} `
                + "work by December";
        case "ot":
            return `${Math.round(change.to)} hours of overtime per person`;
        case "productivity":
            return `${Math.abs(change.to)}% ${change.to >= 0 ? "more" : "less"} `
                + "productive time";
        case "absence":
            return `${Math.round(change.to)}% unavailable time`;
        case "bonusMonths":
            return change.to === 0 ? "no yearly bonus"
                : `${change.to} months of bonus`;
        case "stress":
            return `demand ${change.to >= 0 ? "up" : "down"} `
                + `${Math.abs(change.to)}%`;
        case "raiseMonth":
            return `the increase starting in ${MONTH_NAMES[change.to - 1]}`;
        case "otFrom":
            return `overtime from ${MONTH_NAMES[change.to - 1]}`;
        case "start":
            return `hires arriving in ${MONTH_NAMES[change.to - 1]}`;
        case "attritionOn":
            return change.to ? "people leaving through the year"
                : "nobody leaving";
        case "backfill":
            return change.to ? "replacing everyone who leaves"
                : "not replacing leavers";
        default:
            return "";
    }
}

/** The caption: what you changed, what happened, and why. */
export function story(plan, ref, state, refState, refName, baseline, format) {
    const f = format;
    const list = changes(state, refState, baseline);
    if (!list.length) {
        return {
            title: `This is ${refName.toLowerCase()}. Nothing has changed yet.`,
            copy: "Move one lever on the left and watch people, the work you "
                + "can deliver and profit respond together.",
        };
    }
    const lead = list.slice(0, 2)
        .map((c) => describeChange(c, f)).filter(Boolean).join(" and ");
    const dProfit = plan.year.profit - ref.year.profit;
    const rest = list.length > 2
        ? ` with ${list.length - 2} smaller change`
          + `${list.length > 3 ? "s" : ""}`
        : "";
    const title = `${lead.charAt(0).toUpperCase()}${lead.slice(1)} `
        + `${dProfit >= 0 ? "adds" : "costs"} ${f.money(Math.abs(dProfit))} `
        + `of profit for the year${rest}.`;

    const why = [];
    const dCost = plan.year.people - ref.year.people;
    if (Math.abs(dCost) >= 1) {
        why.push(`Workforce cost is ${f.signedMoney(dCost)} for the year `
                 + `at ${f.money(plan.year.people)}.`);
    } else {
        why.push("Workforce cost is unchanged.");
    }
    if (state.target > 0) {
        const dCov = (plan.year.coverage - ref.year.coverage) * 100;
        why.push(Math.abs(dCov) >= 0.05
            ? `Demand served changes by ${f.pp(dCov)}, to `
              + `${f.pct(plan.year.coverage * 100)}.`
            : "The share of demand you serve is unchanged.");
        if (plan.year.unserved > 0) {
            why.push(`${f.money(plan.year.unserved)} of demand still goes `
                     + "unserved.");
        }
    } else {
        why.push("Type a revenue target and profit appears here too.");
    }
    const dHeads = plan.year.headcount - ref.year.headcount;
    if (Math.abs(dHeads) >= 1) {
        why.push(`${f.people(dHeads)} on payroll by December.`);
    }
    return { title, copy: why.join(" ") };
}

/** What could bite. Shown under the caption, worst first. */
export function warnings(plan, ref, state, format) {
    const f = format;
    const out = [];
    const year = plan.year;
    if (state.target > 0 && year.margin < 0.10) {
        out.push({
            level: "bad",
            text: `Margin falls to ${f.pct(year.margin * 100)}. Below 10% `
                + "there is no room for a slow quarter.",
        });
    } else if (state.target > 0 && year.margin < 0.15) {
        out.push({
            level: "watch",
            text: `Margin at ${f.pct(year.margin * 100)} is thin.`,
        });
    }
    const worst = plan.rows[year.worstMonth];
    if (worst && worst.profit < 0 && state.target > 0) {
        const bonusMonth = worst.bonus > 0;
        const hiring = worst.recruit + worst.severance > worst.base * 0.02;
        const why = bonusMonth && hiring
            ? "the bonus and the new arrivals land in the same month — move "
              + "the hires later and it recovers"
            : bonusMonth
                ? "the yearly bonus is paid this month; it is normal, but the "
                  + "cash has to be there"
                : hiring
                    ? "joining and leaving costs land together this month"
                    : "costs outrun revenue this month";
        out.push({
            level: "bad",
            text: `${MONTH_NAMES[worst.index]} loses money `
                + `(${f.money(worst.profit)}) — ${why}.`,
        });
    }
    if (year.hires > 150) {
        out.push({
            level: "watch",
            text: `${f.int(year.hires)} new people is a lot to recruit at `
                + `once — roughly ${Math.ceil(year.hires / 25)} recruiter-`
                + "months of work. Spreading them over two or three months "
                + "is kinder to everyone.",
        });
    }
    if (state.raise >= 12) {
        out.push({
            level: "watch",
            text: `A ${state.raise}% increase is well above a normal year. `
                + "Good for keeping people; check the yearly bill.",
        });
    }
    if (state.ot >= 40) {
        out.push({
            level: "watch",
            text: `${Math.round(state.ot)} hours of overtime a person brushes `
                + "the legal monthly cap for factory roles. Hiring may cost "
                + "less.",
        });
    }
    if (state.target > 0 && year.coverage < 0.95) {
        out.push({
            level: "watch",
            text: `${f.pct((1 - year.coverage) * 100)} of demand goes `
                + `unserved — ${f.money(year.unserved)} left on the table.`,
        });
    }
    if (state.target > 0 && year.capacity > year.demand * 1.15) {
        out.push({
            level: "watch",
            text: "The team could deliver more than the work coming in. "
                + "Fewer hires, or later ones, would keep the margin.",
        });
    }
    return out;
}

// --------------------------------------------- ready for Phase 2, unused now
/** What five more people in one team would do from here. */
export function marginal(baseline, assumptions, state, plan, teamKey, n = 5) {
    const team = ((baseline && baseline.teams) || [])
        .find((t) => t.key === teamKey);
    if (!team) { return null; }
    const next = compute(baseline, assumptions, {
        ...state,
        moves: [...(state.moves || []),
                { team: teamKey, role: null, n, month: state.start }],
    });
    return {
        team, n, plan: next,
        dProfit: next.year.profit - plan.year.profit,
        dCost: next.year.people - plan.year.people,
        dCoverage: (next.year.coverage - plan.year.coverage) * 100,
    };
}

/** How many more people one team can take before a goal breaks. */
export function headroom(baseline, assumptions, state, goals, teamKey,
                         format, max = 60) {
    const points = [];
    for (let add = 0; add <= max; add++) {
        const trial = compute(baseline, assumptions, {
            ...state,
            moves: add
                ? [...(state.moves || []),
                   { team: teamKey, role: null, n: add, month: state.start }]
                : (state.moves || []),
        });
        const rating = gradeGoals(trial, goals, format);
        points.push({ add, profit: trial.year.profit, met: rating.met,
                      failed: rating.failed });
    }
    const intervals = [];
    for (const point of points) {
        if (!point.met) { continue; }
        const last = intervals[intervals.length - 1];
        if (last && last[1] === point.add - 1) { last[1] = point.add; }
        else { intervals.push([point.add, point.add]); }
    }
    return { points, intervals };
}

/** Three ways to reach the same goals. Pure; Phase 2 gives it a screen. */
export function candidates(baseline, assumptions, state, goals, format) {
    const teams = ((baseline && baseline.teams) || []);
    const earner = teams.find((t) => t.revenue) || teams[0];
    if (!earner) { return { count: 0, lanes: [] }; }
    const lanes = { hire: null, develop: null, balanced: null };
    let count = 0;
    const rank = (a, b) => !b || a.failed < b.failed
        || (a.failed === b.failed && (a.score < b.score - 1e-9
            || (Math.abs(a.score - b.score) < 1e-9
                && a.plan.year.people < b.plan.year.people)));
    const heads = earner.heads;
    const steps = [0, 0.02, 0.05, 0.08, 0.12, 0.2].map(
        (p) => Math.round(heads * p));
    for (const add of [...new Set(steps)]) {
        for (const ot of [0, 8, 16, 24]) {
            for (const productivity of [0, 4, 8, 12]) {
                const trial = {
                    ...state, ot, productivity,
                    moves: add
                        ? [{ team: earner.key, role: null, n: add,
                             month: state.start }]
                        : [],
                };
                const plan = compute(baseline, assumptions, trial);
                const rating = gradeGoals(plan, goals, format);
                const item = { state: trial, plan, ...rating };
                count++;
                const buckets = ["balanced"];
                if (productivity === 0) { buckets.push("hire"); }
                if (add === 0) { buckets.push("develop"); }
                for (const lane of buckets) {
                    if (rank(item, lanes[lane])) { lanes[lane] = item; }
                }
            }
        }
    }
    return {
        count,
        lanes: ["hire", "develop", "balanced"]
            .map((lane) => ({ lane, ...(lanes[lane] || {}) })),
    };
}
