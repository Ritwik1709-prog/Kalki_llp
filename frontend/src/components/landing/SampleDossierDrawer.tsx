import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { showcaseCases } from "../../data/showcaseCases";

export default function SampleDossierDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (!open) return;
    const element = dialog.current!;
    const trigger = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    element.showModal();
    document.body.style.overflow = "hidden";
    return () => { element.close(); document.body.style.overflow = overflow; trigger?.focus(); };
  }, [open]);
  const residency = showcaseCases[1];
  return <dialog ref={dialog} className="sample-drawer" aria-labelledby="dossier-title" aria-describedby="dossier-disclaimer" onKeyDown={event => {
    if (event.key !== "Tab") return;
    const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button,a[href],input,textarea,select,[tabindex="0"]'));
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }} onCancel={event => { event.preventDefault(); onClose(); }} onClick={event => {
    const bounds = event.currentTarget.getBoundingClientRect();
    if (event.target === event.currentTarget && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) onClose();
  }}>
    <div className="modal-top"><span className="micro">KALKI LLP • CONFIDENTIAL COMPLIANCE DOSSIER</span><button autoFocus className="subtle-button" aria-label="Close sample dossier" onClick={onClose}><X size={20}/></button></div>
    <p id="dossier-disclaimer" className="micro">SYNTHETIC SAMPLE / UNSIGNED / NOT AN ISSUED AUDIT</p>
    <h2 id="dossier-title">Executive audit dossier.</h2>
    <p>Example Vendor • Review version DEMO-002/v1</p>
    <div className="dossier-risk"><span>RISK SCORE</span><strong>84/100 <span className="risk">CRITICAL</span></strong><span className="partner-pause">PENDING PARTNER REVIEW</span></div>
    <h3>Executive decision</h3><p>The sample residency claim conflicts directly with the sample transfer policy [C1, E1]. Proposed decision: hold onboarding pending transfer safeguards and authenticated Managing Partner review. The illustrative score is not a measured assessment.</p>
    <h3>Control matrix</h3><div className="matrix-scroll"><table><thead><tr><th>Framework / control</th><th>Evidence</th><th>Disposition</th></tr></thead><tbody>
      <tr><td>DPDP / transfer disclosures</td><td>E1; consent evidence missing</td><td>UNRESOLVED</td></tr>
      <tr><td>GDPR / Art. 44</td><td>C1 ↔ E1</td><td className="risk">CRITICAL</td></tr>
      <tr><td>SOC 2 / CC6.1</td><td>Independent assurance missing</td><td>UNRESOLVED</td></tr>
    </tbody></table></div>
    <h3>Verbatim sample citations</h3><p>These exact excerpts come from the bundled synthetic case record, not retrieved web pages. No certification is inferred.</p>
    {[["C1", "Vendor claim", residency.claim, "https://example-vendor.test/questionnaire", "claim"], ["E1", "Conflicting policy", residency.quote, "https://example-vendor.test/privacy", "quote"]].map(([id, title, quote, source, field]) => <section className="dossier-citation" key={id}><span className="micro">{id} / {title}</span><blockquote>{quote}</blockquote><dl><dt>Sample source URL</dt><dd><code>{source}</code></dd><dt>Retrieval timestamp</dt><dd>Not retrieved — bundled synthetic fixture</dd><dt>Fixture reference</dt><dd><code>showcaseCases / DEMO-002/v1 / {field}</code></dd></dl></section>)}
    <h3>Proposed clause redline</h3><div className="redline"><p><del>Transfers permitted at the processor’s discretion.</del></p><p className="addition"><ins>{residency.redline}</ins></p></div>
    <h3>Managing Partner • SHA-256 sign-off</h3><div className="signoff-block"><dl><dt>Reviewed version</dt><dd>DEMO-002/v1 • pending</dd><dt>Evidence SHA-256</dt><dd>Not sealed — sample only</dd><dt>Authenticated reviewer</dt><dd>Awaiting human review</dd><dt>Decision / rationale / timestamp</dt><dd>Not recorded</dd><dt>Signature / release</dt><dd className="partner-pause">UNSIGNED • RELEASE BLOCKED</dd></dl><p>Approval must bind the exact dossier and evidence version. Material changes invalidate approval.</p></div>
  </dialog>;
}
