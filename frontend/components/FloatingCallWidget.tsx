"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  Phone,
  PhoneOff,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Sparkles,
  Bot,
  User,
  Clock,
  CheckCircle2,
  Calendar,
  X,
  MessageSquare,
  Wrench,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import AudioWaveform from "./AudioWaveform";

interface ToolExecution {
  tool: string;
  call_id?: string;
  args?: any;
  output?: any;
}

interface MessageTurn {
  id: string;
  role: "user" | "assistant";
  text: string;
  tools_used?: ToolExecution[];
  timestamp: number;
}

interface FloatingCallWidgetProps {
  wsUrl?: string;
}

export default function FloatingCallWidget({ wsUrl = "ws://localhost:8000" }: FloatingCallWidgetProps) {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [callActive, setCallActive] = useState<boolean>(false);
  const [callDuration, setCallDuration] = useState<number>(0);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isTranscribing, setIsTranscribing] = useState<boolean>(false);
  const [isThinking, setIsThinking] = useState<boolean>(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState<boolean>(false);
  const [activeTool, setActiveTool] = useState<{ tool: string; args: any } | null>(null);

  const [sessionId, setSessionId] = useState<string>("");
  const [selectedLang, setSelectedLang] = useState<"auto" | "mr" | "en">("mr");
  const [messages, setMessages] = useState<MessageTurn[]>([]);
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [micMuted, setMicMuted] = useState<boolean>(false);
  const [autoSpeak, setAutoSpeak] = useState<boolean>(true);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedBlobsRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const callTimerRef = useRef<NodeJS.Timeout | null>(null);
  const audioChunksRef = useRef<BlobPart[]>([]);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking, activeTool]);

  // Generate session ID on mount
  useEffect(() => {
    setSessionId("sess_clinic_" + Math.random().toString(36).substring(2, 9));
  }, []);

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

  const playTTSAudio = useCallback(() => {
    if (audioChunksRef.current.length === 0) return;
    try {
      const blob = new Blob(audioChunksRef.current, { type: "audio/mpeg" });
      const url = URL.createObjectURL(blob);

      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
      }

      const audio = new Audio(url);
      currentAudioRef.current = audio;

      audio.onplay = () => setIsPlayingAudio(true);
      audio.onended = () => {
        setIsPlayingAudio(false);
        URL.revokeObjectURL(url);
      };
      audio.onerror = () => setIsPlayingAudio(false);

      audio.play().catch(() => setIsPlayingAudio(false));
    } catch {
      setIsPlayingAudio(false);
    }
  }, []);

  // WebSocket connection handler
  const connectWebSocket = useCallback(() => {
    if (!sessionId) return;
    const target = `${wsUrl.replace(/\/$/, "")}/ws/copilot/${sessionId}`;
    const ws = new WebSocket(target);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "stt_status") {
          setIsTranscribing(true);
        }

        if (data.type === "stt_error") {
          setIsTranscribing(false);
          if (data.error) {
            setMessages((prev) => [
              ...prev,
              {
                id: "stt_err_" + Date.now(),
                role: "assistant",
                text: `${data.error}`,
                timestamp: Date.now(),
              },
            ]);
          }
        }

        if (data.type === "transcription") {
          setIsTranscribing(false);
          setMessages((prev) => [
            ...prev,
            {
              id: data.id || "tx_" + Date.now(),
              role: "user",
              text: data.text,
              timestamp: Date.now(),
            },
          ]);
        }

        if (data.type === "agent_thinking") {
          setIsThinking(true);
        }

        if (data.type === "tool_call_start") {
          setActiveTool({ tool: data.tool, args: data.args });
        }

        if (data.type === "tool_call_result") {
          setActiveTool(null);
        }

        if (data.type === "agent_response") {
          setIsThinking(false);
          setActiveTool(null);
          setMessages((prev) => [
            ...prev,
            {
              id: "ai_" + Date.now(),
              role: "assistant",
              text: data.text,
              tools_used: data.tools_used,
              timestamp: Date.now(),
            },
          ]);
        }

        if (data.type === "audio_stream_start") {
          audioChunksRef.current = [];
        }

        if (data.type === "audio_stream_chunk" && data.data) {
          const chunk = base64ToUint8Array(data.data);
          audioChunksRef.current.push(chunk.buffer as ArrayBuffer);
        }

        if (data.type === "audio_stream_end") {
          if (autoSpeak) {
            playTTSAudio();
          }
        }
      } catch {
        // ignore raw
      }
    };

    wsRef.current = ws;
  }, [sessionId, wsUrl, autoSpeak, playTTSAudio]);

  const startMicRecording = useCallback(async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true },
      });
      streamRef.current = stream;
      setMediaStream(stream);

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/mp4";

      recordedBlobsRef.current = [];
      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          recordedBlobsRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        const fullBlob = new Blob(recordedBlobsRef.current, { type: mimeType });
        if (fullBlob.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          const reader = new FileReader();
          reader.onloadend = () => {
            const result = reader.result as string;
            const base64 = result.includes(",") ? result.split(",")[1] : result;
            if (wsRef.current?.readyState === WebSocket.OPEN) {
              wsRef.current.send(
                JSON.stringify({
                  type: "audio_end",
                  data: base64,
                  mime_type: mimeType,
                  language: selectedLang === "auto" ? undefined : selectedLang,
                  size: fullBlob.size,
                })
              );
            }
          };
          reader.readAsDataURL(fullBlob);
        } else if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(
            JSON.stringify({
              type: "audio_end",
              mime_type: mimeType,
              language: selectedLang === "auto" ? undefined : selectedLang,
              size: 0
            })
          );
        }

        if (streamRef.current) {
          streamRef.current.getTracks().forEach((t) => t.stop());
          streamRef.current = null;
        }
        setMediaStream(null);
      };

      recorder.start(100);
      setIsRecording(true);
    } catch (err) {
      console.error("Mic error:", err);
      setIsRecording(false);
    }
  }, [selectedLang]);

  const stopMicRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  const startCall = async () => {
    setIsOpen(true);
    setCallActive(true);
    setCallDuration(0);
    setMessages([]);
    connectWebSocket();

    // Call duration timer
    callTimerRef.current = setInterval(() => {
      setCallDuration((prev) => prev + 1);
    }, 1000);

    // Initial greeting from Sarah
    setTimeout(() => {
      setMessages([
        {
          id: "greet_1",
          role: "assistant",
          text: "Hello and thank you for calling Apex Dental & Wellness Care! My name is Sarah, your AI receptionist. Are you calling to book an appointment, check treatment pricing, or check doctor availability?",
          timestamp: Date.now(),
        },
      ]);
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: "test_tts",
            text: "Hello and thank you for calling Apex Dental & Wellness Care! My name is Sarah, your AI receptionist. Are you calling to book an appointment, check treatment pricing, or check doctor availability?",
          })
        );
      }
    }, 800);
  };

  const endCall = () => {
    stopMicRecording();
    if (callTimerRef.current) {
      clearInterval(callTimerRef.current);
      callTimerRef.current = null;
    }
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setCallActive(false);
    setIsPlayingAudio(false);
    setIsThinking(false);
    setActiveTool(null);
  };

  const sendQuickText = (text: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "user_text", text }));
  };

  const formatTimer = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <>
      {/* Floating Bottom-Right Trigger Button (Collapsed) */}
      {!isOpen && (
        <div className="fixed bottom-6 right-6 z-50">
          <button
            onClick={() => {
              setIsOpen(true);
              startCall();
            }}
            className="group relative flex items-center gap-3 px-5 py-3.5 rounded-full bg-gradient-to-r from-teal-500 via-cyan-600 to-blue-600 text-white font-semibold text-sm shadow-2xl shadow-cyan-500/30 hover:shadow-cyan-500/50 hover:scale-105 transition-all duration-300 ring-2 ring-cyan-400/40"
          >
            <div className="relative">
              <span className="absolute -top-1 -right-1 flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500" />
              </span>
              <div className="h-8 w-8 rounded-full bg-white/20 flex items-center justify-center">
                <Phone className="h-4 w-4 text-white" />
              </div>
            </div>
            <div className="text-left">
              <div className="text-xs font-bold leading-tight flex items-center gap-1.5">
                <span>Call AI Receptionist</span>
                <Sparkles className="h-3 w-3 text-amber-300 animate-pulse" />
              </div>
              <div className="text-[10px] text-cyan-100 font-normal">Sarah • मराठी / English Voice</div>
            </div>
          </button>
        </div>
      )}

      {/* Expanded Call Modal Window */}
      {isOpen && (
        <div className="fixed bottom-5 right-5 z-50 w-full max-w-sm sm:max-w-md h-[620px] rounded-3xl border border-slate-700/80 bg-[#0c1322] shadow-[0_20px_60px_rgba(0,0,0,0.8)] flex flex-col overflow-hidden animate-fadeIn backdrop-blur-xl">
          {/* Call Header */}
          <div className="p-4 bg-gradient-to-r from-[#0d1b2a] via-[#102a43] to-[#0d1b2a] border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="h-11 w-11 rounded-2xl bg-gradient-to-tr from-cyan-500 to-teal-500 flex items-center justify-center text-white shadow-md shadow-cyan-500/20">
                  <Bot className="h-6 w-6" />
                </div>
                <span
                  className={`absolute -bottom-1 -right-1 h-3.5 w-3.5 rounded-full border-2 border-[#0c1322] ${
                    callActive ? "bg-emerald-500" : "bg-slate-500"
                  }`}
                />
              </div>
              <div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <h3 className="text-sm font-bold text-white">Sarah Vance</h3>
                  <span className="px-1.5 py-0.2 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-[10px] font-semibold">
                    AI Dental Receptionist
                  </span>
                  <button
                    onClick={() =>
                      setSelectedLang((prev) =>
                        prev === "mr" ? "en" : prev === "en" ? "auto" : "mr"
                      )
                    }
                    className="px-2 py-0.5 rounded-full bg-gradient-to-r from-orange-500/20 via-amber-500/20 to-teal-500/20 text-amber-300 border border-amber-500/40 text-[10px] font-medium hover:bg-amber-500/30 transition-all flex items-center gap-1 cursor-pointer"
                    title="Toggle Language: Auto, Marathi, English"
                  >
                    <span>🗣️</span>
                    <span>
                      {selectedLang === "mr"
                        ? "मराठी Voice"
                        : selectedLang === "en"
                        ? "English Voice"
                        : "मराठी / English"}
                    </span>
                  </button>
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <p className="text-[11px] text-slate-400 font-mono">
                    साई स्माईल डेंटल क्लिनिक • {formatTimer(callDuration)}
                  </p>
                  <span className="text-[9px] text-emerald-300 bg-emerald-950/80 px-1.5 py-0.5 rounded border border-emerald-800/40 font-medium">
                    मराठी / English Voice Supported
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => setAutoSpeak(!autoSpeak)}
                className={`p-2 rounded-xl border transition-colors ${
                  autoSpeak
                    ? "bg-slate-800 border-slate-700 text-cyan-400"
                    : "bg-slate-900 border-slate-800 text-slate-500"
                }`}
                title={autoSpeak ? "Mute Voice Output" : "Enable Voice Output"}
              >
                {autoSpeak ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
              </button>
              <button
                onClick={() => {
                  endCall();
                  setIsOpen(false);
                }}
                className="p-2 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition-colors"
                title="Minimize widget"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* Active Speaking / Listening Banner */}
          <div className="px-4 py-2 bg-slate-950/60 border-b border-slate-800/80 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span
                className={`h-2 w-2 rounded-full ${
                  isPlayingAudio
                    ? "bg-emerald-400 animate-ping"
                    : isRecording
                    ? "bg-rose-500 animate-ping"
                    : isThinking
                    ? "bg-purple-400 animate-spin"
                    : "bg-cyan-500"
                }`}
              />
              <span className="font-medium text-slate-300">
                {isPlayingAudio
                  ? "Sarah is speaking..."
                  : isRecording
                  ? "Listening to your voice..."
                  : isThinking
                  ? "Checking clinic records..."
                  : "Ready • Speak or click prompts"}
              </span>
            </div>

            {isPlayingAudio && (
              <div className="flex items-center gap-0.5">
                <span className="w-1 bg-emerald-400 h-3 animate-bounce" />
                <span className="w-1 bg-cyan-400 h-4 animate-bounce delay-75" />
                <span className="w-1 bg-teal-400 h-2 animate-bounce delay-150" />
              </div>
            )}
          </div>

          {/* Waveform Visualizer Canvas */}
          <div className="p-3 bg-[#080d18] border-b border-slate-800/60">
            <AudioWaveform isRecording={isRecording} stream={mediaStream} />
          </div>

          {/* Live Conversation Stream */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-[#070b14]/90 text-xs">
            {messages.map((m) => {
              const isAi = m.role === "assistant";
              return (
                <div
                  key={m.id}
                  className={`flex flex-col gap-1.5 ${isAi ? "items-start" : "items-end"}`}
                >
                  <div className="flex items-center gap-1.5 text-[10px] text-slate-500 px-1">
                    {isAi ? (
                      <>
                        <Bot className="h-3 w-3 text-cyan-400" />
                        <span>Sarah</span>
                      </>
                    ) : (
                      <>
                        <span>You</span>
                        <User className="h-3 w-3 text-teal-400" />
                      </>
                    )}
                  </div>

                  <div
                    className={`max-w-[85%] p-3 rounded-2xl leading-relaxed text-xs shadow-md ${
                      isAi
                        ? "bg-[#111c33] text-slate-100 border border-slate-800 rounded-tl-sm"
                        : "bg-gradient-to-r from-teal-600 to-cyan-600 text-white rounded-tr-sm"
                    }`}
                  >
                    {m.text}

                    {/* Tool Badges */}
                    {m.tools_used && m.tools_used.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-800/80 space-y-1">
                        {m.tools_used.map((t, idx) => (
                          <div
                            key={idx}
                            className="p-1.5 rounded-lg bg-black/40 border border-cyan-500/20 text-[10px] font-mono text-cyan-300 flex items-center gap-1.5"
                          >
                            <CheckCircle2 className="h-3 w-3 text-emerald-400 shrink-0" />
                            <span>Executed: {t.tool}()</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* In-Flight Tool Badge */}
            {activeTool && (
              <div className="p-3 rounded-xl bg-purple-950/30 border border-purple-800/40 text-purple-300 flex items-center gap-2 animate-pulse">
                <Wrench className="h-4 w-4 animate-spin text-purple-400" />
                <span>Accessing Clinic Database: {activeTool.tool}()...</span>
              </div>
            )}

            {/* In-Flight Thinking */}
            {isThinking && !activeTool && (
              <div className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-900/60 border border-slate-800 text-slate-400 italic">
                <Sparkles className="h-3.5 w-3.5 text-cyan-400 animate-spin" />
                <span>Sarah is checking clinic schedule...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick Prompt Chips */}
          <div className="p-2.5 bg-[#090f1d] border-t border-slate-800/80 flex items-center gap-1.5 overflow-x-auto text-[11px]">
            {/* Marathi Quick Prompts */}
            <button
              onClick={() => sendQuickText("दांत तपासणी आणि क्लीनिंग फी किती आहे?")}
              className="px-2.5 py-1 rounded-full bg-orange-950/40 hover:bg-orange-900/60 text-amber-200 hover:text-amber-100 shrink-0 border border-orange-700/50 transition-colors flex items-center gap-1 font-medium"
            >
              <span>🦷</span>
              <span>दांत तपासणी फी? (Cleaning Cost)</span>
            </button>
            <button
              onClick={() => sendQuickText("उद्या डॉक्टर उपलब्ध आहेत का? कोणत्या वेळा मोकळ्या आहेत?")}
              className="px-2.5 py-1 rounded-full bg-teal-950/40 hover:bg-teal-900/60 text-teal-200 hover:text-teal-100 shrink-0 border border-teal-700/50 transition-colors flex items-center gap-1 font-medium"
            >
              <span>📅</span>
              <span>उद्या वेळ मिळेल का? (Slots Tomorrow)</span>
            </button>
            <button
              onClick={() => sendQuickText("कृपया राहुल पाटील यांच्यासाठी उद्या दुपारी २ वाजता दात तपासणीची अपॉइंटमेंट बुक करा, फोन 9822012345.")}
              className="px-2.5 py-1 rounded-full bg-emerald-950/40 hover:bg-emerald-900/60 text-emerald-200 hover:text-emerald-100 shrink-0 border border-emerald-700/50 transition-colors flex items-center gap-1 font-medium"
            >
              <span>✨</span>
              <span>अपॉइंटमेंट बुक करा (Book Visit)</span>
            </button>
            {/* English Quick Prompts */}
            <button
              onClick={() => sendQuickText("What is the cost of teeth whitening?")}
              className="px-2.5 py-1 rounded-full bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-cyan-300 shrink-0 border border-slate-700/60 transition-colors"
            >
              💎 Whitening Cost?
            </button>
          </div>

          {/* Main Call Action Footer */}
          <div className="p-4 bg-[#0a101f] border-t border-slate-800 flex items-center justify-between gap-3">
            {/* Push to speak / Toggle mic button */}
            <button
              onClick={() => {
                if (isRecording) {
                  stopMicRecording();
                } else {
                  startMicRecording();
                }
              }}
              className={`flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-2xl font-bold text-xs transition-all shadow-lg ${
                isRecording
                  ? "bg-rose-600 hover:bg-rose-500 text-white ring-4 ring-rose-500/30 animate-pulse"
                  : isTranscribing
                  ? "bg-slate-800 text-amber-300"
                  : "bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white shadow-cyan-600/20"
              }`}
            >
              {isRecording ? (
                <>
                  <MicOff className="h-4 w-4" />
                  <span>Release to Send Voice</span>
                </>
              ) : isTranscribing ? (
                <span>Transcribing Voice...</span>
              ) : (
                <>
                  <Mic className="h-4 w-4" />
                  <span>Click to Speak to Sarah</span>
                </>
              )}
            </button>

            {/* End Call Button */}
            <button
              onClick={() => {
                endCall();
                setIsOpen(false);
              }}
              className="p-3 rounded-2xl bg-rose-600/20 hover:bg-rose-600/30 text-rose-400 border border-rose-500/40 transition-colors"
              title="End Phone Call"
            >
              <PhoneOff className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
