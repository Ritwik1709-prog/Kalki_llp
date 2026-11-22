import { useEffect, useState } from "react";
import { FileText, Pause, RotateCcw } from "lucide-react";

const trace = [
  { at: 310, time: "00.31s", kind: "MAP", text: "POST /v1/maps → 42 URLs discovered, 4 compliance targets ranked (1 cr)" },
  { at: 1180, time: "01.18s", kind: "SCRAPE", text: "olostep://vendor.io/privacy → SHA-256 cache HIT (0 cr)" },
  { at: 1940, time: "01.94s", kind: "VERIFY", text: "Cross-examining SOC2-CC6.1 inside <UNTRUSTED_WEB_EVIDENCE>" },
  { at: 2420, time: "02.42s", kind: "HALT", text: "CRITICAL CONTRADICTION • PAUSED AT PARTNER GATE" },
];

export default function CrossExamination() {
  const [run, setRun] = useState(0);
  const [visible, setVisible] = useState(0);
  useEffect(() => {
    const timers = trace.map((step, index) => window.setTimeout(() => setVisible(index + 1), step.at));
    return () => timers.forEach(window.clearTimeout);
  }, [run]);
  return <div className="hero-evidence trace-card">
    <div className="evidence-heading"><FileText size={17}/><span>LIVE CROSS-EXAMINATION</span><span className="sample">DEMO</span><span className="telemetry">14 / 5,000 OLOSTEP CR</span></div>
    <div className="trace-toolbar"><span className="micro">CONTROL / SOC2-CC6.1</span><button className="text-link" onClick={() => { setVisible(0); setRun(value => value + 1); }}><RotateCcw size={13}/> Replay</button></div>
    <ol className="execution-trace" aria-label="Sample execution trace">{trace.map((step, index) => <li key={step.kind} className={index < visible ? "trace-step visible" : "trace-step"} aria-hidden={index >= visible}><time>{step.time}</time><strong>{step.kind}</strong><span className={step.kind === "HALT" ? "halt-badge" : ""}>{step.text}</span></li>)}</ol>
    <div className="gate" role="status"><Pause size={14}/><span>{visible === 4 ? "PAUSED: PARTNER GATE" : "REPLAYING SAMPLE TRACE"}</span></div>
    <div className="trace-footer telemetry">CONFIDENCE 98.4% • SHA-256 9f3c...8a12</div>
    <p className="demo-note">Simulated trace, confidence, hash and account telemetry. No paid calls. Each real engagement remains capped at 25 credits.</p>
  </div>;
}
