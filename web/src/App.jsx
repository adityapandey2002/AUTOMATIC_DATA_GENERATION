import { useEffect, useRef, useState, useCallback } from "react";
import { useWebSocket } from "./hooks/useWebSocket";
import { useBrowserMic } from "./hooks/useBrowserMic";
import TranscriptPanel from "./components/TranscriptPanel";
import CaseSheetForm from "./components/CaseSheetForm";
import AlertBanner from "./components/AlertBanner";
import PatientsList from "./components/PatientsList";
import { FORM_SCHEMA } from "./formSchema";

const WS_URL =
  import.meta.env.VITE_WS_URL ||
  `ws://${window.location.hostname}:8765/ws/dashboard`;

function uuid() {
  if (crypto?.randomUUID) return crypto.randomUUID();
  return "rec-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10);
}

export default function App() {
  const { connected, lastMessage, send } = useWebSocket(WS_URL);
  const [schema, setSchema] = useState(FORM_SCHEMA);
  const [messages, setMessages] = useState([]);
  const [answers, setAnswers] = useState({});
  const [alerts, setAlerts] = useState([]);
  const [recording, setRecording] = useState(false);
  const [startedAt, setStartedAt] = useState(null);
  const [elapsed, setElapsed] = useState("");
  const [voiceActive, setVoiceActive] = useState(false);
  const [voiceLevel, setVoiceLevel] = useState(0);
  const [captureConnected, setCaptureConnected] = useState(false);
  const [tab, setTab] = useState("scribe");
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState("");
  const [lastSavedAt, setLastSavedAt] = useState(null);
  const timerRef = useRef(null);
  const voiceTimerRef = useRef(null);
  const encounterIdRef = useRef("");

  const { start: startMic, stop: stopMic, error: micError } = useBrowserMic({
    language: "hi",
    onLevel: (level) => {
      setVoiceLevel(level);
      if (level > 0) {
        setVoiceActive(true);
        if (voiceTimerRef.current) clearTimeout(voiceTimerRef.current);
        voiceTimerRef.current = setTimeout(() => setVoiceActive(false), 1500);
      }
    },
  });

  useEffect(() => {
    fetch("/api/schema")
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => s && setSchema(s))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (recording) {
      const t0 = startedAt || Date.now();
      setStartedAt(t0);
      timerRef.current = setInterval(() => {
        const s = Math.floor((Date.now() - t0) / 1000);
        const m = Math.floor(s / 60);
        setElapsed(`${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`);
      }, 1000);
    } else {
      clearInterval(timerRef.current);
      setElapsed("");
    }
    return () => clearInterval(timerRef.current);
  }, [recording, startedAt]);

  useEffect(() => () => clearTimeout(voiceTimerRef.current), []);

  useEffect(() => {
    if (micError && recording) {
      stopMic();
      setRecording(false);
      setStartedAt(null);
    }
  }, [micError, recording, stopMic]);

  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === "voice_activity") {
      setVoiceActive(true);
      if (voiceTimerRef.current) clearTimeout(voiceTimerRef.current);
      voiceTimerRef.current = setTimeout(() => setVoiceActive(false), 1500);
    }

    if (lastMessage.type === "capture_status") {
      setCaptureConnected(Boolean(lastMessage.connected));
    }

    if (lastMessage.type === "session_state") {
      setRecording(Boolean(lastMessage.active));
      if (!lastMessage.active) setVoiceActive(false);
      if (lastMessage.active) {
        setMessages([]);
        setAnswers({});
        setAlerts([]);
        setStartedAt(Date.now());
        setSaveStatus("");
      }
    }

    if (lastMessage.type === "snapshot") {
      if (lastMessage.answers) setAnswers(lastMessage.answers);
      if (Array.isArray(lastMessage.transcript)) {
        setMessages((prev) => [...prev, ...lastMessage.transcript]);
      } else if (lastMessage.transcript) {
        setMessages([{ text: lastMessage.transcript, speaker: "unknown", language: "" }]);
      }
    }

    if (lastMessage.type === "chunk_result") {
      if (lastMessage.transcript && lastMessage.status !== "rejected" && lastMessage.status !== "empty") {
        setMessages((prev) => [
          ...prev,
          {
            text: lastMessage.transcript,
            speaker: lastMessage.speaker,
            language: lastMessage.language,
            tentative: lastMessage.status === "tentative",
          },
        ]);
      }
      if (lastMessage.answers) setAnswers(lastMessage.answers);
      if (lastMessage.alerts?.length) setAlerts(lastMessage.alerts);
    }

    if (lastMessage.type === "field_updated") {
      if (lastMessage.answers) setAnswers(lastMessage.answers);
    }

    if (lastMessage.type === "finalize_result") {
      setAnswers(lastMessage.answers || {});
      setAlerts(lastMessage.alerts || []);
      setRecording(false);
      setStartedAt(null);
      setElapsed("");
      setVoiceActive(false);
    }

    if (lastMessage.type === "save_result") {
      setSaving(false);
      if (lastMessage.ok) {
        setLastSavedAt(Date.now());
        setSaveStatus(`Saved ✓ ${lastMessage.encounter_id || ""}`);
        setTab("patients");
      } else {
        setSaveStatus(lastMessage.error || "Save failed");
      }
    }
  }, [lastMessage]);

  const handleEdit = useCallback(
    (field, value) => {
      setAnswers((prev) => ({ ...prev, [field]: value }));
      send({ type: "set_field", field, value });
      setSaveStatus("");
    },
    [send]
  );

  const handleSave = useCallback(() => {
    setSaving(true);
    setSaveStatus("Saving…");
    send({ type: "save" });
    setTimeout(() => {
      setSaving((s) => {
        if (s) setSaveStatus("No response from backend");
        return false;
      });
    }, 8000);
  }, [send]);

  const handleMic = useCallback(() => {
    if (recording) {
      stopMic();
      setRecording(false);
      setStartedAt(null);
      setVoiceActive(false);
      setVoiceLevel(0);
    } else {
      const encounterId = uuid();
      encounterIdRef.current = encounterId;
      setMessages([]);
      setAnswers({});
      setAlerts([]);
      setRecording(true);
      setStartedAt(Date.now());
      setSaveStatus("");
      startMic(encounterId);
    }
  }, [recording, startMic, stopMic]);

  const filledCount = Object.values(answers ?? {}).filter(
    (v) => v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && v.length === 0)
  ).length;

  return (
    <div className="h-screen flex flex-col bg-gradient-to-br from-slate-50 via-white to-brand-50/40">
      {/* Header */}
      <header className="bg-gradient-to-r from-brand-800 via-brand-700 to-brand-600 text-white shadow-lg">
        <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/15 backdrop-blur flex items-center justify-center shadow-inner">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 12h4l2-6 4 12 2-6h6" />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-extrabold tracking-tight leading-none">
                Ambient Scribe
                <span className="ml-2 text-sm font-bold text-brand-200">मातृत्व केस शीट</span>
              </h1>
              <p className="text-xs text-brand-100/90 mt-0.5 font-medium">
                Maternity Case Sheet · L1 PHC — State Health Society, Bihar
              </p>
            </div>
          </div>

          <nav className="flex items-center gap-1 bg-black/15 rounded-full p-1">
            <button
              onClick={() => setTab("scribe")}
              className={`px-4 py-1.5 rounded-full text-xs font-extrabold transition-all ${
                tab === "scribe" ? "bg-white text-brand-800 shadow" : "text-white/80 hover:text-white"
              }`}
            >
              Scribe
            </button>
            <button
              onClick={() => setTab("patients")}
              className={`px-4 py-1.5 rounded-full text-xs font-extrabold transition-all ${
                tab === "patients" ? "bg-white text-brand-800 shadow" : "text-white/80 hover:text-white"
              }`}
            >
              Patients
            </button>
          </nav>

          <div className="flex items-center gap-2.5">
            {recording && (
              <span className="text-xs font-extrabold tabular-nums bg-black/20 px-2.5 py-1 rounded-full">
                ⏱ {elapsed}
              </span>
            )}

            <button
              onClick={handleMic}
              disabled={!connected}
              className={`group flex items-center gap-2 rounded-full px-4 py-2 text-sm font-extrabold transition-all shadow-lg active:scale-95 ${
                recording
                  ? "bg-red-500 hover:bg-red-600 text-white"
                  : connected
                  ? "bg-white hover:bg-brand-50 text-brand-800"
                  : "bg-white/20 text-white/50 cursor-not-allowed"
              }`}
              title={connected ? (recording ? "Stop recording" : "Start recording") : "Waiting for backend…"}
            >
              {recording ? (
                <span className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 bg-white rounded-full animate-pulse-dot" />
                  Stop
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
                  </svg>
                  Start Recording
                </span>
              )}
            </button>

            <span
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold shadow ${
                connected
                  ? "bg-emerald-400/90 text-emerald-950"
                  : "bg-red-500/90 text-white"
              }`}
              title={connected ? "Connected" : "Disconnected"}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  connected ? "bg-emerald-900 animate-pulse-dot" : "bg-white animate-pulse-dot"
                }`}
              />
              {connected ? "LIVE" : "OFFLINE"}
            </span>
          </div>
        </div>
      </header>

      {/* Alerts */}
      {micError && (
        <div className="mx-5 mt-3 rounded-xl bg-red-50 ring-1 ring-red-300 px-4 py-2.5 text-sm font-semibold text-red-700 shadow-sm">
          🎙 {micError}
        </div>
      )}
      <div className="px-5 pt-3">
        <AlertBanner alerts={alerts} />
      </div>

      {/* Main */}
      {tab === "patients" ? (
        <div className="flex-1 min-h-0 p-5">
          <div className="h-full rounded-2xl bg-white shadow-card ring-1 ring-slate-200/60 overflow-hidden flex flex-col">
            <PatientsList refreshToken={lastSavedAt} />
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-0 p-5 grid grid-cols-1 xl:grid-cols-[2fr_3fr] gap-5">
          <div className="min-h-0 rounded-2xl bg-white shadow-card ring-1 ring-slate-200/60 overflow-hidden flex flex-col">
            <TranscriptPanel
              messages={messages}
              liveCount={filledCount}
              voiceActive={voiceActive}
              voiceLevel={voiceLevel}
              captureConnected={captureConnected || recording}
              recording={recording}
              micError={micError}
            />
          </div>

          <div className="min-h-0 rounded-2xl bg-white shadow-card ring-1 ring-slate-200/60 overflow-hidden flex flex-col">
            <CaseSheetForm
              schema={schema}
              answers={answers}
              onEdit={handleEdit}
              onSave={handleSave}
              saving={saving}
              saveStatus={saveStatus}
            />
          </div>
        </div>
      )}
    </div>
  );
}
