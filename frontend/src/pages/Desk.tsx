import { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { Wordmark } from "../components/landing/Navigation";
import { showcaseCases } from "../data/showcaseCases";
import { LayoutDashboard, FileText, ShieldCheck, ArrowLeft, RefreshCw, ArrowUpRight, Search, ChevronRight, X, Download } from "lucide-react";
import { api } from "../lib/api";


export default function Desk() {
  const [status, setStatus] = useState("Connecting to backend…");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    setStatus("Connecting to backend…");
    const controller = new AbortController();
    const wake = setTimeout(() => setStatus("Waking the backend… Render may take a minute to start."), 3000);
    const deadline = setTimeout(() => controller.abort(), 120000);
    let active = true;
    api<{status: string}>("/health", {signal: controller.signal})
      .then(data => { if(active) setStatus(data.status === "ok" ? "Backend Connected" : "API Offline \u2014 Ready for Backend"); })
      .catch(() => { if(active) setStatus("API Offline \u2014 Ready for Backend"); })
      .finally(() => { clearTimeout(wake); clearTimeout(deadline); });
    return () => { active = false; controller.abort(); clearTimeout(wake); clearTimeout(deadline); };
  }, [attempt]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState(1);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [tab, setTab] = useState("evidence");
  const [notice, setNotice] = useState("");
  const modal = useRef<HTMLDialogElement>(null);
  const current = showcaseCases[selected];
  const matches = showcaseCases.map((item,index)=>({item,index})).filter(({item}) => item.name.toLowerCase().includes(query.toLowerCase()) && (filter === "all" || item.tone === filter));
  function download(){
    const content = `KALKI LLP - SAMPLE DOSSIER\nSYNTHETIC DATA / UNSIGNED / NOT A COMPLIANCE DECISION\n\n${current.name}\n${current.status}\n\nClaim: ${current.claim}\nQuote: ${current.quote}\nSample source: ${current.source}\n\nProposed disposition: ${current.redline}\n\nSession notes: ${notes[selected] || "None"}`;
    const url = URL.createObjectURL(new Blob([content],{type:"text/plain"}));
    const link = document.createElement("a"); link.href=url;link.download="kalki-sample-dossier.txt";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    setNotice("Unsigned sample dossier downloaded.");
  }
  return <div className="desk-layout">
    <aside className="desk-sidebar"><Wordmark/><span className="workspace-label">PARTNER WORKSPACE</span><a href="#case-library" className="sidebar-active"><LayoutDashboard size={17}/> Case library <span>03</span></a><button onClick={()=>modal.current?.showModal()}><FileText size={17}/> Dossier preview</button><Link to="/#safeguards"><ShieldCheck size={17}/> Practice safeguards</Link><Link to="/"><ArrowLeft size={17}/> Firm website</Link><div className="sidebar-bottom"><span className="micro">ENVIRONMENT</span><strong>Demonstration</strong><p>Synthetic cases. No live audit or approval actions.</p></div></aside>
    <main className="desk-main"><div className="desk-toolbar"><span className="micro">KALKI LLP / COMMAND CENTER</span><button className="subtle-button" onClick={()=>setAttempt(attempt+1)}><RefreshCw size={14}/> Check backend</button></div><div role="status" className="connection-state">{status}</div>
    <header className="desk-heading"><div><span className="eyebrow">THE HUMAN AUTHORITY LAYER</span><h1>Partner Judgment Desk</h1><p>Inspect the evidence. Challenge the conclusion.</p></div><button className="button" onClick={()=>modal.current?.showModal()}>Preview dossier <ArrowUpRight size={16}/></button></header>
    <section className="engagement-launchers" aria-label="Preset engagement launchers">{[
      ["DPDP readiness", "Consent and data-transfer review", 1, "evidence"],
      ["GDPR residency", "Subprocessor and transfer review", 1, "evidence"],
      ["SOC 2 diligence", "Security claim review", 0, "evidence"],
      ["Contract redlines", "Proposed remediation clauses", 1, "redline"]
    ].map(([title,description,index,view])=><button key={title} className="launcher" onClick={()=>{setSelected(Number(index));setTab(String(view));setQuery("");setFilter("all");setNotice(`${title} sample opened. No live engagement started.`);document.getElementById("case-library")?.scrollIntoView();}}><span className="micro">OPEN SAMPLE ENGAGEMENT</span><strong>{title}</strong><span>{description}</span><ArrowUpRight size={16}/></button>)}</section>
    <div className="desk-metrics"><div><span>Sample engagements</span><strong>03</strong><small>Available for exploration</small></div><div><span>Partner review scenarios</span><strong className="risk">02</strong><small>Contradiction or source integrity</small></div><div><span>Live credits consumed</span><strong>00</strong><small>This demonstration makes no paid calls</small></div></div>
    <section id="case-library" className="desk-workbench"><div className="case-library"><label className="search-field"><Search size={16}/><input aria-label="Search sample cases" placeholder="Find a case..." value={query} onChange={e=>setQuery(e.target.value)}/></label><div className="filter-row">{[["all","All cases"],["risk","Needs review"],["safe","Verified"]].map(([value,label])=><button key={value} aria-pressed={filter===value} className={filter===value?"chosen":""} onClick={()=>setFilter(value)}>{label}</button>)}</div>{matches.map(({item,index})=><button key={item.name} className={`library-item ${selected===index?"selected":""}`} onClick={()=>{setSelected(index);setNotice("");}}><span className="micro">CASE 0{index+1} / {item.control}</span><strong>{item.name}</strong><span className={item.tone}>{item.status.split(" ")[0]}</span><ChevronRight size={16}/></button>)}{matches.length===0&&<div className="empty-state"><Search size={22}/><p>No matching sample cases.</p><button onClick={()=>{setQuery("");setFilter("all");}}>Reset filters</button></div>}</div>
    <article className="desk-inspector" key={selected}><div className="panel-top"><span>CASE 0{selected+1}</span><span className={current.tone}>{current.status}</span></div><h2>{current.name}</h2><div className="inspector-tabs">{["evidence","redline","notes"].map(t=><button key={t} aria-pressed={tab===t} className={tab===t?"chosen":""} onClick={()=>setTab(t)}>{t}</button>)}</div><div className="inspector-content" key={tab}>{tab==="evidence"?<><span className="micro">VENDOR CLAIM</span><blockquote>{current.claim}</blockquote><span className="micro">VERBATIM SAMPLE POLICY</span><blockquote className={`quote-box ${current.tone}`}>{current.quote}</blockquote><code>{current.source}</code></>:tab==="redline"?<><span className="micro">PROPOSED DISPOSITION / NOT LEGAL ADVICE</span><p className="quote-box">{current.redline}</p><p>Draft language requires human review before incorporation into a contract.</p></>:<><label htmlFor="partner-notes">Partner working notes</label><textarea id="partner-notes" value={notes[selected]||""} placeholder="Record a question or proposed follow-up..." onChange={e=>setNotes({...notes,[selected]:e.target.value})}/><p>Session-only notes. Included in your sample download; not saved to a server.</p></>}</div><div className="inspector-footer"><ShieldCheck size={16}/><span>{current.action}</span></div></article></section><p className="desk-disclaimer">Final Partner approval and signed dossier release remain unavailable. This workspace is an interactive preview.</p><p role="status" className="micro">{notice}</p></main>
    <dialog ref={modal} className="dossier-modal" onClick={e=>{if(e.target===e.currentTarget)modal.current?.close();}}><div className="modal-top"><span className="micro">KALKI LLP / UNSIGNED SAMPLE</span><button aria-label="Close dossier" onClick={()=>modal.current?.close()}><X size={20}/></button></div><h2>Evidence dossier.</h2><p>{current.name}</p><div className={`quote-box ${current.tone}`}>{current.status}</div><h3>Executive disposition</h3><p>{current.redline}</p><p className="micro">SYNTHETIC DATA. NOT AN ISSUED COMPLIANCE DOSSIER.</p><button className="button" onClick={download}><Download size={16}/> Download sample text</button></dialog>
  </div>;
}
