import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import HeroCrossExamCard from "./HeroCrossExamCard";

export default function HeroSection({ onInspectDossier }: { onInspectDossier?: () => void }) {
  function inspect() {
    document.getElementById("cases")?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
    });
    onInspectDossier?.();
  }
  return <section className="hero editorial-hero wrap" aria-labelledby="hero-title">
    <div className="hero-copy">
      <span className="eyebrow framed-eyebrow">TRACK A2 • AUTONOMOUS COMPLIANCE PRACTICE</span>
      <h1 id="hero-title">Autonomous<br/>due diligence.<br/><em>Partner-grade<br/>judgment.</em></h1>
      <p>Kalki LLP replaces 14-day vendor audits by investigating live web policies and cross-examining every self-reported security claim with verbatim source quotes. Execution pauses at a Managing Partner gate before signed dossiers are issued.</p>
      <div className="hero-actions"><Link className="button" to="/desk">Launch Command Center <ArrowRight size={17}/></Link><button className="text-link" onClick={inspect}>Inspect Sample Dossier <ArrowRight size={16}/></button></div>
      <span className="micro hero-note">EVIDENCE FIRST. HUMAN AUTHORITY, ALWAYS.</span>
    </div>
    <HeroCrossExamCard/>
  </section>;
}
