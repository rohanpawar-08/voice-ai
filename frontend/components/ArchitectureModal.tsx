"use client";

import { X, Layers, Cpu, Database, Volume2, Mic, Sparkles, Check, ArrowRight } from "lucide-react";

interface ArchitectureModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ArchitectureModal({ isOpen, onClose }: ArchitectureModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-3xl rounded-2xl border border-slate-700/80 bg-[#0c1222] p-6 shadow-2xl overflow-y-auto max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-5">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-cyan-500 via-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-lg shadow-indigo-500/20">
              <Layers className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">
                System Architecture & Full-Duplex Data Flow
              </h2>
              <p className="text-xs text-slate-400">
                End-to-End Multimodal Voice & Support Copilot Engine
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Data Flow Diagram Card */}
        <div className="space-y-4 mb-6">
          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 text-xs font-mono space-y-3">
            <div className="text-[11px] text-cyan-400 uppercase tracking-wider font-semibold">
              Live Pipeline Sequence
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-center">
              <div className="p-2.5 rounded-lg bg-cyan-950/30 border border-cyan-800/40 text-cyan-200">
                <Mic className="h-4 w-4 mx-auto mb-1 text-cyan-400" />
                <div className="font-bold text-[11px]">1. Mic Streaming</div>
                <div className="text-[10px] text-slate-400">16kHz audio blobs (250ms chunks)</div>
              </div>

              <div className="p-2.5 rounded-lg bg-blue-950/30 border border-blue-800/40 text-blue-200">
                <Cpu className="h-4 w-4 mx-auto mb-1 text-blue-400" />
                <div className="font-bold text-[11px]">2. Whisper STT</div>
                <div className="text-[10px] text-slate-400">Groq Whisper-large-v3 (sub-250ms)</div>
              </div>

              <div className="p-2.5 rounded-lg bg-purple-950/30 border border-purple-800/40 text-purple-200">
                <Sparkles className="h-4 w-4 mx-auto mb-1 text-purple-400" />
                <div className="font-bold text-[11px]">3. LangGraph & Tools</div>
                <div className="text-[10px] text-slate-400">Llama / GPT + MCP banking & orders</div>
              </div>

              <div className="p-2.5 rounded-lg bg-emerald-950/30 border border-emerald-800/40 text-emerald-200">
                <Volume2 className="h-4 w-4 mx-auto mb-1 text-emerald-400" />
                <div className="font-bold text-[11px]">4. Neural TTS</div>
                <div className="text-[10px] text-slate-400">Edge-TTS MP3 chunk auto-play</div>
              </div>
            </div>
          </div>

          {/* Architecture Pillars */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <h4 className="font-bold text-slate-200 mb-1 flex items-center gap-1.5">
                <Database className="h-3.5 w-3.5 text-red-400" />
                Redis State & Memory Cache
              </h4>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                Dockerized Redis stores multi-turn conversational history (<code className="text-cyan-300">copilot:session:messages</code>),
                last speech heartbeats, and round-trip telemetry with automated 24-hour TTL expiration.
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <h4 className="font-bold text-slate-200 mb-1 flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-purple-400" />
                LangGraph State Machine
              </h4>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                Features conditional routing between the agent reasoning node and executable MCP Python tools
                (<code className="text-purple-300">get_account_balance</code>, <code className="text-purple-300">check_order_status</code>, <code className="text-purple-300">system_control</code>).
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <h4 className="font-bold text-slate-200 mb-1 flex items-center gap-1.5">
                <Cpu className="h-3.5 w-3.5 text-cyan-400" />
                FastAPI Asynchronous WebSocket
              </h4>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                Fully asynchronous bidirectional WebSocket connection handling simultaneous audio chunk streaming,
                low-overhead ping-pong latency tracking, and tool execution lifecycle hooks.
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <h4 className="font-bold text-slate-200 mb-1 flex items-center gap-1.5">
                <Volume2 className="h-3.5 w-3.5 text-emerald-400" />
                Zero-Cost Neural Audio
              </h4>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                Uses Microsoft Edge Neural TTS (<code className="text-emerald-300">en-US-ChristopherNeural</code>) for
                crystal-clear, zero-subscription speech synthesis with chunked browser playback.
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-slate-800 pt-4 text-xs">
          <span className="text-slate-500 font-mono">100% Free & Open-Source Stack</span>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-medium transition-all"
          >
            Close Architecture Inspector
          </button>
        </div>
      </div>
    </div>
  );
}
