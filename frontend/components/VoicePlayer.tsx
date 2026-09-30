"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Volume2, VolumeX, Square, Play, Sparkles, Radio } from "lucide-react";

interface VoicePlayerProps {
  ws: WebSocket | null;
  wsConnected: boolean;
  onLog?: (direction: "out" | "in" | "system", type: string, payload: any) => void;
}

export default function VoicePlayer({ ws, wsConnected, onLog }: VoicePlayerProps) {
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [autoPlay, setAutoPlay] = useState<boolean>(true);
  const [voiceName, setVoiceName] = useState<string>("Christopher (Neural)");
  const [chunksReceived, setChunksReceived] = useState<number>(0);

  const audioChunksRef = useRef<BlobPart[]>([]);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const currentUrlRef = useRef<string | null>(null);

  // Helper to convert base64 to Uint8Array
  const base64ToUint8Array = (base64: string): Uint8Array => {
    const binaryString = window.atob(base64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes;
  };

  const stopAudio = useCallback(() => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.currentTime = 0;
      currentAudioRef.current = null;
    }
    if (currentUrlRef.current) {
      URL.revokeObjectURL(currentUrlRef.current);
      currentUrlRef.current = null;
    }
    audioChunksRef.current = [];
    setIsPlaying(false);
    setChunksReceived(0);
  }, []);

  const playBufferedAudio = useCallback(() => {
    if (audioChunksRef.current.length === 0) return;

    try {
      // Assemble all received MP3 byte chunks into a single Blob
      const audioBlob = new Blob(audioChunksRef.current, { type: "audio/mpeg" });
      const audioUrl = URL.createObjectURL(audioBlob);

      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
      }
      if (currentUrlRef.current) {
        URL.revokeObjectURL(currentUrlRef.current);
      }

      const audio = new Audio(audioUrl);
      currentAudioRef.current = audio;
      currentUrlRef.current = audioUrl;

      audio.onplay = () => {
        setIsPlaying(true);
      };

      audio.onended = () => {
        setIsPlaying(false);
        if (currentUrlRef.current) {
          URL.revokeObjectURL(currentUrlRef.current);
          currentUrlRef.current = null;
        }
      };

      audio.onerror = (e) => {
        console.error("Audio playback error:", e);
        setIsPlaying(false);
      };

      audio.play().catch((err) => {
        console.warn("Autoplay was blocked or interrupted by browser:", err);
        setIsPlaying(false);
      });
    } catch (err) {
      console.error("Failed to construct audio blob:", err);
      setIsPlaying(false);
    }
  }, []);

  // Listen to WebSocket messages for TTS streaming
  useEffect(() => {
    if (!ws) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "connection_ack" && data.tts_voice) {
          const cleanVoice = data.tts_voice.replace("en-US-", "").replace("Neural", " (Neural)");
          setVoiceName(cleanVoice);
        }

        if (data.type === "audio_stream_start") {
          audioChunksRef.current = [];
          setChunksReceived(0);
          // If previous audio is playing, interrupt it
          if (currentAudioRef.current) {
            currentAudioRef.current.pause();
            currentAudioRef.current = null;
          }
        }

        if (data.type === "audio_stream_chunk" && data.data) {
          const chunk = base64ToUint8Array(data.data);
          audioChunksRef.current.push(chunk.buffer as ArrayBuffer);
          setChunksReceived((prev) => prev + 1);
        }

        if (data.type === "audio_stream_end") {
          if (autoPlay) {
            playBufferedAudio();
          }
        }
      } catch {
        // Non-JSON or other packet
      }
    };

    ws.addEventListener("message", handleMessage);
    return () => {
      ws.removeEventListener("message", handleMessage);
    };
  }, [ws, autoPlay, playBufferedAudio]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopAudio();
    };
  }, [stopAudio]);

  const testTTSVoice = () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const testText = "Hello Alex! Your account balance is fourteen thousand two hundred and fifty dollars, and your FedEx order is out for delivery today.";
    ws.send(JSON.stringify({ type: "test_tts", text: testText }));
    onLog?.("out", "test_tts", { text: testText });
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-[#0e1626]/90 p-4 shadow-xl backdrop-blur-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className={`h-2.5 w-2.5 rounded-full ${
              isPlaying ? "bg-emerald-400 animate-ping" : "bg-cyan-500"
            }`}
          />
          <h3 className="text-xs font-bold tracking-wider uppercase text-slate-200 flex items-center gap-1.5">
            <Volume2 className="h-3.5 w-3.5 text-cyan-400" />
            Neural TTS Audio Player
          </h3>
        </div>

        {/* Auto-Play Toggle */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-[11px] text-slate-400">Auto-Speak</span>
          <button
            onClick={() => setAutoPlay(!autoPlay)}
            className={`relative inline-flex h-4 w-7 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
              autoPlay ? "bg-cyan-500" : "bg-slate-700"
            }`}
            title="Auto-play AI spoken responses"
          >
            <span
              className={`inline-block h-3 w-3 transform rounded-full bg-white transition duration-200 ease-in-out ${
                autoPlay ? "translate-x-3" : "translate-x-0"
              }`}
            />
          </button>
        </div>
      </div>

      {/* Main Player State Display */}
      <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 mb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className={`h-9 w-9 rounded-xl flex items-center justify-center transition-all ${
              isPlaying
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-lg shadow-emerald-500/20 animate-pulse"
                : "bg-slate-900 text-slate-400 border border-slate-800"
            }`}
          >
            {isPlaying ? (
              <Radio className="h-4 w-4 animate-spin text-emerald-400" />
            ) : (
              <Volume2 className="h-4 w-4" />
            )}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-200">
                {isPlaying ? "Copilot Speaking..." : "Speech Engine Ready"}
              </span>
              {isPlaying && (
                <span className="px-1.5 py-0.2 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800 text-[10px] font-mono">
                  Playing MP3
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-400 font-mono">
              Voice: {voiceName} {chunksReceived > 0 && `(${chunksReceived} chunks)`}
            </p>
          </div>
        </div>

        {/* Animated wave bars while speaking */}
        {isPlaying ? (
          <div className="flex items-center gap-1 h-5">
            <span className="w-1 bg-emerald-400 rounded-full animate-bounce h-4" />
            <span className="w-1 bg-cyan-400 rounded-full animate-bounce h-5 delay-75" />
            <span className="w-1 bg-purple-400 rounded-full animate-bounce h-3 delay-150" />
            <span className="w-1 bg-emerald-400 rounded-full animate-bounce h-5 delay-100" />
          </div>
        ) : (
          <span className="text-[11px] text-slate-500 font-mono">Idle</span>
        )}
      </div>

      {/* Action Controls */}
      <div className="flex items-center gap-2">
        {isPlaying ? (
          <button
            onClick={stopAudio}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-rose-600/20 hover:bg-rose-600/30 border border-rose-500/40 text-rose-300 font-medium text-xs transition-colors"
          >
            <Square className="h-3.5 w-3.5 fill-current" />
            Stop & Mute Speech
          </button>
        ) : (
          <button
            onClick={testTTSVoice}
            disabled={!wsConnected}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-gradient-to-r from-purple-600/30 to-indigo-600/30 hover:from-purple-600/40 hover:to-indigo-600/40 border border-purple-500/30 text-purple-200 font-medium text-xs transition-all disabled:opacity-40"
          >
            <Sparkles className="h-3.5 w-3.5 text-purple-400" />
            Test Voice Output
          </button>
        )}
      </div>
    </div>
  );
}
