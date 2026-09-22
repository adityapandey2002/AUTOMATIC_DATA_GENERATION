import { useEffect, useRef } from "react";

const SPEAKER_STYLE = {
  gnm: "bg-sky-100 text-sky-700",
  midwife: "bg-sky-100 text-sky-700",
  anm: "bg-sky-100 text-sky-700",
  patient: "bg-rose-100 text-rose-700",
  mother: "bg-rose-100 text-rose-700",
  unknown: "bg-slate-200 text-slate-600",
};

const SPEAKER_LABEL = {
  gnm: "GNM",
  midwife: "GNM",
  anm: "ANM",
  patient: "Patient",
  mother: "Patient",
  unknown: "Speaker",
};

export default function TranscriptPanel({
  messages,
  liveCount = 0,
  voiceActive = false,
  voiceLevel = 0,
  captureConnected = false,
  recording = false,
  micError = "",
}) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const waveBars = [0, 1, 2, 3, 4, 5, 6];
  const maxHeight = 28;

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-extrabold text-slate-800 tracking-tight">
            Live Transcript
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            {messages.length === 0
              ? voiceActive
                ? "Audio detected — transcribing…"
                : "Waiting for audio..."
              : `${messages.length} segment${messages.length === 1 ? "" : "s"} transcribed`}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          {voiceActive ? (
            <span className="flex items-center gap-1.5 text-[10px] font-bold text-red-500">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse-dot" />
              Hearing…
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-[10px] font-bold text-slate-500">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse-dot" />
              {recording && !captureConnected
                ? "Capture agent not connected"
                : liveCount > 0
                ? `${liveCount} fields detected`
                : "listening"}
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-5 py-4 space-y-4 bg-gradient-to-b from-white to-slate-50/70">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div
              className={`w-14 h-14 rounded-2xl ring-1 flex items-center justify-center mb-3 transition-colors ${
                voiceActive ? "bg-red-50 ring-red-100" : "bg-brand-50 ring-brand-100"
              }`}
            >
              <div className="flex items-end gap-1 h-8">
                {waveBars.map((i) => {
                  const offset = Math.sin((i / waveBars.length) * Math.PI);
                  const height = voiceActive
                    ? Math.max(6, maxHeight * (0.15 + 0.85 * voiceLevel * offset))
                    : 7;
                  return (
                    <span
                      key={i}
                      className="w-1.5 rounded-full bg-brand-400 transition-all duration-150"
                      style={{
                        height: `${height}px`,
                        animationDelay: `${i * 0.11}s`,
                      }}
                    />
                  );
                })}
              </div>
            </div>
            <p className="text-sm font-semibold text-slate-500">
              {voiceActive ? "Hearing…" : "Waiting for audio…"}
            </p>
            <p className="text-xs text-slate-400 mt-1">
              {micError
                ? micError
                : recording
                ? "Speak now — transcribing your voice in real time."
                : "Press Start Recording and speak to the microphone."}
            </p>
          </div>
        )}

        {messages.map((msg, i) => {
          const style = SPEAKER_STYLE[msg.speaker] ?? SPEAKER_STYLE.unknown;
          const label = SPEAKER_LABEL[msg.speaker] ?? SPEAKER_LABEL.unknown;
          return (
            <div key={i} className="animate-fade-up group">
              <div className="flex items-center gap-2 mb-1.5">
                <span className={`inline-flex items-center gap-1 text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-md ${style}`}>
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 13a4 4 0 100-8 4 4 0 000 8zm0 2c-3.5 0-7 1.8-7 4v1h14v-1c0-2.2-3.5-4-7-4z" />
                  </svg>
                  {label}
                </span>
                {msg.language && (
                  <span className="text-[10px] font-semibold text-slate-300 uppercase tracking-wide">
                    · {msg.language}
                  </span>
                )}
              </div>
              <p className="text-sm text-slate-700 leading-relaxed bg-white rounded-xl rounded-tl-sm ring-1 ring-slate-100 shadow-sm px-3.5 py-2.5">
                {msg.text}
              </p>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}