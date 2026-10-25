import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import DashboardPage from "@/dashboard/DashboardPage";
import DevPage from "@/dashboard/DevPage";
import SettingsPage from "@/dashboard/SettingsPage";
import SessionsPage from "@/dashboard/SessionsPage";
import PortalPage from "@/portal/PortalPage";
import { AuthCallback, RequireAuth } from "@/dashboard/Auth";

function AppRouter() {
  const location = useLocation();
  const portal = location.pathname.startsWith("/w/");
  if (!portal && location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <>
      {/* Toaster must mount before Routes so it subscribes before page mount effects call toast() */}
      <Toaster theme="light" position={portal ? "top-center" : "bottom-right"} closeButton />
      <Routes>
        <Route path="/" element={<RequireAuth><DashboardPage /></RequireAuth>} />
        <Route path="/dev" element={<RequireAuth><DevPage /></RequireAuth>} />
        <Route path="/settings" element={<RequireAuth><SettingsPage /></RequireAuth>} />
        <Route path="/sessions" element={<RequireAuth><SessionsPage /></RequireAuth>} />
        <Route path="/w/:token" element={<PortalPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppRouter />
    </BrowserRouter>
  );
}

export default App;
