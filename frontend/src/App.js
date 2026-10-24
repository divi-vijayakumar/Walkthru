import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AppLayout } from "@/components/AppLayout";
import Dashboard from "@/pages/Dashboard";
import LeadDetail from "@/pages/LeadDetail";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/leads/:leadId" element={<LeadDetail />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
      <Toaster theme="dark" position="bottom-right" />
    </BrowserRouter>
  );
}

export default App;
