import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import AppRoutes from "./routes/AppRoutes.jsx";

function MobileMenu() {
  const location = useLocation();
  const isDashboard = location.pathname.startsWith("/dashboard");

  // Close sidebar whenever the route changes (nav link tapped)
  useEffect(() => {
    document.body.classList.remove("ps-sidebar-open");
  }, [location.pathname]);

  // Only render on dashboard pages — auth pages / landing have no sidebar
  if (!isDashboard) return null;

  const toggle = () => document.body.classList.toggle("ps-sidebar-open");
  const close = () => document.body.classList.remove("ps-sidebar-open");

  return (
    <>
      <button
        className="ps-hamburger-btn"
        onClick={toggle}
        aria-label="Toggle navigation menu"
      >
        ☰
      </button>
      <div className="ps-sidebar-overlay" onClick={close} />
    </>
  );
}

export default function App() {
  return (
    <>
      <MobileMenu />
      <AppRoutes />
    </>
  );
}
