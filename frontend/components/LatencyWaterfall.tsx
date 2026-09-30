"use client";

import { useMemo } from "react";
import { Zap, Clock, Activity, Cpu, Volume2, Sparkles, CheckCircle2 } from "lucide-react";

export interface LatencyMetrics {
  stt_ms: number;
  llm_reasoning_ms: number;
  tts_first_chunk_ms?: number;
  tts_ms: number;
  total_e2e_ms: number;
  tools_count?: number;
}

interface LatencyWaterfallProps {
  metrics: LatencyMetrics | null;
  history?: LatencyMetrics[];
}

export default function LatencyWaterfall({ metrics, history = [] }: LatencyWaterfallProps) {
  // If no live telemetry yet, provide default benchmark values for visualization
  const current = useMemo<LatencyMetrics>(() => {
    if (metrics && metrics.total_e2e_ms > 0) {
      return metrics;
    }
    return {
      stt_ms: 185,
      llm_reasoning_ms: 320,
      tts_first_chunk_ms: 110,
      tts_ms: 215,
      total_e2e_ms: 720,
      tools_count: 1,
    };
  }, [metrics]);

  const isSimulated = !metrics || metrics.total_e2e_ms === 0;

  // Calculate percentages for the horizontal waterfall bar
  const total = Math.max(1, current.stt_ms + current.llm_reasoning_ms + current.tts_ms);
  const sttPct = Math.round((current.stt_ms / total) * 100);
  const llmPct = Math.round((current.llm_reasoning_ms / total) * 100);
  const ttsPct = Math.max(5, 100 - sttPct - llmPct);

  // Compute average from history if available
  const avgTotal = useMemo(() => {
    if (history.length === 0) return current.total_e2e_ms;
    const sum = history.reduce((acc, h) => acc + h.total_e2e_ms, 0);
    return Math.round(sum / history.length);
  }, [history, current.total_e2e_ms]);

  return (
    <div className="rounded-2xl border border-slate-800 bg-[#0e1626]/90 p-5 shadow-2xl backdrop-blur-md">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="h-6 w-6 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <Activity className="h-3.5 w-3.5" />
          </div>
          <div>
            <h3 className="text-xs font-bold tracking-wider uppercase text-slate-200">
              E2E Latency Waterfall Telemetry
            </h3>
            <span className="text-[11px] text-slate-400">
              Live breakdown across STT, LangGraph, and Neural TTS
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold flex items-center gap-1 ${
              current.total_e2e_ms <= 800
                ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800"
                : "bg-amber-950/80 text-amber-400 border border-amber-800"
            }`}
          >
            <Zap className="h-3 w-3" />
            {current.total_e2e_ms <= 800 ? "< 800ms Benchmark Met" : "Target: < 800ms"}
          </span>
          {isSimulated && (
            <span className="px-1.5 py-0.5 bg-slate-800 text-slate-400 text-[10px] font-mono rounded">
              Baseline
            </span>
          )}
        </div>
      </div>

      {/* Horizontal Waterfall Bar */}
      <div className="space-y-2 mb-4">
        <div className="h-6 w-full rounded-xl bg-slate-950/80 border border-slate-800/80 p-0.5 flex overflow-hidden">
          {/* STT Segment */}
          <div
            style={{ width: `${sttPct}%` }}
            className="h-full bg-gradient-to-r from-cyan-600 to-cyan-500 rounded-l-lg transition-all duration-500 flex items-center justify-center text-[10px] font-mono font-bold text-white shadow-sm overflow-hidden"
            title={`Whisper STT: ${current.stt_ms}ms (${sttPct}%)`}
          >
            {sttPct > 12 && <span>{current.stt_ms}ms</span>}
          </div>

          {/* LangGraph LLM & Tools Segment */}
          <div
            style={{ width: `${llmPct}%` }}
            className="h-full bg-gradient-to-r from-purple-600 to-indigo-600 transition-all duration-500 flex items-center justify-center text-[10px] font-mono font-bold text-white shadow-sm overflow-hidden"
            title={`LangGraph & Tools: ${current.llm_reasoning_ms}ms (${llmPct}%)`}
          >
            {llmPct > 12 && <span>{current.llm_reasoning_ms}ms</span>}
          </div>

          {/* TTS Segment */}
          <div
            style={{ width: `${ttsPct}%` }}
            className="h-full bg-gradient-to-r from-emerald-600 to-teal-500 rounded-r-lg transition-all duration-500 flex items-center justify-center text-[10px] font-mono font-bold text-white shadow-sm overflow-hidden"
            title={`Edge Neural TTS: ${current.tts_ms}ms (${ttsPct}%)`}
          >
            {ttsPct > 12 && <span>{current.tts_ms}ms</span>}
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 px-1">
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-cyan-400" />
            <span>STT (Whisper): {current.stt_ms}ms</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-purple-400" />
            <span>Reasoning (LangGraph): {current.llm_reasoning_ms}ms</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            <span>Speech (Edge-TTS): {current.tts_ms}ms</span>
          </div>
        </div>
      </div>

      {/* 4 Metrics Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {/* Metric 1: Total E2E Turnaround */}
        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
          <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Clock className="h-3 w-3 text-emerald-400" />
            Total E2E
          </div>
          <div className="text-xl font-bold font-mono text-white flex items-baseline gap-1">
            <span className={current.total_e2e_ms <= 800 ? "text-emerald-400" : "text-amber-400"}>
              {current.total_e2e_ms}
            </span>
            <span className="text-[10px] text-slate-500 font-normal">ms</span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono">
            Silence $\rightarrow$ Speech
          </span>
        </div>

        {/* Metric 2: STT Transcription */}
        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
          <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Cpu className="h-3 w-3 text-cyan-400" />
            Whisper STT
          </div>
          <div className="text-xl font-bold font-mono text-cyan-300 flex items-baseline gap-1">
            {current.stt_ms}
            <span className="text-[10px] text-slate-500 font-normal">ms</span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono">Groq v3 Large</span>
        </div>

        {/* Metric 3: LLM & Tools */}
        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
          <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Sparkles className="h-3 w-3 text-purple-400" />
            LangGraph Agent
          </div>
          <div className="text-xl font-bold font-mono text-purple-300 flex items-baseline gap-1">
            {current.llm_reasoning_ms}
            <span className="text-[10px] text-slate-500 font-normal">ms</span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono">
            {current.tools_count ? `${current.tools_count} tool call` : "Reasoning"}
          </span>
        </div>

        {/* Metric 4: TTS First Audio Byte */}
        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
          <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Volume2 className="h-3 w-3 text-emerald-400" />
            Time to 1st Byte
          </div>
          <div className="text-xl font-bold font-mono text-emerald-300 flex items-baseline gap-1">
            {current.tts_first_chunk_ms || current.tts_ms}
            <span className="text-[10px] text-slate-500 font-normal">ms</span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono">Neural Stream</span>
        </div>
      </div>
    </div>
  );
}
