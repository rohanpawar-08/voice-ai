"use client";

import { useState } from "react";
import {
  MessageSquare,
  Clock,
  Zap,
  Copy,
  Check,
  Trash2,
  User,
  Sparkles,
  AlertCircle,
  Bot,
  Wrench,
  ChevronDown,
  ChevronUp,
  Send,
  Loader2,
} from "lucide-react";

export interface ToolExecution {
  tool: string;
  call_id?: string;
  args?: any;
  output?: any;
}

export interface TranscriptItem {
  id: string;
  session_id?: string;
  text: string;
  role?: "user" | "assistant";
  latency_ms?: number;
  audio_bytes?: number;
  timestamp: number | string;
  model?: string;
  is_demo?: boolean;
  tools_used?: ToolExecution[];
}

interface TranscriptFeedProps {
  transcripts: TranscriptItem[];
  isTranscribing: boolean;
  isAgentThinking: boolean;
  activeToolCall: { tool: string; args: any } | null;
  onClear: () => void;
  onSendText?: (text: string) => void;
}

export default function TranscriptFeed({
  transcripts,
  isTranscribing,
  isAgentThinking,
  activeToolCall,
  onClear,
  onSendText,
}: TranscriptFeedProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});
  const [inputText, setInputText] = useState<string>("");

  const copyText = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const toggleToolExpand = (id: string) => {
    setExpandedTools((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const formatTimestamp = (ts: number | string) => {
    if (typeof ts === "number") {
      const d = new Date(ts * 1000);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    }
    return String(ts);
  };

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    onSendText?.(inputText.trim());
    setInputText("");
  };

  const handleChipClick = (prompt: string) => {
    onSendText?.(prompt);
  };

  return (
    <div className="flex flex-col h-[560px] rounded-2xl border border-slate-800 bg-[#0a0f1d] shadow-2xl overflow-hidden">
      {/* Panel Header */}
      <div className="bg-[#0f172a] border-b border-slate-800 px-5 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-lg bg-gradient-to-tr from-cyan-500/20 to-purple-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
            <MessageSquare className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold tracking-wider uppercase text-slate-200">
              Live Multimodal Conversation
            </h3>
            <span className="text-[11px] text-slate-400">
              Voice STT + LangGraph Agent with MCP Tools
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 text-xs font-mono bg-slate-800 text-slate-300 rounded-full border border-slate-700">
            {transcripts.length} {transcripts.length === 1 ? "turn" : "turns"}
          </span>
          {transcripts.length > 0 && (
            <button
              onClick={onClear}
              className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800/80 rounded-lg transition-colors"
              title="Clear transcript & session context"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Panel Body: Chat Stream */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-[#070b14]/70">
        {transcripts.length === 0 && !isTranscribing && !isAgentThinking && !activeToolCall ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500">
            <div className="h-12 w-12 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center mb-3 text-cyan-400">
              <Bot className="h-6 w-6" />
            </div>
            <p className="text-sm font-medium text-slate-400 mb-1">Conversation is ready</p>
            <p className="text-xs text-slate-500 max-w-sm mb-4">
              Speak via microphone or use quick prompts below to trigger LangGraph agent reasoning and MCP tools.
            </p>

            <div className="flex flex-wrap gap-2 justify-center max-w-md">
              <button
                onClick={() => handleChipClick("What is my account balance for ACC-8899?")}
                className="px-2.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-cyan-400 transition-colors"
              >
                💳 Check balance (ACC-8899)
              </button>
              <button
                onClick={() => handleChipClick("Track my delivery for order ORD-4421")}
                className="px-2.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-amber-400 transition-colors"
              >
                📦 Track order (ORD-4421)
              </button>
              <button
                onClick={() => handleChipClick("Run system diagnostics on redis")}
                className="px-2.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-emerald-400 transition-colors"
              >
                ⚙️ System diagnostics (redis)
              </button>
            </div>
          </div>
        ) : (
          <>
            {transcripts.map((item) => {
              const isAssistant = item.role === "assistant";
              return (
                <div
                  key={item.id}
                  className={`group relative flex flex-col gap-2.5 p-4 rounded-2xl border transition-all shadow-md ${
                    isAssistant
                      ? "bg-[#11192e]/90 border-purple-900/30 hover:border-purple-800/50"
                      : "bg-[#0f172a]/90 border-slate-800 hover:border-slate-700/80"
                  }`}
                >
                  {/* Bubble Header */}
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <div className="flex items-center gap-2">
                      {isAssistant ? (
                        <span className="h-6 w-6 rounded-full bg-gradient-to-tr from-purple-600 to-indigo-600 text-white flex items-center justify-center font-bold text-[11px] shadow-sm shadow-purple-500/20">
                          <Bot className="h-3.5 w-3.5" />
                        </span>
                      ) : (
                        <span className="h-6 w-6 rounded-full bg-cyan-500/20 text-cyan-300 flex items-center justify-center font-bold text-[11px] border border-cyan-500/40">
                          <User className="h-3.5 w-3.5" />
                        </span>
                      )}

                      <span className="font-semibold text-slate-200">
                        {isAssistant ? "AI Copilot" : "User Voice"}
                      </span>

                      <span className="text-[11px] text-slate-500 flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatTimestamp(item.timestamp)}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      {/* Latency Pill */}
                      {item.latency_ms !== undefined && (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-800/80">
                          <Zap className="h-3 w-3" />
                          {item.latency_ms} ms
                        </span>
                      )}

                      {/* Model badge */}
                      {item.model && (
                        <span className="hidden sm:inline px-1.5 py-0.5 rounded bg-slate-800/80 text-[10px] font-mono text-slate-400 border border-slate-700/60">
                          {item.model}
                        </span>
                      )}

                      {/* Copy Button */}
                      <button
                        onClick={() => copyText(item.id, item.text)}
                        className="p-1 text-slate-400 hover:text-cyan-300 rounded transition-colors"
                        title="Copy text"
                      >
                        {copiedId === item.id ? (
                          <Check className="h-3.5 w-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Tool execution badge(s) if assistant used tools */}
                  {isAssistant && item.tools_used && item.tools_used.length > 0 && (
                    <div className="pl-8 space-y-1.5">
                      {item.tools_used.map((toolCall, idx) => {
                        const expandKey = `${item.id}_${idx}`;
                        const isExpanded = expandedTools[expandKey];
                        return (
                          <div
                            key={idx}
                            className="rounded-xl border border-purple-800/40 bg-purple-950/20 text-xs overflow-hidden"
                          >
                            <button
                              onClick={() => toggleToolExpand(expandKey)}
                              className="w-full flex items-center justify-between px-3 py-1.5 text-purple-300 hover:bg-purple-900/20 transition-colors"
                            >
                              <span className="flex items-center gap-1.5 font-mono font-semibold text-[11px]">
                                <Wrench className="h-3 w-3 text-purple-400" />
                                Tool Executed: {toolCall.tool}()
                              </span>
                              <span className="text-[10px] text-purple-400 flex items-center gap-1">
                                {isExpanded ? "Collapse" : "Inspect Result"}
                                {isExpanded ? (
                                  <ChevronUp className="h-3 w-3" />
                                ) : (
                                  <ChevronDown className="h-3 w-3" />
                                )}
                              </span>
                            </button>

                            {isExpanded && (
                              <div className="p-2.5 bg-black/40 border-t border-purple-800/30 font-mono text-[11px] text-slate-300 overflow-x-auto">
                                <pre>{JSON.stringify(toolCall.output, null, 2)}</pre>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Transcribed Speech / Assistant Body */}
                  <div className="text-sm font-medium text-slate-100 pl-8 leading-relaxed whitespace-pre-wrap">
                    {item.text}
                  </div>

                  {/* Footnote / Demo indicator */}
                  {item.is_demo && (
                    <div className="mt-1 pl-8 flex items-center gap-1.5 text-[11px] text-amber-400/90 font-mono">
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                      <span>Demo mode: set GROQ_API_KEY in backend/.env for production Whisper</span>
                    </div>
                  )}
                </div>
              );
            })}

            {/* In-Flight Transcribing Skeleton */}
            {isTranscribing && (
              <div className="flex flex-col gap-2 p-4 rounded-2xl bg-amber-950/15 border border-amber-900/40 animate-pulse">
                <div className="flex items-center justify-between text-xs text-amber-400">
                  <div className="flex items-center gap-2">
                    <span className="h-6 w-6 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center text-[11px]">
                      <Sparkles className="h-3.5 w-3.5 animate-spin" />
                    </span>
                    <span className="font-semibold">Transcribing Voice Stream...</span>
                  </div>
                  <span className="text-[11px] font-mono text-amber-400/80">Groq Whisper Engine</span>
                </div>
                <div className="pl-8 space-y-1.5 pt-1">
                  <div className="h-3 bg-amber-500/20 rounded w-3/4 animate-pulse" />
                  <div className="h-3 bg-amber-500/10 rounded w-1/2 animate-pulse" />
                </div>
              </div>
            )}

            {/* In-Flight Tool Calling Badge */}
            {activeToolCall && (
              <div className="flex items-center gap-3 p-3.5 rounded-2xl bg-gradient-to-r from-purple-950/40 to-blue-950/40 border border-purple-600/40 shadow-lg shadow-purple-900/20 animate-pulse">
                <div className="h-7 w-7 rounded-xl bg-purple-500/20 flex items-center justify-center text-purple-400">
                  <Wrench className="h-4 w-4 animate-spin" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-purple-300 font-mono">
                      Executing MCP Tool: {activeToolCall.tool}()
                    </span>
                    <span className="px-1.5 py-0.2 bg-purple-500/20 rounded text-[10px] text-purple-300 font-mono">
                      Live
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono">
                    Arguments: {JSON.stringify(activeToolCall.args)}
                  </div>
                </div>
              </div>
            )}

            {/* In-Flight Agent Thinking Indicator */}
            {isAgentThinking && !activeToolCall && (
              <div className="flex items-center gap-2.5 p-3.5 rounded-2xl bg-indigo-950/20 border border-indigo-800/40 text-xs text-indigo-300 animate-pulse">
                <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
                <span className="font-medium">LangGraph Agent is reasoning and formulating response...</span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Quick Prompt Chips & Text Input Bar */}
      <div className="bg-[#0c1222] border-t border-slate-800/80 p-3 space-y-2">
        {/* Quick action chips */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 text-[11px]">
          <span className="text-slate-500 font-mono shrink-0">Try:</span>
          <button
            type="button"
            onClick={() => handleChipClick("Check account balance for ACC-9981")}
            className="px-2 py-0.5 rounded-md bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-cyan-400 shrink-0 transition-colors"
          >
            Balance: ACC-9981
          </button>
          <button
            type="button"
            onClick={() => handleChipClick("What is the status of order ORD-7721?")}
            className="px-2 py-0.5 rounded-md bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-amber-400 shrink-0 transition-colors"
          >
            Order: ORD-7721
          </button>
          <button
            type="button"
            onClick={() => handleChipClick("Launch system control on redis")}
            className="px-2 py-0.5 rounded-md bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-emerald-400 shrink-0 transition-colors"
          >
            System: redis
          </button>
        </div>

        {/* Text Input Form */}
        <form onSubmit={handleSend} className="flex gap-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type a query or speak via microphone above..."
            className="flex-1 px-3 py-2 bg-slate-950/80 border border-slate-800 rounded-xl text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500 transition-colors"
          />
          <button
            type="submit"
            disabled={!inputText.trim()}
            className="px-3 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 text-white font-medium text-xs transition-all disabled:opacity-40 flex items-center gap-1"
          >
            <Send className="h-3.5 w-3.5" />
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
