import { useCallback, useRef, useState } from "react";

const SAMPLE_RATE = 16000;
const CHUNK_TARGET_MS = 6000;
const MIN_CHUNK_MS = 800;
const VAD_THRESHOLD = 0.002;
const IDLE_FLUSH_S = 0.9;

const CHUNKS_URL = `ws://${window.location.hostname}:8765/ws/chunks`;

function floatToInt16(buffer) {
  const out = new Int16Array(buffer.length);
  for (let i = 0; i < buffer.length; i++) {
    const s = Math.max(-1, Math.min(1, buffer[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

function arrayBufferToBase64(buffer) {
  let binary = "";
  const bytes = new Uint8Array(buffer);
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function concatInt16(parts) {
  let total = 0;
  for (const p of parts) total += p.length;
  const out = new Int16Array(total);
  let offset = 0;
  for (const p of parts) {
    out.set(p, offset);
    offset += p.length;
  }
  return out;
}

function resampleToRate(input, fromRate, toRate) {
  if (fromRate === toRate) return input;
  const ratio = fromRate / toRate;
  const outLen = Math.floor(input.length / ratio);
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const idx = i * ratio;
    const i0 = Math.floor(idx);
    const i1 = Math.min(i0 + 1, input.length - 1);
    const frac = idx - i0;
    out[i] = input[i0] * (1 - frac) + input[i1] * frac;
  }
  return out;
}

export function useBrowserMic({ language = "hi", onLevel }) {
  const [error, setError] = useState(null);
  const streamRef = useRef(null);
  const wsRef = useRef(null);
  const ctxRef = useRef(null);
  const sourceRef = useRef(null);
  const processorRef = useRef(null);
  const partsRef = useRef([]);
  const pendingRef = useRef([]);
  const chunkIdRef = useRef(0);
  const sampleOffsetRef = useRef(0);
  const vadRef = useRef({ seen: false, idle: 0 });
  const reconnectRef = useRef(0);
  const reconnectTimerRef = useRef(null);
  const onLevelRef = useRef(onLevel);
  onLevelRef.current = onLevel;
  const rmsRef = useRef(0);
  const rawRef = useRef({ anySignal: false });
  const rawRmsRef = useRef(0);
  const analyserRef = useRef(null);
  const analyserReadRef = useRef(() => 0);
  const micInfoRef = useRef({ label: "?", deviceId: "?", sampleRate: 0, channelCount: 0 });
  const encounterIdRef = useRef("");

  const sendPayload = (merged, rate) => {
    if (merged.length < (MIN_CHUNK_MS * SAMPLE_RATE) / 1000) return;
    const pcm_b64 = arrayBufferToBase64(merged.buffer);
    const payload = {
      chunk_id: chunkIdRef.current++,
      pcm_b64,
      // Wire data is ALWAYS 16k mono int16 (resampleToRate normalizes the
      // context rate down to SAMPLE_RATE) - stamp that, not the ctx rate.
      sample_rate: SAMPLE_RATE,
      channels: 1,
      mic_channel: 0,
      start_sample: sampleOffsetRef.current,
      end_sample: sampleOffsetRef.current + merged.length,
      duration_ms: Math.round((merged.length / SAMPLE_RATE) * 1000),
      rms: rmsRef.current,
      raw_rms: rawRmsRef.current,
      analyser_rms: analyserReadRef.current(),
      anySignal: rawRef.current.anySignal,
      actualRate: rate,
      label: micInfoRef.current.label,
      deviceId: micInfoRef.current.deviceId,
      devRate: micInfoRef.current.sampleRate,
      language,
    };
    sampleOffsetRef.current += merged.length;
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    } else {
      pendingRef.current.push(payload);
    }
  };

  const flush = (rate) => {
    if (partsRef.current.length === 0) return;
    const merged = concatInt16(partsRef.current);
    partsRef.current = [];
    vadRef.current = { seen: false, idle: 0 };
    sendPayload(merged, rate);
  };

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      try {
        if (wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(
            JSON.stringify({
              type: "finalize",
              encounter_id: encounterIdRef.current,
            })
          );
        }
      } catch {
        /* ignore */
      }
      try {
        wsRef.current.close();
      } catch {
        /* ignore */
      }
      wsRef.current = null;
    }
    if (processorRef.current) {
      try {
        processorRef.current.disconnect();
      } catch {
        /* ignore */
      }
      processorRef.current = null;
    }
    if (sourceRef.current) {
      try {
        sourceRef.current.disconnect();
      } catch {
        /* ignore */
      }
      sourceRef.current = null;
    }
    if (ctxRef.current) {
      try {
        ctxRef.current.close();
      } catch {
        /* ignore */
      }
      ctxRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    partsRef.current = [];
    pendingRef.current = [];
    vadRef.current = { seen: false, idle: 0 };
    onLevelRef.current?.(0);
  }, []);

  const openWs = useCallback(() => {
    const ws = new WebSocket(CHUNKS_URL);
    wsRef.current = ws;
    const flushPending = () => {
      if (ws.readyState !== WebSocket.OPEN || pendingRef.current.length === 0) return;
      for (const p of pendingRef.current) {
        try {
          ws.send(JSON.stringify(p));
        } catch {
          /* ignore */
        }
      }
      pendingRef.current = [];
    };
    ws.onopen = () => {
      reconnectRef.current = 0;
      ws.send(
        JSON.stringify({
          type: "session_start",
          encounter_id: encounterIdRef.current,
        })
      );
      flushPending();
    };
    ws.onclose = () => {
      if (wsRef.current === ws) wsRef.current = null;
      const delay = Math.min(2000 * 2 ** reconnectRef.current, 30000);
      reconnectRef.current += 1;
      reconnectTimerRef.current = setTimeout(() => {
        if (streamRef.current) openWs();
      }, delay);
    };
    ws.onerror = () => {
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    };
  }, []);

  const start = useCallback(
    async (encounterId) => {
      if (streamRef.current) return;
      setError(null);
      encounterIdRef.current = encounterId;

      // Create + resume the AudioContext synchronously inside the user gesture
      // (Chrome suspends contexts created in async callbacks, which silently
      // stops onaudioprocess and produces no audio — the "0 chunks" bug).
      //
      // Do NOT force {sampleRate: 16000} on the context. The mic's
      // MediaStreamSource runs at the DEVICE rate (44.1/48 kHz); a 16k context
      // makes Chrome/Edge resample that stream internally, and in current builds
      // that resampler feeds ALL-ZERO buffers to ScriptProcessorNode — getUserMedia
      // resolves, callbacks fire, but every sample is 0 (exactly the
      // "js_rms=0.0000 anySignal=False" signature). Create the context at the
      // default device rate and let resampleToRate() below downconvert to 16k
      // for the wire (this path is proven correct).
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioCtx();
      if (ctx.state === "suspended") {
        try {
          await ctx.resume();
        } catch {
          /* ignore */
        }
      }
      ctxRef.current = ctx;
      const actualRate = ctx.sampleRate || SAMPLE_RATE;

      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
          },
        });
      } catch (err) {
        ctxRef.current = null;
        try {
          ctx.close();
        } catch {
          /* ignore */
        }
        setError(err?.message || "Microphone access denied");
        return;
      }
      streamRef.current = stream;
      const track = stream.getAudioTracks()[0];
      let settings = {};
      try {
        settings = track?.getSettings?.() ?? {};
      } catch {
        /* ignore */
      }
      micInfoRef.current = {
        label: track?.label || "?",
        deviceId: settings.deviceId || "?",
        sampleRate: settings.sampleRate || 0,
        channelCount: settings.channelCount || 0,
      };

      const source = ctx.createMediaStreamSource(stream);
      sourceRef.current = source;
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      // AnalyserNode taps the MediaStreamSource DIRECTLY — ground truth that
      // bypasses ScriptProcessor entirely. If this shows signal but
      // onaudioprocess input shows zeros, the ScriptProcessor input is the
      // problem (switch to AudioWorklet). If this ALSO shows zeros, the OS/browser
      // mic input is genuinely silent (wrong device / OS privacy / no mic).
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 2048;
      analyserRef.current = analyser;
      const mute = ctx.createGain();
      mute.gain.value = 0;
      source.connect(processor);
      source.connect(analyser);
      processor.connect(mute);
      mute.connect(ctx.destination);

      const readAnalyserRms = () => {
        try {
          const data = new Float32Array(analyser.fftSize);
          analyser.getFloatTimeDomainData(data);
          let s = 0;
          for (let i = 0; i < data.length; i++) s += data[i] * data[i];
          return Math.sqrt(s / data.length);
        } catch {
          return 0;
        }
      };
      analyserReadRef.current = readAnalyserRms;

      processor.onaudioprocess = (e) => {
        let input = e.inputBuffer.getChannelData(0);
        let rawSum = 0;
        for (let i = 0; i < input.length; i++) rawSum += input[i] * input[i];
        const rawRms = Math.sqrt(rawSum / input.length);
        if (actualRate !== SAMPLE_RATE) {
          input = resampleToRate(input, actualRate, SAMPLE_RATE);
        }
        let sum = 0;
        for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
        const rms = Math.sqrt(sum / input.length);
        rmsRef.current = rms;
        rawRmsRef.current = rawRms;
        const isSpeech = rms > VAD_THRESHOLD;
        onLevelRef.current?.(isSpeech ? Math.min(1, rms * 6) : 0);
        if (rms > 0.0005 && !rawRef.current.anySignal) rawRef.current.anySignal = true;

        const vad = vadRef.current;
        if (isSpeech) {
          vad.seen = true;
          vad.idle = 0;
        } else {
          vad.idle += input.length / SAMPLE_RATE;
        }

        partsRef.current.push(floatToInt16(input));
        const accumulatedMs =
          (partsRef.current.reduce((n, p) => n + p.length, 0) / SAMPLE_RATE) * 1000;

        if (isSpeech && accumulatedMs >= CHUNK_TARGET_MS) {
          flush(actualRate);
        } else if (vad.idle >= IDLE_FLUSH_S && accumulatedMs >= MIN_CHUNK_MS) {
          flush(actualRate);
        }
      };

      openWs();
    },
    [openWs]
  );

  const stop = useCallback(() => {
    // Flush any buffered tail speech before tearing down.
    if (partsRef.current.length > 0) {
      flush(ctxRef.current?.sampleRate || SAMPLE_RATE);
    }
    cleanup();
  }, [cleanup]);

  return { start, stop, error };
}
