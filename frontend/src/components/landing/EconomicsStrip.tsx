const metrics = [
  ["14 Days → 45s", "End-to-End Vendor Audit Turnaround"],
  ["$5,000+ → $0.08", "Unit Economics per Client Engagement"],
  ["100% Verbatim", "Zero-Hallucination Substring Citation Gate"],
  ["≤ 18 Credits", "Hard-Capped Live Web Intelligence (Olostep)"],
];

export default function EconomicsStrip() {
  return <section className="institutional-economics" aria-label="Institutional economics targets">
    <div className="wrap"><div className="economics-grid">{metrics.map(([value, label]) => <div key={value}><strong>{value}</strong><p>{label}</p></div>)}</div>
    <p className="micro economics-disclaimer">DESIGN TARGETS, NOT MEASURED OUTCOMES • PARTNER REVIEW TIME EXCLUDED. ≤18 credits is the operating target; 25 is the enforced engagement cap. Exact substring validation protects quotations, not every model conclusion.</p></div>
  </section>;
}
