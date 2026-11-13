/* Inspired by the supplied 21st.dev particle-text-canvas example.
 * Native Odoo integration: local canvas coordinates, bounded work and a readable fallback. */
(() => {
    'use strict';
    const canvas = document.querySelector('.particle-text-canvas');
    if (!canvas) return;
    const host = canvas.parentElement;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    const fine = matchMedia('(hover: hover) and (pointer: fine)');
    const mouse = { x: null, y: null };
    let particles = [], width = 0, height = 0, visible = true;
    let frame = 0, last = 0, count = 0, ready = false;
    const enabled = () => ready && !reduced.matches && !navigator.connection?.saveData;

    function init() {
        const box = host.getBoundingClientRect();
        width = Math.round(box.width); height = Math.round(box.height);
        if (!width || !height) return;
        const scale = Math.min(devicePixelRatio || 1, 2);
        canvas.width = Math.round(width * scale); canvas.height = Math.round(height * scale);
        ctx.setTransform(scale, 0, 0, scale, 0, 0);
        // Sample at CSS resolution, independent of retina screen size.
        const sample = document.createElement('canvas');
        sample.width = width; sample.height = height;
        const ink = sample.getContext('2d', { willReadFrequently: true });
        if (!ink) return;
        let size = width * 0.23;
        ink.font = `600 ${size}px Manrope, Arial, sans-serif`;
        size *= width * 0.9 / ink.measureText('Biztinct').width;
        ink.font = `600 ${size}px Manrope, Arial, sans-serif`;
        ink.textAlign = 'center'; ink.textBaseline = 'middle';
        ink.fillStyle = 'white'; ink.fillText('Biztinct', width / 2, height / 2);
        const pixels = ink.getImageData(0, 0, width, height).data;
        particles = [];
        const gap = width < 400 ? 3 : 4;
        for (let y = 0; y < height; y += gap) {
            for (let x = 0; x < width; x += gap) {
                if (pixels[(y * width + x) * 4 + 3] > 128) {
                    particles.push({ x, y, bx: x, by: y, density: 8 + Math.random() * 18,
                        phase: Math.random() * Math.PI * 2,
                        color: `hsl(${260 - x / width * 75}, 85%, ${78 + x / width * 7}%)` });
                }
            }
        }
        canvas.dataset.particles = String(particles.length);
        mouse.x = mouse.y = null;
        sync();
    }

    function draw(time) {
        ctx.clearRect(0, 0, width, height);
        const radius = Math.min(100, width * 0.22);
        for (const p of particles) {
            let tx = p.bx, ty = p.by + Math.sin(time * 0.0007 + p.phase) * 0.7;
            if (mouse.x !== null && mouse.y !== null) {
                const dx = p.bx - mouse.x, dy = p.by - mouse.y;
                const distance = Math.hypot(dx, dy);
                // A coincident pointer must never create NaN particle coordinates.
                if (distance > 0.01 && distance < radius) {
                    const force = (1 - distance / radius) * p.density * 2.4;
                    tx += dx / distance * force; ty += dy / distance * force;
                }
            }
            p.x += (tx - p.x) * 0.12; p.y += (ty - p.y) * 0.12;
            ctx.fillStyle = p.color;
            ctx.beginPath(); ctx.arc(p.x, p.y, 1.25, 0, Math.PI * 2); ctx.fill();
        }
    }

    function tick(time) {
        frame = 0;
        if (!enabled() || !visible || document.hidden) { sync(); return; }
        if (time - last >= 32) {
            draw(time); last = time;
            canvas.dataset.frame = String(++count);
        }
        frame = requestAnimationFrame(tick);
    }
    function sync() {
        const active = enabled();
        host.classList.toggle('particles-ready', active);
        canvas.dataset.motion = active && visible && !document.hidden ? 'running' : 'paused';
        if (active && visible && !document.hidden) {
            if (!frame) frame = requestAnimationFrame(tick);
        } else if (frame) { cancelAnimationFrame(frame); frame = 0; }
    }
    host.addEventListener('pointermove', event => {
        if (!fine.matches || !enabled()) return;
        const box = host.getBoundingClientRect();
        mouse.x = event.clientX - box.left; mouse.y = event.clientY - box.top;
        canvas.dataset.interaction = 'repel';
    }, { passive: true });
    host.addEventListener('pointerleave', () => {
        mouse.x = mouse.y = null; canvas.dataset.interaction = 'return';
    });
    if (typeof ResizeObserver === 'function') new ResizeObserver(init).observe(host);
    else window.addEventListener('resize', init, { passive: true });
    if (typeof IntersectionObserver === 'function') {
        new IntersectionObserver(entries => {
            visible = entries[0].isIntersecting; sync();
        }, { threshold: 0.01 }).observe(host);
    }
    reduced.addEventListener('change', sync);
    navigator.connection?.addEventListener('change', sync);
    document.addEventListener('visibilitychange', sync);
    window.addEventListener('pagehide', () => {
        if (frame) cancelAnimationFrame(frame);
        frame = 0; canvas.dataset.motion = 'paused';
    });
    window.addEventListener('pageshow', sync);
    const fonts = document.fonts ? document.fonts.ready : Promise.resolve();
    fonts.then(() => { ready = true; init(); });
})();
