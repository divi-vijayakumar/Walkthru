import { createContext, useContext, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, errorText } from "@/shared/api";
import { Logo } from "@/dashboard/Sidebar";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

const signIn = () => {
  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  const redirectUrl = window.location.origin + window.location.pathname;
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
};

const LoginScreen = ({ error }) => (
  <div data-testid="login-screen" className="grid min-h-screen place-items-center bg-wt-ink px-5">
    <div className="w-full max-w-sm rounded-2xl bg-white p-7">
      <Logo dark={false} />
      <h1 className="mt-6 font-display text-3xl font-bold text-wt-ink">Contractor sign in</h1>
      <p className="mt-2 text-[15px] text-wt-muted">Watch every lead from first text to deposit.</p>
      {error && <p data-testid="login-error" className="mt-4 rounded-lg bg-[#FDE2E2] px-3 py-2 text-sm font-semibold text-[#B91C1C]">{error}</p>}
      <button data-testid="google-signin-btn" onClick={signIn}
        className="mt-6 flex min-h-[52px] w-full items-center justify-center gap-3 rounded-xl bg-wt-accent text-[16px] font-bold text-white transition-colors hover:bg-wt-accentDark">
        Sign in with Google
      </button>
      <p className="mt-4 text-[13px] text-wt-muted">Only approved Apex Remodeling accounts can get in.</p>
    </div>
  </div>
);

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

export const RequireAuth = ({ children }) => {
  const location = useLocation();
  const [user, setUser] = useState(location.state?.user || null);
  const [checked, setChecked] = useState(!!location.state?.user);
  const [error, setError] = useState(location.state?.authError || null);

  useEffect(() => {
    if (user) { return; }
    api.get("/auth/me")
      .then((r) => setUser(r.data))
      .catch((e) => { if (e?.response?.status === 403) setError(errorText(e)); })
      .finally(() => setChecked(true));
  }, [user]);

  const signOut = async () => {
    await api.post("/auth/logout").catch(() => {});
    setUser(null);
    setError(null);
  };

  if (!checked) return <div data-testid="auth-loading" className="min-h-screen bg-wt-ground" />;
  if (!user) return <LoginScreen error={error} />;
  return <AuthContext.Provider value={{ user, signOut }}>{children}</AuthContext.Provider>;
};
