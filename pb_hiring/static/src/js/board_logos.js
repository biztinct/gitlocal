/** @odoo-module **/
// Bundled provider assets; never send viewer traffic to external logo services.
const BOARD_LOGOS = {
    "linkedin": "/pb_hiring/static/src/img/job_boards/linkedin.webp",
    "jobstreet": "/pb_hiring/static/src/img/job_boards/jobstreet.webp",
    "naukri": "/pb_hiring/static/src/img/job_boards/naukri.webp",
    "foundit": "/pb_hiring/static/src/img/job_boards/foundit.webp",
    "foundit_id": "/pb_hiring/static/src/img/job_boards/foundit_id.webp",
    "apna": "/pb_hiring/static/src/img/job_boards/apna.webp",
    "shine": "/pb_hiring/static/src/img/job_boards/shine.svg",
    "hirist": "/pb_hiring/static/src/img/job_boards/hirist.webp",
    "iimjobs": "/pb_hiring/static/src/img/job_boards/iimjobs.webp",
    "instahyre": "/pb_hiring/static/src/img/job_boards/instahyre.webp",
    "timesjobs": "/pb_hiring/static/src/img/job_boards/timesjobs.webp",
    "internshala": "/pb_hiring/static/src/img/job_boards/internshala.webp",
    "vietnamworks": "/pb_hiring/static/src/img/job_boards/vietnamworks.webp",
    "topcv": "/pb_hiring/static/src/img/job_boards/topcv.webp",
    "itviec": "/pb_hiring/static/src/img/job_boards/itviec.webp",
    "careerviet": "/pb_hiring/static/src/img/job_boards/careerviet.webp",
    "vieclam24h": "/pb_hiring/static/src/img/job_boards/vieclam24h.webp",
    "topdev": "/pb_hiring/static/src/img/job_boards/topdev.webp",
    "glints": "/pb_hiring/static/src/img/job_boards/glints.webp",
    "kalibrr": "/pb_hiring/static/src/img/job_boards/kalibrr.webp",
    "dealls": "/pb_hiring/static/src/img/job_boards/dealls.webp",
    "kitalulus": "/pb_hiring/static/src/img/job_boards/kitalulus.webp",
    "karir": "/pb_hiring/static/src/img/job_boards/karir.webp",
    "indeed": "/pb_hiring/static/src/img/job_boards/indeed.webp",
    "careerjet": "/pb_hiring/static/src/img/job_boards/careerjet.webp",
    "jooble": "/pb_hiring/static/src/img/job_boards/jooble.webp",
    "google_jobs": "/pb_hiring/static/src/img/job_boards/google_jobs.webp",
    "logicmelon": "/pb_hiring/static/src/img/job_boards/logicmelon.webp",
    "broadbean": "/pb_hiring/static/src/img/job_boards/broadbean.webp"
};

export function boardLogo(key) {
    return BOARD_LOGOS[key === "seek" ? "jobstreet" : key] || "";
}
