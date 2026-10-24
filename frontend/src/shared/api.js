import axios from "axios";

export const api = axios.create({ baseURL: `${process.env.REACT_APP_BACKEND_URL}/api`, withCredentials: true });

api.interceptors.response.use(undefined, (error) => {
  const url = error?.config?.url || "";
  const status = error?.response?.status;
  if ((status === 401 || status === 403) && !url.startsWith("/auth/") && !url.startsWith("/portal/")) {
    window.dispatchEvent(new CustomEvent("wt-auth-lost", { detail: error.response.data?.detail }));
  }
  return Promise.reject(error);
});

export const errorText = (e, fallback = "Something went wrong") => e?.response?.data?.detail || fallback;
