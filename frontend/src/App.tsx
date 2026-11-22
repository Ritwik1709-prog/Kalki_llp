import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import Experience from "./components/landing/Experience";
import LandingPage from "./pages/LandingPage";
const DeskPage = lazy(() => import("./pages/Desk"));
export default function App() {
  return <BrowserRouter><Experience/><Suspense fallback={<main className="wrap section" role="status">Opening Partner Desk?</main>}><Routes>
    <Route path="/" element={<LandingPage/>}/>
    <Route path="/desk" element={<DeskPage/>}/>
    <Route path="*" element={<main className="wrap section"><h1>Page not found.</h1><Link to="/">Return to Kalki</Link></main>}/>
  </Routes></Suspense></BrowserRouter>;
}
