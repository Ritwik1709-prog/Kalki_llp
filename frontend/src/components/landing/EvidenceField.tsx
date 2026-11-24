import { useEffect, useRef } from "react";
// Hero backdrop: 42 discovered URLs that react to the cross-examination trace (MAP → SCRAPE → VERIFY → HALT).
const N = 42, TARGETS = [3, 11, 19, 30];
const rnd = (i: number) => { const s = Math.sin(i * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
export default function EvidenceField() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current!, g = c.getContext("2d")!;
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const nodes = Array.from({ length: N }, (_, i) => ({ x: rnd(i), y: rnd(i + 99), p: rnd(i + 7) * 6.28, r: 1 + rnd(i + 3) * 1.3 }));
    const links = nodes.map((a, i) => nodes.map((b, j) => ({ j, d: (a.x - b.x) ** 2 + (a.y - b.y) ** 2 })).filter(o => o.j !== i).sort((p, q) => p.d - q.d).slice(0, 2).map(o => o.j));
    let w = 0, h = 0, step = 0, raf = 0, on = true;
    const ts = [0, 0, 0, 0, 0];
    const size = () => { const d = Math.min(devicePixelRatio || 1, 2); w = c.clientWidth; h = c.clientHeight; c.width = w * d; c.height = h * d; g.setTransform(d, 0, 0, d, 0, 0); };
    const draw = (now: number) => {
      g.clearRect(0, 0, w, h);
      const frozen = step === 4, m = still || frozen ? 0 : 1;
      const pos = nodes.map(n => [n.x * w + Math.sin(now * 2e-4 + n.p) * 9 * m, n.y * h + Math.cos(now * 1.7e-4 + n.p) * 9 * m]);
      const cp = [w * 0.8, h * 0.52], a0 = step === 0 ? 0.16 : frozen ? 0.14 : 0.32;
      const lit = (i: number) => step >= 2 || (step === 1 && now - ts[1] > i * 22);
      g.lineWidth = 1;
      nodes.forEach((_, i) => links[i].forEach(j => {
        if (!(lit(i) && lit(j))) return;
        const t = TARGETS.includes(i) || TARGETS.includes(j);
        g.strokeStyle = `rgba(185,185,197,${t ? (frozen ? 0.12 : 0.24) : 0.06})`;
        g.beginPath(); g.moveTo(pos[i][0], pos[i][1]); g.lineTo(pos[j][0], pos[j][1]); g.stroke();
      }));
      nodes.forEach((n, i) => {
        g.fillStyle = `rgba(215,215,225,${lit(i) ? a0 : 0.1})`;
        g.beginPath(); g.arc(pos[i][0], pos[i][1], n.r, 0, 6.283); g.fill();
        if (TARGETS.includes(i) && lit(i)) { g.strokeStyle = `rgba(245,245,247,${frozen ? 0.2 : 0.5})`; g.beginPath(); g.arc(pos[i][0], pos[i][1], n.r + 4, 0, 6.283); g.stroke(); }
      });
      if (step >= 2 && step < 4) TARGETS.forEach((k, n) => {
        const q = (((now - ts[2]) / 1100 + n * 0.18) % 1);
        g.fillStyle = `rgba(245,245,247,${0.8 * (1 - q)})`;
        g.beginPath(); g.arc(pos[k][0] + (cp[0] - pos[k][0]) * q, pos[k][1] + (cp[1] - pos[k][1]) * q, 1.8, 0, 6.283); g.fill();
      });
      if (step >= 3) {
        const q = Math.min(1, (now - ts[3]) / 700), s = pos[TARGETS[0]];
        g.strokeStyle = step === 4 ? "rgba(217,119,6,.5)" : "rgba(245,245,247,.7)";
        g.beginPath(); g.moveTo(s[0], s[1]); g.lineTo(s[0] + (cp[0] - s[0]) * q, s[1] + (cp[1] - s[1]) * q); g.stroke();
      }
      if (step === 4) {
        g.fillStyle = "#D97706"; g.beginPath(); g.arc(cp[0], cp[1], 3.2, 0, 6.283); g.fill();
        for (let k = 0; k < 3; k++) { const q = ((now - ts[4]) / 1600 + k / 3) % 1; g.strokeStyle = `rgba(217,119,6,${0.5 * (1 - q)})`; g.beginPath(); g.arc(cp[0], cp[1], 4 + q * 70 * (still ? 0.4 : 1), 0, 6.283); g.stroke(); }
      }
    };
    const loop = (now: number) => { if (on && !document.hidden) draw(now); raf = requestAnimationFrame(loop); };
    const onTrace = (e: Event) => { step = (e as CustomEvent<number>).detail; ts[step] = performance.now(); if (still) draw(performance.now()); };
    size(); addEventListener("resize", size); addEventListener("kalki-trace", onTrace);
    const io = new IntersectionObserver(([e]) => { on = e.isIntersecting; }); io.observe(c);
    if (still) draw(0); else raf = requestAnimationFrame(loop);
    return () => { cancelAnimationFrame(raf); io.disconnect(); removeEventListener("resize", size); removeEventListener("kalki-trace", onTrace); };
  }, []);
  return <canvas ref={ref} className="evidence-field" aria-hidden="true" />;
}
