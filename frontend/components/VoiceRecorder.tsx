"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Mic, MicOff, Square, Radio, Loader2, Sparkles, Volume2 } from "lucide-react";
import AudioWaveform from "./AudioWaveform";

interface VoiceRecorderProps {
  ws: WebSocket | null;
  wsConnected: boolean;
  isTranscribing: boolean;
  onLog: (direction: "out" | "in" | "system", type: string, payload: any) => void;
}

export default function VoiceRecorder({
  ws,
  wsConnected,
  isTranscribing,
  onLog,
}: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordMode, setRecordMode] = useState<"toggle" | "push">("toggle");
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [recordingSeconds, setRecordingSeconds] = useState<number>(0);
  const [micError, setMicError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedBlobsRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const chunksCountRef = useRef<number>(0);
  const isMouseDownRef = useRef<boolean>(false);

  // Pick best supported MIME type
  const getSupportedMimeType = (): string => {
    if (typeof MediaRecorder === "undefined") return "audio/webm";
    const types = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/mp4",
    ];
    for (const t of types) {
      if (MediaRecorder.isTypeSupported(t)) {
        return t;
      }
    }
    return "";
  };

  // Convert blob to base64
  const blobToBase64 = (blob: Blob): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64String = (reader.result as string).split(",")[1];
        resolve(base64String);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  };

  const startRecording = useCallback(async () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setMicError("WebSocket is not connected. Reconnect before speaking.");
      return;
    }

    setMicError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      streamRef.current = stream;
      setMediaStream(stream);

      const mimeType = getSupportedMimeType();
      const options = mimeType ? { mimeType } : undefined;
      const recorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = recorder;
      chunksCountRef.current = 0;
      recordedBlobsRef.current = [];

      recorder.ondataavailable = async (event) => {
        if (event.data && event.data.size > 0) {
          recordedBlobsRef.current.push(event.data);
          chunksCountRef.current += 1;
        }
      };

      recorder.onstop = async () => {
        const fullBlob = new Blob(recordedBlobsRef.current, {
          type: recorder.mimeType || mimeType || "audio/webm",
        });

        let fullBase64 = "";
        if (fullBlob.size > 0) {
          try {
            fullBase64 = await blobToBase64(fullBlob);
          } catch (e) {
            console.error("Failed to convert fullBlob to base64:", e);
          }
        }

        if (ws.readyState === WebSocket.OPEN) {
          ws.send(
            JSON.stringify({
              type: "audio_end",
              data: fullBase64,
              mime_type: recorder.mimeType || mimeType || "audio/webm",
              size: fullBlob.size,
            })
          );
          onLog("out", "audio_end", {
            chunks_streamed: chunksCountRef.current,
            mime_type: recorder.mimeType || mimeType || "audio/webm",
            bytes: fullBlob.size,
          });
        }

        // Stop all audio tracks
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
        }
        setMediaStream(null);
      };

      // Slice audio into 250ms chunks for live low-latency streaming
      recorder.start(250);
      setIsRecording(true);
      setRecordingSeconds(0);

      onLog("out", "audio_start", {
        mime_type: recorder.mimeType || mimeType,
        sample_rate: 16000,
        mode: recordMode,
      });

      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      console.error("Microphone access error:", err);
      setMicError(err.message || "Microphone access denied or unavailable.");
      setIsRecording(false);
    }
  }, [ws, recordMode, onLog]);

  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }

    setIsRecording(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, []);

  // Push to talk event handlers
  const handleMouseDown = () => {
    if (recordMode !== "push") return;
    isMouseDownRef.current = true;
    startRecording();
  };

  const handleMouseUp = () => {
    if (recordMode !== "push") return;
    if (isMouseDownRef.current) {
      isMouseDownRef.current = false;
      stopRecording();
    }
  };

  const handleToggleClick = () => {
    if (recordMode !== "toggle") return;
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const formatSeconds = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-[#0e1626]/90 p-5 shadow-2xl backdrop-blur-md">
      {/* Header & Mode Switcher */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div
            className={`h-2.5 w-2.5 rounded-full ${
              isRecording
                ? "bg-rose-500 animate-ping"
                : isTranscribing
                ? "bg-amber-400 animate-spin"
                : "bg-cyan-500"
            }`}
          />
          <h2 className="text-sm font-semibold tracking-wider uppercase text-slate-200">
            Microphone Voice Stream
          </h2>
        </div>

        {/* Mode Selector */}
        <div className="flex bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-xs">
          <button
            onClick={() => setRecordMode("toggle")}
            className={`px-2.5 py-1 rounded transition-colors ${
              recordMode === "toggle"
                ? "bg-cyan-600 text-white font-medium shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Click to Speak
          </button>
          <button
            onClick={() => setRecordMode("push")}
            className={`px-2.5 py-1 rounded transition-colors ${
              recordMode === "push"
                ? "bg-cyan-600 text-white font-medium shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Push to Talk
          </button>
        </div>
      </div>

      {/* Live Waveform Canvas */}
      <div className="mb-5">
        <AudioWaveform isRecording={isRecording} stream={mediaStream} />
      </div>

      {/* Main Interactive Button Area */}
      <div className="flex flex-col items-center justify-center space-y-3">
        {recordMode === "toggle" ? (
          <button
            onClick={handleToggleClick}
            disabled={!wsConnected || isTranscribing}
            className={`relative flex items-center justify-center gap-3 w-full py-4 px-6 rounded-2xl font-semibold text-sm transition-all duration-300 shadow-xl ${
              isRecording
                ? "bg-rose-600 hover:bg-rose-500 text-white ring-4 ring-rose-500/30 animate-pulse"
                : isTranscribing
                ? "bg-slate-800 text-amber-300 cursor-wait border border-amber-500/30"
                : wsConnected
                ? "bg-gradient-to-r from-cyan-600 via-teal-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white shadow-cyan-600/20"
                : "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50"
            }`}
          >
            {isRecording ? (
              <>
                <Square className="h-5 w-5 fill-current" />
                <span>Stop & Transcribe ({formatSeconds(recordingSeconds)})</span>
              </>
            ) : isTranscribing ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>Processing Whisper STT...</span>
              </>
            ) : (
              <>
                <Mic className="h-5 w-5" />
                <span>{wsConnected ? "Start Speaking" : "Connect WebSocket to Speak"}</span>
              </>
            )}
          </button>
        ) : (
          <button
            onMouseDown={handleMouseDown}
            onMouseUp={handleMouseUp}
            onTouchStart={handleMouseDown}
            onTouchEnd={handleMouseUp}
            disabled={!wsConnected || isTranscribing}
            className={`select-none relative flex items-center justify-center gap-3 w-full py-4 px-6 rounded-2xl font-semibold text-sm transition-all duration-150 shadow-xl ${
              isRecording
                ? "bg-rose-600 text-white ring-4 ring-rose-500/40 scale-[0.98]"
                : isTranscribing
                ? "bg-slate-800 text-amber-300 cursor-wait"
                : wsConnected
                ? "bg-gradient-to-r from-cyan-600 to-blue-600 hover:brightness-110 text-white active:scale-[0.98]"
                : "bg-slate-800 text-slate-500 cursor-not-allowed"
            }`}
          >
            {isRecording ? (
              <>
                <Radio className="h-5 w-5 animate-spin" />
                <span>Release to Transcribe ({formatSeconds(recordingSeconds)})</span>
              </>
            ) : isTranscribing ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>Transcribing Speech...</span>
              </>
            ) : (
              <>
                <Mic className="h-5 w-5" />
                <span>Hold Button to Speak</span>
              </>
            )}
          </button>
        )}

        {/* State Helper Hint */}
        <div className="text-center text-xs text-slate-400">
          {isRecording ? (
            <span className="text-rose-400 flex items-center justify-center gap-1 font-mono">
              <span className="h-2 w-2 rounded-full bg-rose-500 animate-ping inline-block" />
              Streaming 16kHz audio chunks across WebSocket in real time...
            </span>
          ) : isTranscribing ? (
            <span className="text-amber-400 flex items-center justify-center gap-1 font-mono">
              <Sparkles className="h-3 w-3 animate-pulse" />
              FastAPI backend running Groq Whisper-large-v3 transcription...
            </span>
          ) : (
            <span>
              {recordMode === "toggle"
                ? "Click button to start recording, click again when done."
                : "Press and hold mouse button while speaking, release to transcribe."}
            </span>
          )}
        </div>

        {/* Error message */}
        {micError && (
          <div className="w-full p-2.5 rounded-lg bg-rose-950/50 border border-rose-800/60 text-xs text-rose-300 text-center">
            {micError}
          </div>
        )}
      </div>
    </div>
  );
}
