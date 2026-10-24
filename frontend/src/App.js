import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import DashboardPage from "@/dashboard/DashboardPage";
import DevPage from "@/dashboard/DevPage";
import PortalPage from "@/portal/PortalPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/dev" element={<DevPage />} />
        <Route path="/w/:token" element={<PortalPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster theme="light" position="bottom-right" closeButton />
    </BrowserRouter>
  );
}

export default App;
