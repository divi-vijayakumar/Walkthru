import axios from "axios";

export const api = axios.create({ baseURL: `${process.env.REACT_APP_BACKEND_URL}/api` });

export const errorText = (e, fallback = "Something went wrong") => e?.response?.data?.detail || fallback;
