import { BrowserRouter, Routes, Route } from "react-router-dom";
import Nav from "./Nav";
import Dashboard from "./pages/Dashboard";
import Schedule from "./pages/Schedule";
import History from "./pages/History";
import Settings from "./pages/Settings";
import "./App.css";

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <header className="app-header">
          <h1>Irrigation Controller</h1>
          <Nav />
        </header>
        <main className="app-main">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/schedule" element={<Schedule />} />
            <Route path="/history" element={<History />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
