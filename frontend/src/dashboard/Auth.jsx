import { createContext, useContext, useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, errorText } from "@/shared/api";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export const AuthCallback = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const done = useRef(false);
  useEffect(() => {
    if (done.current) { return; }
    done.current = true;
    const sessionId = new URLSearchParams(location.hash.slice(1)).get("session_id");
    api.post("/auth/session", { session_id: sessionId })
      .then((r) => navigate(location.pathname, { replace: true, state: { user: r.data } }))
      .catch((e) => navigate(location.pathname, { replace: true, state: { authError: errorText(e, "Sign-in failed. Please try again.") } }));
  }, [location, navigate]);
  return null;
};

// Login removed by the owner's choice: the dashboard opens without sign-in.
export const RequireAuth = ({ children }) => children;
