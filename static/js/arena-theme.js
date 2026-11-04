/*
 * "Caminho do Samurai": trilha original gerada com Web Audio API, em loop.
 * Taiko (tambores japoneses) + koto (cordas dedilhadas) + shakuhachi (flauta de bambu),
 * na escala japonesa miyako-bushi em ré (D, Eb, G, A, Bb).
 * Se a página informar um arquivo de áudio, ele é usado no lugar.
 *
 * Uso: ArenaTheme.attach(buttonEl, { audioSrc: '/static/audio/arena.mp3' | null, label: {...} })
 */
(function () {
    const BPM = 84;
    const STEP = 60 / BPM / 4;      // semicolcheia
    const BAR = 16;

    // Escala miyako-bushi em ré
    const N = { D3: 146.83, Eb3: 155.56, G3: 196.0, A3: 220.0, Bb3: 233.08,
                D4: 293.66, Eb4: 311.13, G4: 392.0, A4: 440.0, Bb4: 466.16, D5: 587.33 };

    // Taiko: 3 = odaiko (grave), 2 = golpe forte, 1 = golpe leve ("don don doko don")
    const TAIKO = [3, 0, 0, 0, 2, 0, 0, 0, 3, 0, 1, 1, 2, 0, 0, 0];
    const TAIKO_FILL = [3, 0, 1, 1, 2, 0, 1, 1, 3, 1, 1, 1, 2, 1, 2, 2];

    // Koto: arpejos por compasso (colcheias), alternando duas cores harmônicas
    const KOTO = [
        ['D3', 'A3', 'D4', 'Eb4', 'D4', 'A3', 'G3', 'A3'],
        ['D3', 'A3', 'Bb3', 'D4', 'Eb4', 'D4', 'Bb3', 'A3'],
        ['G3', 'D4', 'G4', 'A4', 'G4', 'D4', 'Bb3', 'D4'],
        ['A3', 'Eb4', 'A4', 'Bb4', 'A4', 'Eb4', 'D4', 'A3'],
    ];

    // Shakuhachi: frases longas (nota, duração em semicolcheias), entram a cada 4 compassos
    const FLUTE = [
        [['A4', 12], ['Bb4', 4], ['A4', 8], ['G4', 8], ['D4', 32]],
        [['D5', 12], ['Bb4', 4], ['A4', 16], ['G4', 8], ['A4', 24]],
    ];

    let ctx = null, master = null, reverb = null, timer = null, nextTime = 0, step = 0;
    let audioEl = null, playing = false, noiseBuf = null;

    function setupCtx() {
        ctx = new (window.AudioContext || window.webkitAudioContext)();
        const comp = ctx.createDynamicsCompressor();
        comp.threshold.value = -16; comp.ratio.value = 4;
        master = ctx.createGain();
        master.gain.value = 0;
        master.connect(comp).connect(ctx.destination);

        noiseBuf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
        const d = noiseBuf.getChannelData(0);
        for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;

        // Reverb simples (resposta ao impulso sintética) para dar sensação de salão
        const len = ctx.sampleRate * 2.2;
        const ir = ctx.createBuffer(2, len, ctx.sampleRate);
        for (let c = 0; c < 2; c++) {
            const ch = ir.getChannelData(c);
            for (let i = 0; i < len; i++) ch[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3);
        }
        reverb = ctx.createConvolver();
        reverb.buffer = ir;
        const wet = ctx.createGain(); wet.gain.value = 0.28;
        reverb.connect(wet).connect(master);
    }

    function out(node, dry = 1, wetSend = 0.5) {
        const g = ctx.createGain(); g.gain.value = dry; node.connect(g).connect(master);
        const s = ctx.createGain(); s.gain.value = wetSend; node.connect(s).connect(reverb);
    }

    function taiko(t, kind) {
        const big = kind === 3;
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.type = 'sine';
        o.frequency.setValueAtTime(big ? 110 : kind === 2 ? 150 : 190, t);
        o.frequency.exponentialRampToValueAtTime(big ? 38 : kind === 2 ? 62 : 90, t + (big ? 0.35 : 0.15));
        g.gain.setValueAtTime(big ? 1.0 : kind === 2 ? 0.6 : 0.3, t);
        g.gain.exponentialRampToValueAtTime(0.001, t + (big ? 1.4 : kind === 2 ? 0.6 : 0.25));
        o.connect(g); out(g, 1, big ? 0.6 : 0.3);
        o.start(t); o.stop(t + 1.5);
        // batida da baqueta na pele
        const n = ctx.createBufferSource(), f = ctx.createBiquadFilter(), ng = ctx.createGain();
        n.buffer = noiseBuf; f.type = 'bandpass'; f.frequency.value = big ? 500 : 1200; f.Q.value = 0.8;
        ng.gain.setValueAtTime(big ? 0.5 : 0.25, t);
        ng.gain.exponentialRampToValueAtTime(0.001, t + 0.08);
        n.connect(f).connect(ng); out(ng, 1, 0.2);
        n.start(t); n.stop(t + 0.1);
    }

    function koto(t, freq, vel) {
        // corda dedilhada: ataque seco, leve "puxada" de afinação e decaimento longo
        const o = ctx.createOscillator(), o2 = ctx.createOscillator();
        const f = ctx.createBiquadFilter(), g = ctx.createGain();
        o.type = 'triangle'; o2.type = 'sawtooth';
        o.frequency.setValueAtTime(freq * 1.012, t); o.frequency.exponentialRampToValueAtTime(freq, t + 0.06);
        o2.frequency.setValueAtTime(freq * 2.004, t);
        f.type = 'lowpass';
        f.frequency.setValueAtTime(4200, t); f.frequency.exponentialRampToValueAtTime(700, t + 0.5);
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(0.16 * vel, t + 0.005);
        g.gain.exponentialRampToValueAtTime(0.001, t + 1.6);
        const g2 = ctx.createGain(); g2.gain.value = 0.25;
        o.connect(f); o2.connect(g2).connect(f); f.connect(g); out(g, 1, 0.45);
        o.start(t); o2.start(t); o.stop(t + 1.7); o2.stop(t + 1.7);
    }

    function shakuhachi(t, freq, dur) {
        // flauta de bambu: entra deslizando de baixo, vibrato que cresce e sopro audível
        const o = ctx.createOscillator(), g = ctx.createGain(), f = ctx.createBiquadFilter();
        const lfo = ctx.createOscillator(), lfoG = ctx.createGain();
        o.type = 'sine';
        o.frequency.setValueAtTime(freq * 0.94, t);
        o.frequency.exponentialRampToValueAtTime(freq, t + 0.18);
        lfo.frequency.value = 5.2;
        lfoG.gain.setValueAtTime(0, t); lfoG.gain.linearRampToValueAtTime(freq * 0.012, t + dur * 0.7);
        lfo.connect(lfoG).connect(o.frequency);
        f.type = 'lowpass'; f.frequency.value = 2400;
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(0.13, t + 0.12);
        g.gain.setValueAtTime(0.13, t + dur * 0.75);
        g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        o.connect(f).connect(g); out(g, 0.9, 0.8);
        o.start(t); lfo.start(t); o.stop(t + dur + 0.05); lfo.stop(t + dur + 0.05);
        // sopro
        const n = ctx.createBufferSource(), nf = ctx.createBiquadFilter(), ng = ctx.createGain();
        n.buffer = noiseBuf; n.loop = true; nf.type = 'bandpass'; nf.frequency.value = freq * 2; nf.Q.value = 3;
        ng.gain.setValueAtTime(0.0001, t);
        ng.gain.exponentialRampToValueAtTime(0.05, t + 0.06);
        ng.gain.exponentialRampToValueAtTime(0.008, t + 0.4);
        ng.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        n.connect(nf).connect(ng); out(ng, 1, 0.6);
        n.start(t); n.stop(t + dur + 0.05);
    }

    function schedule() {
        while (nextTime < ctx.currentTime + 0.15) {
            const bar = Math.floor(step / BAR);
            const s = step % BAR;
            const cycle = bar % 16;                    // forma: 16 compassos
            const intense = cycle >= 8;                // segunda metade mais forte
            const fill = bar % 4 === 3;

            const hit = (fill && intense ? TAIKO_FILL : TAIKO)[s];
            if (hit) taiko(nextTime, hit);

            if (s % 2 === 0 && cycle >= 2) {
                const pattern = KOTO[Math.floor(bar / 2) % KOTO.length];
                const note = pattern[(s / 2) % pattern.length];
                koto(nextTime, N[note], s % 8 === 0 ? 1 : 0.7);
            }

            if (s === 0 && bar % 4 === 0 && cycle >= 4) {
                let t = nextTime;
                FLUTE[Math.floor(bar / 4) % FLUTE.length].forEach(([note, len]) => {
                    shakuhachi(t, N[note], len * STEP);
                    t += len * STEP;
                });
            }

            nextTime += STEP;
            step++;
        }
    }

    function startSynth() {
        if (!ctx) setupCtx();
        clearInterval(timer);
        ctx.resume();
        master.gain.cancelScheduledValues(ctx.currentTime);
        master.gain.setTargetAtTime(0.6, ctx.currentTime, 0.4);
        nextTime = ctx.currentTime + 0.05;
        timer = setInterval(schedule, 25);
    }

    function stopSynth() {
        clearInterval(timer); timer = null;
        if (ctx) master.gain.setTargetAtTime(0, ctx.currentTime, 0.2);
    }

    async function start(audioSrc) {
        if (audioSrc) {
            if (!audioEl) { audioEl = new Audio(audioSrc); audioEl.loop = true; audioEl.volume = 0.8; }
            await audioEl.play();
        } else {
            startSynth();
            await new Promise(r => setTimeout(r, 60));
            if (ctx.state !== 'running') { stopSynth(); throw new Error('autoplay bloqueado'); }
        }
        playing = true;
    }

    function stop() {
        if (audioEl) audioEl.pause();
        stopSynth();
        playing = false;
    }

    function attach(button, opts) {
        opts = opts || {};
        const audioSrc = opts.audioSrc || null;
        const labels = Object.assign({ on: 'Trilha tocando', off: 'Tocar trilha' }, opts.label || {});
        const KEY = 'arena-music-on';
        const label = button.querySelector('[data-label]') || button;

        const render = () => {
            button.classList.toggle('is-playing', playing);
            label.textContent = playing ? labels.on : labels.off;
            button.setAttribute('aria-pressed', String(playing));
        };

        const tryStart = async () => {
            try { await start(audioSrc); } catch (e) { playing = false; }
            render();
        };

        button.addEventListener('click', async () => {
            if (playing) { stop(); try { localStorage.setItem(KEY, '0'); } catch (e) {} render(); }
            else { await tryStart(); try { localStorage.setItem(KEY, playing ? '1' : '0'); } catch (e) {} }
        });

        // Se já estava ligada, tenta voltar a tocar; o navegador pode exigir um clique antes
        let wanted = false;
        try { wanted = localStorage.getItem(KEY) === '1'; } catch (e) {}
        if (wanted) {
            tryStart();
            const resume = (ev) => {
                if (button.contains(ev.target)) return; // o próprio botão já trata o clique
                if (!playing) tryStart();
                document.removeEventListener('pointerdown', resume);
            };
            document.addEventListener('pointerdown', resume);
        }
        render();
    }

    window.ArenaTheme = { attach };
})();
