import { NavLink } from "react-router-dom";

export default function Nav() {
  return (
    <nav className="nav">
      <NavLink to="/" end className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
        Dashboard
      </NavLink>
      <NavLink to="/schedule" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
        Schedule
      </NavLink>
      <NavLink to="/history" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
        History
      </NavLink>
      <NavLink to="/settings" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
        Settings
      </NavLink>
    </nav>
  );
}
