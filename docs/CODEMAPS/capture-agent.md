# Capture Agent Codemap (capture-agent/)

**Last Updated:** 2026-09-23

Standalone client that captures mic audio, denoises, chunks on speech, and streams PCM bytes to
the backend `/ws/chunks`. Used on a separate clinic laptop (via `deploy/scripts/install-laptop.bat`
if desired); the web dashboard's browser mic is the in-clinic alternative.

## Pipeline

```
recorder.py (16kHz stereo USB mic, float32)
   → denoise.py (DeepFilterNet primary, RNNoise fallback; probe.py decides)
   → vad.py (Silero VAD, 512-sample frames @16kHz, chunks speech)
   → streamer.py (websocket-client, spools + reconnects, sends chunk + finalize)
└── main.py orchestrates; sends chunks ≥ 300ms; finalize if --encounter-id
```

## Modules

| File | Purpose |
|------|---------|
| `main.py` | CLI orchestration; args: `--backend-url`, `--mic-device`, `--denoiser [auto|deepfilter|rnnoise]`, `--encounter-id`, `--language [hi|mai]` |
| `recorder.py` | `sounddevice.InputStream`, 16kHz, 2ch (stereo for future diarization), `BLOCK_SIZE=1024` |
| `denoise.py` | `DeepFilterDenoiser` (df.enhance) + `RNNoiseDenoiser` (rnnoise_demo subprocess); `create_denoiser(backend)` |
| `probe.py` | CPU/RAM benchmark; `MachineProfile.evaluate()` → deepfilter vs rnnoise |
| `vad.py` | `VADChunker`: Silero VAD via `torch.hub.load(snakers4/silero-vad)`; 512-sample window @16kHz (256 @8kHz); buffers input; emits `SpeechChunk` (float32 mono, start/end sample, PCM bytes) on silence ≥ 400ms; max 10s speech, 300ms context |
| `streamer.py` | `ChunkStreamer` (websocket-client): `connect()` retries, `send_chunk()` spools on failure (disconnect/reconnect loop), `send_finalize(encounter_id)` for type `finalize`, `disconnect()` |

## Message Payload

Chunks are sent as JSON:
```
{ chunk_id, pcm_b64 (16k mono int16), sample_rate=16000, channels=1, mic_channel,
  start_sample, end_sample, duration_ms, language }
```
Finalize (`--encounter-id` provided) sends `{type: "finalize", encounter_id}`.
The backend now **responds** to the chunks socket with `chunk_result` / `finalize_result`,
so the capture agent could consume results (today `main.py` just streams; `streamer.py`
does not currently parse replies).

## Dependencies (requirements.txt)

- `sounddevice==0.5.1`, `numpy>=1.24`, `silero-vad>=5.1`, `torch>=2.0`, `torchaudio>=2.0`,
  `websocket-client>=1.8`, `pydantic>=2.0`, `psutil>=5.9`
- PyInstaller spec `capture-agent.spec` for a standalone exe.

### Known quirks (from this repo's setup)

- `numpy>=1.24` — numpy **<2 has no Python 3.14 wheels**; install into the backend venv.
- torch: **2.9.1+cpu**, torchaudio, **silero-vad 6.2.2** (VAD needs 512-sample frames @16kHz).
- `edge-tts` + `soundfile` installed in backend venv for generating TTS test audio.
- NeMo NOT installed in this repo — IndicConformer ASR degrades gracefully (Groq handles
  Maithili-as-Hindi).

## Usage

```powershell
# From repo ROOT (uses the backend venv):
backend\venv\Scripts\python.exe capture-agent\main.py --language hi --encounter-id demo
```

Connect target: `--backend-url ws://127.0.0.1:8765/ws/chunks` (default ws://localhost:8765).

## Related Areas

- [backend.md](backend.md) — `/ws/chunks` protocol + ASR chain.
- [frontend.md](frontend.md) — browser-mic alternative.
- [INDEX.md](INDEX.md)