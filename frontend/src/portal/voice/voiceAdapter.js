import { createMockAdapter } from "@/portal/voice/mockAdapter";
import { createVapiAdapter } from "@/portal/voice/vapiAdapter";

// voice_adapter: start(), stop(), onCaption(cb), onEnd(cb). Mode comes from the server env (VOICE_MODE).
export const createVoiceAdapter = ({ token, data, mode, chat = false }) =>
  data.voice?.mode === "vapi" && !chat
    ? createVapiAdapter({ token, data, mode })
    : createMockAdapter({ token, data, mode, chat });
