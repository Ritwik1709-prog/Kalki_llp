import { Link } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
export const navItems = [["Practice","practice"],["How It Works","how-it-works"],["Live Cases","cases"],["Safeguards","safeguards"],["Benchmarks","benchmarks"]];
export function Wordmark(){return <Link to="/" className="wordmark">KALKI <span>LLP</span></Link>}
export function Navigation(){const [open,setOpen]=useState(false);const menu=useRef<HTMLButtonElement>(null);
useEffect(()=>{const close=(event:KeyboardEvent)=>{if(event.key==="Escape" && open){setOpen(false);menu.current?.focus();}};window.addEventListener("keydown",close);return()=>window.removeEventListener("keydown",close);},[open]);return <header className="navigation"><div className="nav-inner"><Wordmark/><nav className={open?"nav-links open":"nav-links"} aria-label="Primary">{navItems.map(([label,id])=><a key={id} href={`/#${id}`} onClick={()=>setOpen(false)}>{label}</a>)}</nav><div className="nav-actions"><Link to="/desk" className="desk-link">Partner Desk</Link><Link to="/desk" className="button small">Commission Audit</Link><button ref={menu} className="menu" aria-label="Toggle navigation" aria-expanded={open} onClick={()=>setOpen(!open)}>{open?<X size={20}/>:<Menu size={20}/>}</button></div></div></header>}
