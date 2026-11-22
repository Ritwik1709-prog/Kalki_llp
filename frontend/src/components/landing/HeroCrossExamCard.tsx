import { useEffect, useState } from "react";
import { RotateCcw } from "lucide-react";

const trace = [
  { at: 310, time: "00.31s", kind: "MAP", text: "POST /v1/maps → 42 URLs discovered, 4 compliance targets ranked (1 cr)" },
  { at: 1180, time: "01.18s", kind: "SCRAPE", text: "olostep://acme-cloud.io/privacy → SHA-256 cache HIT (0 cr)" },
  { at: 1940, time: "01.94s", kind: "VERIFY", text: "Cross-examining Claim SOC2-CC6.1 inside <UNTRUSTED_WEB_EVIDENCE>" },
  { at: 2420, time: "02.42s", kind: "HALT", text: "CRITICAL CONTRADICTION • PAUSED AT PARTNER GATE" },
];

export default function HeroCrossExamCard() {
  const [run, setRun] = useState(0);
  const [visible, setVisible] = useState(0);
  useEffect(() => {
    // Timings are deterministic; CSS removes visual motion when requested.
    const timers = trace.map((step, index) => window.setTimeout(() => setVisible(index + 1), step.at));
    return () => timers.forEach(window.clearTimeout);
  }, [run]);
  return <article className="hero-evidence trace-card institutional-terminal" aria-label="Live cross-examination demonstration">
    <div className="terminal-chrome"><span>ENGAGEMENT #KLK-2026-084 • DPDP / SOC 2</span><button className="text-link" onClick={() => { setVisible(0); setRun(value => value + 1); }}><RotateCcw size={13}/> Replay</button><span className="credit-badge telemetry">14 / 5,000 OLOSTEP CR</span></div>
    <div className="terminal-scroll">
      <div className="trace-toolbar"><span className="micro">LIVE CROSS-EXAMINATION</span><span className="sample">SIMULATED REPLAY</span></div>
      <ol className="execution-trace" aria-label="Sample execution trace">{trace.map((step, index) => <li key={step.kind} className={index < visible ? "trace-step visible" : "trace-step"} aria-hidden={index >= visible}><time>{step.time}</time><strong>{step.kind}</strong><span className={step.kind === "HALT" ? "halt-badge" : ""}>{step.text}</span></li>)}</ol>
      <div className="terminal-comparison"><section><h2>Vendor Questionnaire Claim</h2><blockquote>“Customer inputs are never shared with third-party model providers or external subprocessors.”</blockquote></section><section><h2>Live Web Evidence <span>(/privacy §4.2)</span></h2><blockquote><mark>“We may transmit anonymized prompts and metadata to third-party analytics and foundation-model subprocessors...”</mark></blockquote></section></div>
    </div>
    <div className="trace-footer telemetry"><span>CONFIDENCE 98.4%</span><span>SHA-256 9f3c...8a12</span><span className="partner-pause" role="status">{visible === 4 ? "STATUS: AWAITING PARTNER SIGN-OFF" : "STATUS: CROSS-EXAMINING"}</span></div>
    <p className="demo-note">Illustrative quotations, confidence, hash and account credits; not retrieved evidence. No paid calls. Real engagements have a 25-credit hard cap.</p>
  </article>;
}
