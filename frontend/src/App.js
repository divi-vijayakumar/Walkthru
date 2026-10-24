import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import DashboardPage from "@/dashboard/DashboardPage";
import DevPage from "@/dashboard/DevPage";
import PortalPage from "@/portal/PortalPage";
import { AuthCallback, RequireAuth } from "@/dashboard/Auth";

function AppRouter() {
  const location = useLocation();
  const portal = location.pathname.startsWith("/w/");
  if (!portal && location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <>
      <Routes>
        <Route path="/" element={<RequireAuth><DashboardPage /></RequireAuth>} />
        <Route path="/dev" element={<RequireAuth><DevPage /></RequireAuth>} />
        <Route path="/w/:token" element={<PortalPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster theme="light" position={portal ? "top-center" : "bottom-right"} closeButton />
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
