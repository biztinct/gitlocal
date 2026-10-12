/* Native animation; no third-party runtime, tracking or remote asset requests. */
(() => {
    'use strict';
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
    const progress = document.querySelector('.scroll-progress');
    let scrollTick = false;
    const syncProgress = () => {
        const distance = document.documentElement.scrollHeight - innerHeight;
        if (progress) progress.style.transform = `scaleX(${distance > 0 ? scrollY / distance : 0})`;
        scrollTick = false;
    };
    syncProgress();
    window.addEventListener('scroll', () => {
        if (!scrollTick) { scrollTick = true; requestAnimationFrame(syncProgress); }
    }, { passive: true });
    window.addEventListener('resize', syncProgress, { passive: true });

    if (!reduced.matches && typeof IntersectionObserver === 'function') {
        document.body.classList.add('motion-ready');
        const revealObserver = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    revealObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.06, rootMargin: '0px 0px -25px 0px' });
        document.querySelectorAll('.intro-grid, .section-heading, .solution-card, .digital-banner, '
            + '.philosophy-art, .philosophy-copy, .process-grid article, .industry-tags, '
            + '.detail-copy, .detail-visual, .approach-step, .principles-grid article, '
            + '.contact-form-wrap, .contact-faq, .cta-inner').forEach(element => {
            element.classList.add('reveal');
            if (element.matches('.solution-card, .process-grid article, .principles-grid article')) {
                const index = [...element.parentElement.children].indexOf(element);
                element.style.setProperty('--reveal-delay', `${Math.min(index, 3) * 90}ms`);
            }
            revealObserver.observe(element);
        });
    }
    reduced.addEventListener('change', event => {
        if (event.matches) document.body.classList.remove('motion-ready');
    });

    const strip = document.querySelector('.capability-strip .shell');
    if (strip && !reduced.matches) {
        const source = strip.querySelector('div');
        if (source) {
            const track = document.createElement('div');
            track.className = 'marquee-track';
            source.className = 'marquee-run';
            const clone = source.cloneNode(true);
            clone.setAttribute('aria-hidden', 'true');
            source.replaceWith(track);
            track.append(source, clone);
        }
    }

    if (finePointer.matches && !reduced.matches) {
        document.querySelectorAll('.solution-card').forEach(card => {
            card.addEventListener('pointermove', event => {
                if (reduced.matches) return;
                const box = card.getBoundingClientRect();
                const x = (event.clientX - box.left) / box.width;
                const y = (event.clientY - box.top) / box.height;
                card.style.setProperty('--pointer-x', `${x * 100}%`);
                card.style.setProperty('--pointer-y', `${y * 100}%`);
                card.style.setProperty('--tilt-x', `${(0.5 - y) * 5}deg`);
                card.style.setProperty('--tilt-y', `${(x - 0.5) * 6}deg`);
            }, { passive: true });
            card.addEventListener('pointerleave', () => {
                card.style.setProperty('--tilt-x', '0deg');
                card.style.setProperty('--tilt-y', '0deg');
            });
        });
        const hero = document.querySelector('.hero-v2');
        const art = document.querySelector('.hero-art-parallax');
        if (hero && art) {
            let targetX = 0, targetY = 0, currentX = 0, currentY = 0, moving = false;
            const step = () => {
                if (reduced.matches) { moving = false; return; }
                currentX += (targetX - currentX) * 0.09;
                currentY += (targetY - currentY) * 0.09;
                art.style.setProperty('--art-x', `${currentX.toFixed(2)}px`);
                art.style.setProperty('--art-y', `${currentY.toFixed(2)}px`);
                art.style.setProperty('--art-r', `${(currentX / 14).toFixed(2)}deg`);
                if (Math.abs(targetX - currentX) + Math.abs(targetY - currentY) > 0.08) {
                    requestAnimationFrame(step);
                } else { moving = false; }
            };
            const move = (x, y) => {
                targetX = x; targetY = y;
                if (!moving) { moving = true; requestAnimationFrame(step); }
            };
            hero.addEventListener('pointermove', event => {
                const box = hero.getBoundingClientRect();
                move(((event.clientX - box.left) / box.width - 0.5) * 34,
                     ((event.clientY - box.top) / box.height - 0.5) * 26);
            }, { passive: true });
            hero.addEventListener('pointerleave', () => move(0, 0));
        }
    }

    // A subtle procedural aurora; renders at 30 fps and sleeps out of view.
    const canvas = document.querySelector('.hero-canvas');
    if (!canvas || reduced.matches || navigator.connection?.saveData) return;
    let gl;
    try { gl = canvas.getContext('webgl', { alpha: true, antialias: false, powerPreference: 'low-power' }); }
    catch { return; }
    if (!gl) return;
    const vertex = `attribute vec2 position;
        void main(){gl_Position=vec4(position,0.0,1.0);}`;
    const fragment = `precision highp float;
        uniform vec2 resolution; uniform float time;
        float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
        float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);
          return mix(mix(hash(i),hash(i+vec2(1.0,0.0)),f.x),
                     mix(hash(i+vec2(0.0,1.0)),hash(i+vec2(1.0,1.0)),f.x),f.y);}
        float fbm(vec2 p){float v=0.0,a=0.5;for(int i=0;i<4;i++){
          v+=a*noise(p);p=p*2.02+7.4;a*=0.5;}return v;}
        void main(){vec2 uv=gl_FragCoord.xy/resolution;
          vec2 p=(uv-vec2(0.72,0.5))*vec2(resolution.x/resolution.y,1.0);
          float t=time*0.07;
          float n=fbm(p*2.4+vec2(t,-t*0.7));
          float bend=sin(p.x*3.5+t*2.0)*0.16+cos(p.x*2.1-t)*0.12;
          float ribbon=exp(-abs(p.y+bend+(n-0.5)*0.5)*7.0);
          float waves=pow(0.5+0.5*sin(p.y*16.0+p.x*3.0+n*6.0-t*3.0),6.0);
          float falloff=exp(-dot(p,p)*1.5);
          vec3 purple=vec3(0.26,0.12,0.52);
          vec3 cyan=vec3(0.04,0.28,0.35);
          vec3 colour=mix(purple,cyan,0.5+0.5*sin(p.x*2.5+n*2.0+t));
          colour*=falloff*(0.35+ribbon*0.85+waves*0.14);
          gl_FragColor=vec4(colour,0.94);}`;
    const compile = (type, source) => {
        const shader = gl.createShader(type);
        gl.shaderSource(shader, source); gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
            gl.deleteShader(shader); return null;
        }
        return shader;
    };
    const vs = compile(gl.VERTEX_SHADER, vertex), fs = compile(gl.FRAGMENT_SHADER, fragment);
    if (!vs || !fs) return;
    const program = gl.createProgram();
    gl.attachShader(program, vs); gl.attachShader(program, fs); gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
    gl.useProgram(program);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, 'position');
    gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    const resolution = gl.getUniformLocation(program, 'resolution');
    const time = gl.getUniformLocation(program, 'time');
    const resize = () => {
        const box = canvas.getBoundingClientRect();
        const scale = Math.min(devicePixelRatio || 1, 1.25, 1600 / Math.max(box.width, 1));
        canvas.width = Math.max(1, Math.round(box.width * scale));
        canvas.height = Math.max(1, Math.round(box.height * scale));
        gl.viewport(0, 0, canvas.width, canvas.height);
        gl.uniform2f(resolution, canvas.width, canvas.height);
    };
    resize();
    window.addEventListener('resize', resize, { passive: true });
    let visible = true, running = false, lastFrame = 0, frames = 0;
    const tick = timestamp => {
        if (!visible || document.hidden || reduced.matches) {
            running = false; canvas.dataset.motion = 'paused'; return;
        }
        if (timestamp - lastFrame > 32) {
            gl.uniform1f(time, timestamp / 1000);
            gl.drawArrays(gl.TRIANGLES, 0, 6);
            lastFrame = timestamp; frames++;
            canvas.dataset.motion = 'running'; canvas.dataset.frame = String(frames);
        }
        requestAnimationFrame(tick);
    };
    const start = () => {
        if (!running && visible && !document.hidden && !reduced.matches) {
            running = true; requestAnimationFrame(tick);
        }
    };
    if (typeof IntersectionObserver === 'function') {
        new IntersectionObserver(entries => {
            visible = entries[0].isIntersecting;
            if (visible) start();
        }, { threshold: 0.02 }).observe(canvas);
    }
    document.addEventListener('visibilitychange', start);
    reduced.addEventListener('change', start);
    start();
})();
