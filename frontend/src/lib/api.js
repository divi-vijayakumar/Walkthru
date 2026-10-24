import axios from "axios";

export const api = axios.create({ baseURL: `${process.env.REACT_APP_BACKEND_URL}/api` });

export const STATUSES = {
  new: { label: "New", className: "bg-orange-500/15 text-orange-400 border-orange-500/30" },
  in_review: { label: "In review", className: "bg-sky-500/15 text-sky-400 border-sky-500/30" },
  quoted: { label: "Quoted", className: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" },
  archived: { label: "Archived", className: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30" },
};

export const timeAgo = (iso) => {
  const mins = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
};
