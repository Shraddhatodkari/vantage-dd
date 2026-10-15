import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router";
import "./index.css";
import { AuthProvider, useAuth } from "./lib/auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Deals from "./pages/Deals";
import Compare from "./pages/Compare";
import DealDetail from "./pages/DealDetail";
import Audit from "./pages/Audit";
import Account from "./pages/Account";
import ResetPassword from "./pages/ResetPassword";

function Protected({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth();
  const { pathname } = useLocation();
  if (loading) return <div className="p-10 text-sm text-slate-500">Loading…</div>;
  if (!session) return <Navigate to="/login" replace />;
  // a role that requires 2FA can only reach the enrolment page until it is set up (the API enforces the same)
  if (session.mfa_setup_required && pathname !== "/account") return <Navigate to="/account" replace />;
  return <>{children}</>;
}

function Home() {
  const { can } = useAuth();
  return can("deal:read") ? <Dashboard /> : can("audit:read") ? <Navigate to="/audit" replace /> : <Navigate to="/account" replace />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route element={<Protected><Layout /></Protected>}>
            <Route path="/" element={<Home />} />
            <Route path="/deals" element={<Deals />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/deals/:id" element={<DealDetail />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/account" element={<Account />} />
          </Route>
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </React.StrictMode>,
);
