import { useEffect } from "react";
import { useLocation } from "react-router-dom";
export default function Experience(){const {pathname}=useLocation();useEffect(()=>{
 const sections=document.querySelectorAll(".section-heading,.practice-grid article,.closing,.safeguards>div,.economics-grid>div,.boundary-copy,.chamber,.scorecard");
 const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add("revealed");observer.unobserve(entry.target);}}),{threshold:.08});
 sections.forEach(element=>{element.classList.add("reveal-ready");observer.observe(element);});
 const update=()=>{const height=document.documentElement.scrollHeight-innerHeight;document.documentElement.style.setProperty("--reading-progress",`${height>0?scrollY/height:0}`);};
 update();window.addEventListener("scroll",update,{passive:true});
 return()=>{observer.disconnect();window.removeEventListener("scroll",update);sections.forEach(el=>el.classList.remove("reveal-ready"));};
 },[pathname]);return <div className="reading-progress" aria-hidden="true"/>}
