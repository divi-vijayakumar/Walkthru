import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/api";

export const useCallFeed = (adapter, token, onEnded) => {
  const [caption, setCaption] = useState(null);
  const [lines, setLines] = useState([]);
  const [prompt, setPrompt] = useState(null);
  const endRef = useRef(onEnded);
  endRef.current = onEnded;

  useEffect(() => {
    const offCaption = adapter.onCaption((c) => {
      setCaption(c);
      if (c.final === false) return;
      setLines((l) => [...l, c]);
      api.post(`/portal/${token}/call/caption`, { role: c.role, text: c.text }).catch(() => {});
    });
    const offEnd = adapter.onEnd(() => endRef.current());
    const offPrompt = adapter.onPrompt(setPrompt);
    return () => { offCaption(); offEnd(); offPrompt(); };
  }, [adapter, token]);

  return { caption, lines, prompt };
};

export const useLiveQuote = (token, initial, adapter) => {
  const [quote, setQuote] = useState(initial);
  const [chips, setChips] = useState([]);
  useEffect(() => {
    const id = setInterval(() => {
      api.get(`/portal/${token}`, { params: { live: 1 } }).then((r) => {
        setQuote(r.data.quote);
        setChips(r.data.session?.chips || []);
        (r.data.insights || []).forEach((text) => adapter?.injectInsight?.(text));
      }).catch(() => {});
    }, 1500);
    return () => clearInterval(id);
  }, [token, adapter]);
  return { quote, chips };
};

const CLIP_MS = 10000;
const FIRST_CLIP_MS = 5000;
const MIME = typeof MediaRecorder === "undefined" ? null
  : ["video/webm;codecs=vp8", "video/webm", "video/mp4"].find((m) => MediaRecorder.isTypeSupported(m)) || "";

const uploadClip = (token, sessionId, tStart, durationMs, blob) => {
  const form = new FormData();
  form.append("session_id", sessionId);
  form.append("kind", "video");
  form.append("seq", String(tStart));
  form.append("t_start_ms", String(tStart));
  form.append("duration_ms", String(durationMs));
  form.append("file", blob, blob.type.includes("mp4") ? "clip.mp4" : "clip.webm");
  return api.post("/media", form, { headers: { "X-Portal-Token": token }, timeout: 60000 }).catch(() => {});
};

// Records ~10 s standalone clips while the camera is on and uploads each one
const useClipRecorder = (on, token, streamRef) => {
  useEffect(() => {
    if (!on || MIME === null) { return undefined; }
    let stopped = false;
    let seq = 0;
    let rec = null;
    let timer = null;
    const begin = async () => {
      const { data } = await api.get(`/portal/${token}`);
      const session = data.session;
      if (!session || stopped || !streamRef.current) return;
      const t0 = Date.parse(session.started_at);
      const next = () => {
        if (stopped || !streamRef.current) return;
        const chunks = [];
        const start = Date.now();
        rec = new MediaRecorder(streamRef.current, MIME ? { mimeType: MIME, videoBitsPerSecond: 1000000 } : undefined);
        rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
        rec.onstop = () => {
          if (chunks.length) uploadClip(token, session.id, Math.max(0, start - t0), Date.now() - start, new Blob(chunks, { type: rec.mimeType || "video/webm" }));
          next();
        };
        rec.start();
        timer = setTimeout(() => { if (rec.state !== "inactive") rec.stop(); }, seq++ === 0 ? FIRST_CLIP_MS : CLIP_MS);
      };
      next();
    };
    begin().catch(() => {});
    return () => {
      stopped = true;
      clearTimeout(timer);
      if (rec && rec.state !== "inactive") rec.stop();
    };
  }, [on, token, streamRef]);
};

export const useCamera = (token) => {
  const [on, setOn] = useState(false);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const stop = () => {
    setOn(false);
    setTimeout(() => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }, 300);
    api.post(`/portal/${token}/call/camera`, { on: false }).catch(() => {});
  };

  const start = async () => {
    try {
      streamRef.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      setOn(true);
      api.post(`/portal/${token}/call/camera`, { on: true }).catch(() => {});
      return true;
    } catch {
      return false;
    }
  };

  useEffect(() => {
    if (on && videoRef.current) videoRef.current.srcObject = streamRef.current;
  }, [on]);

  useClipRecorder(on, token, streamRef);

  useEffect(() => () => streamRef.current?.getTracks().forEach((t) => t.stop()), []);

  return { on, start, stop, videoRef };
};
