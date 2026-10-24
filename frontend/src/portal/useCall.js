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

export const useLiveQuote = (token, initial) => {
  const [quote, setQuote] = useState(initial);
  const [chips, setChips] = useState([]);
  useEffect(() => {
    const id = setInterval(() => {
      api.get(`/portal/${token}`).then((r) => {
        setQuote(r.data.quote);
        setChips(r.data.session?.chips || []);
      }).catch(() => {});
    }, 1500);
    return () => clearInterval(id);
  }, [token]);
  return { quote, chips };
};

export const useCamera = (token) => {
  const [on, setOn] = useState(false);
  const [chips, setChips] = useState([]);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const stop = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setOn(false);
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

  useEffect(() => {
    if (!on) { return undefined; }
    const canvas = document.createElement("canvas");
    const id = setInterval(() => {
      const v = videoRef.current;
      if (!v || !v.videoWidth) return;
      canvas.width = 768;
      canvas.height = Math.round((v.videoHeight * 768) / v.videoWidth);
      canvas.getContext("2d").drawImage(v, 0, 0, canvas.width, canvas.height);
      api.post(`/portal/${token}/frames`, { image: canvas.toDataURL("image/jpeg", 0.7) })
        .then((r) => setChips(r.data.chips || [])).catch(() => {});
    }, 2000);
    return () => clearInterval(id);
  }, [on, token]);

  useEffect(() => () => streamRef.current?.getTracks().forEach((t) => t.stop()), []);

  return { on, start, stop, videoRef, chips };
};
