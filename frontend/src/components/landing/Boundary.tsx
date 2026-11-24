import { useEffect, useRef, useState } from "react";
// Signature piece: a simulation of the evidence pipeline. Illustrative only, not live telemetry.
type Blk = { n: number; kind: string; hash: string; prev: string; tone: string };
type P = { a: number; r: number; k: "q" | "i" | "c"; st: number; t: number; v: number };
type F = { x: number; y: number; vx: number; vy: number; l: number };
const hex = (n: number) => { let h = Math.imul(n + 1, 2654435761) ^ 0x9f3c1a77; h = Math.imul(h ^ (h >>> 15), 2246822507); h ^= h >>> 13; return (h >>> 0).toString(16).padStart(8, "0"); };
const short = (s: string) => `${s.slice(0, 4)}…${s.slice(-4)}`;
export default function Boundary() {
  const ref = useRef<HTMLCanvasElement>(null);
  const [blocks, setBlocks] = useState<Blk[]>([{ n: 411, kind: "CHAIN OPENED", hash: hex(411), prev: hex(410), tone: "" }]);
  const [stats, setStats] = useState({ q: 0, i: 0, c: 0 });
  useEffect(() => {
    const cv = ref.current!, g = cv.getContext("2d")!;
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let n = 411, head = hex(411), S = 0, raf = 0, on = false, last = 0, acc = 0;
    const s = { q: 0, i: 0, c: 0 }, ps: P[] = [], fs: F[] = [], fl = [0, 0, 0, 0], tm = { q: 0, i: 2.5, c: 4 };
    const add = (kind: string, tone: string) => { const prev = head, num = ++n; head = hex(num * 31 + prev.charCodeAt(0)); const hh = head; setBlocks(b => [{ n: num, kind, hash: hh, prev, tone }, ...b].slice(0, 5)); setStats({ ...s }); };
    const size = () => { const d = Math.min(devicePixelRatio || 1, 2); S = cv.clientWidth; cv.width = S * d; cv.height = S * d; g.setTransform(d, 0, 0, d, 0, 0); if (still) frame(0, 0); };
    const frame = (now: number, dt: number) => {
      const cx = S / 2, R3 = S * 0.46, R2 = S * 0.31, R1 = S * 0.2, RC = S * 0.045;
      if (dt) {
        tm.q -= dt; tm.i -= dt; tm.c -= dt;
        if (tm.q <= 0) { tm.q = 0.5 + Math.random() * 0.4; ps.push({ a: Math.random() * 6.283, r: R3 * 1.05, k: "q", st: 0, t: 0, v: 0 }); }
        if (tm.i <= 0) { tm.i = 5.5; ps.push({ a: Math.random() * 6.283, r: R3 * 1.05, k: "i", st: 0, t: 0, v: 0 }); }
        if (tm.c <= 0 && !ps.some(p => p.k === "c")) { tm.c = 9.5; ps.push({ a: -1.2 + Math.random() * 0.8, r: R3 * 1.05, k: "c", st: 0, t: 0, v: 0 }); }
        for (let i = ps.length - 1; i >= 0; i--) {
          const p = ps[i];
          if (p.st === 0) {
            p.r -= S * (p.k === "i" ? 0.16 : 0.09) * dt;
            if (p.k === "i" && p.r <= R3) { for (let f = 0; f < 9; f++) { const a = p.a + (Math.random() - 0.5) * 1.4, v = 40 + Math.random() * 60; fs.push({ x: cx + Math.cos(p.a) * R3, y: cx + Math.sin(p.a) * R3, vx: Math.cos(a) * v, vy: Math.sin(a) * v, l: 1 }); } fl[0] = 1; s.i++; add("INJECTION QUARANTINED", "risk"); ps.splice(i, 1); continue; }
            if (p.k !== "i" && !p.v && p.r <= R2) { p.v = 1; fl[1] = 1; if (p.k === "q") s.q++; }
            if (p.k !== "i" && p.r <= R1) { if (p.k === "q") { fl[2] = 0.5; ps.splice(i, 1); continue; } p.st = 1; p.t = 0; p.r = R1; s.c++; fl[2] = 1; }
          } else if (p.st === 1) { p.t += dt; if (p.t > 3.4) p.st = 2; }
          else { p.r -= S * 0.14 * dt; if (p.r <= RC) { fl[3] = 1; add("PARTNER SIGN-OFF", "safe"); ps.splice(i, 1); continue; } }
        }
        fs.forEach(f => { f.x += f.vx * dt; f.y += f.vy * dt; f.l -= dt * 1.2; });
        for (let i = fs.length - 1; i >= 0; i--) if (fs[i].l <= 0) fs.splice(i, 1);
        fl.forEach((_, k) => { fl[k] = Math.max(0, fl[k] - dt * 1.6); });
        acc += dt; if (acc > 1) { acc = 0; setStats({ ...s }); }
      }
      g.clearRect(0, 0, S, S); g.lineWidth = 1; g.textAlign = "center"; g.font = "9px 'JetBrains Mono',monospace";
      for (let k = 0; k < 72; k++) { const a = k * 0.0873 + now * 3e-5; g.strokeStyle = "rgba(255,255,255,.1)"; g.beginPath(); g.moveTo(cx + Math.cos(a) * (R3 + 6), cx + Math.sin(a) * (R3 + 6)); g.lineTo(cx + Math.cos(a) * (R3 + 10), cx + Math.sin(a) * (R3 + 10)); g.stroke(); }
      g.setLineDash([3, 6]); g.strokeStyle = `rgba(${fl[0] ? "220,38,38" : "255,255,255"},${0.16 + fl[0] * 0.6})`; g.beginPath(); g.arc(cx, cx, R3, 0, 6.283); g.stroke(); g.setLineDash([]);
      g.strokeStyle = `rgba(${fl[1] ? "16,185,129" : "255,255,255"},${0.12 + fl[1] * 0.6})`; g.beginPath(); g.arc(cx, cx, R2, 0, 6.283); g.stroke();
      g.strokeStyle = `rgba(217,119,6,${0.4 + fl[2] * 0.5})`; g.lineWidth = 1.5; g.beginPath(); g.arc(cx, cx, R1, 0, 6.283); g.stroke(); g.lineWidth = 1;
      g.fillStyle = `rgba(245,245,247,${0.1 + fl[3] * 0.8})`; g.beginPath(); g.arc(cx, cx, RC, 0, 6.283); g.fill();
      g.fillStyle = "rgba(154,154,166,.85)";
      g.fillText("UNTRUSTED WEB EVIDENCE", cx, cx - R3 + 16); g.fillText("EXACT-SUBSTRING GATE", cx, cx - R2 + 16); g.fillText("PARTNER GATE", cx, cx - R1 + 16); g.fillText("SIGNED DOSSIER", cx, cx + RC + 16);
      ps.forEach(p => {
        const x = cx + Math.cos(p.a) * p.r, y = cx + Math.sin(p.a) * p.r, ox = Math.cos(p.a) * 12, oy = Math.sin(p.a) * 12;
        const col = p.k === "i" ? "220,38,38" : p.st ? "217,119,6" : p.v ? "16,185,129" : "190,190,200";
        g.strokeStyle = `rgba(${col},.35)`; g.beginPath(); g.moveTo(x, y); g.lineTo(x + ox, y + oy); g.stroke();
        g.fillStyle = `rgb(${col})`; g.beginPath(); g.arc(x, y, p.k === "c" ? 3.4 + (p.st === 1 ? Math.sin(now * 0.008) : 0) : 2.2, 0, 6.283); g.fill();
        if (p.st === 1) { g.strokeStyle = "rgba(217,119,6,.9)"; g.beginPath(); g.arc(x, y, 9, -1.571, -1.571 + 6.283 * (p.t / 3.4)); g.stroke(); }
      });
      fs.forEach(f => { g.fillStyle = `rgba(220,38,38,${f.l})`; g.fillRect(f.x, f.y, 2, 2); });
    };
    const loop = (now: number) => { const dt = Math.min((now - last) / 1000, 0.05); last = now; if (on && !document.hidden) frame(now, dt); raf = requestAnimationFrame(loop); };
    size(); addEventListener("resize", size);
    const io = new IntersectionObserver(([e]) => { on = e.isIntersecting; }); io.observe(cv);
    if (!still) raf = requestAnimationFrame(loop);
    return () => { cancelAnimationFrame(raf); io.disconnect(); removeEventListener("resize", size); };
  }, []);
  return <section className="boundary" id="boundary" aria-labelledby="boundary-title">
    <div className="boundary-copy">
      <span className="eyebrow">THE TRUST BOUNDARY</span>
      <h2 id="boundary-title">Hostile pages stop at the wall.<br />Contradictions stop at the Partner.</h2>
      <p>Web text is untrusted until an exact substring match clears it. Anything HIGH or CRITICAL waits for a human, and every release extends a hash-chained record.</p>
      <div className="boundary-stats telemetry" aria-hidden="true"><span><b>{stats.q}</b> quotes verified</span><span><b>{stats.i}</b> injections quarantined</span><span><b>{stats.c}</b> held for Partner</span></div>
      <ol className="ledger" aria-label="Illustrative audit chain">{blocks.map(b => <li key={b.n} className={b.tone}><span>#{b.n}</span><strong>{b.kind}</strong><code>{short(b.hash)}</code><i>prev {short(b.prev)}</i></li>)}</ol>
      <p className="micro">ILLUSTRATIVE SIMULATION, NOT LIVE TELEMETRY. THE HASH-CHAINED AUDIT TRAIL IS PLANNED.</p>
    </div>
    <figure className="chamber"><canvas ref={ref} role="img" aria-label="Animated diagram: untrusted web evidence passes an exact-substring gate, critical findings wait at the Partner gate, hostile instructions are quarantined." /></figure>
  </section>;
}
