"use client";

import { useState, useRef, useEffect } from "react";
import { Terminal, ArrowUpRight, ArrowDownLeft, Trash2 } from "lucide-react";

export interface LogEntry {
  id: string;
  direction: "out" | "in" | "system";
  timestamp: string;
  type: string;
  payload: any;
  latencyMs?: number;
}

interface ConsoleLoggerProps {
  logs: LogEntry[];
  sessionId: string;
  onClear: () => void;
}

export default function ConsoleLogger({ logs, sessionId, onClear }: ConsoleLoggerProps) {
  const [filter, setFilter] = useState<"all" | "in" | "out">("all");
  const logsEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const filteredLogs = logs.filter((log) => {
    if (filter === "in") return log.direction === "in";
    if (filter === "out") return log.direction === "out";
    return true;
  });

  return (
    <div className="flex flex-col h-[520px] rounded-2xl border border-slate-800 bg-[#0a0f1d] shadow-2xl overflow-hidden">
      {/* Console Header */}
      <div className="bg-[#0f172a] border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-cyan-400" />
          <span className="text-xs font-semibold tracking-wider text-slate-300 uppercase">
            WebSocket Telemetry Console
          </span>
          <span className="px-1.5 py-0.5 text-[10px] font-mono bg-slate-800 text-slate-400 rounded">
            {filteredLogs.length} events
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Filter Pills */}
          <div className="flex bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-xs">
            <button
              onClick={() => setFilter("all")}
              className={`px-2 py-0.5 rounded transition-colors ${
                filter === "all" ? "bg-slate-700 text-white font-medium" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilter("out")}
              className={`px-2 py-0.5 rounded transition-colors ${
                filter === "out" ? "bg-slate-700 text-cyan-300 font-medium" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              TX
            </button>
            <button
              onClick={() => setFilter("in")}
              className={`px-2 py-0.5 rounded transition-colors ${
                filter === "in" ? "bg-slate-700 text-emerald-300 font-medium" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              RX
            </button>
          </div>

          <button
            onClick={onClear}
            className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800/80 rounded-lg transition-colors"
            title="Clear console"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Console Body */}
      <div className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-3 bg-[#070b14]/90">
        {filteredLogs.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-600 space-y-2">
            <Terminal className="h-8 w-8 text-slate-700" />
            <p>Console waiting for packets...</p>
            <p className="text-[11px] text-slate-600">Connect to WebSocket or speak to stream packets.</p>
          </div>
        ) : (
          filteredLogs.map((log) => (
            <div
              key={log.id}
              className={`p-3 rounded-xl border transition-all ${
                log.direction === "out"
                  ? "bg-cyan-950/15 border-cyan-900/40 text-cyan-200"
                  : log.direction === "in"
                  ? "bg-emerald-950/15 border-emerald-900/40 text-emerald-200"
                  : "bg-slate-900/60 border-slate-800 text-slate-300"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5 text-[11px]">
                <div className="flex items-center gap-2">
                  {log.direction === "out" ? (
                    <span className="flex items-center gap-1 font-semibold text-cyan-400 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-800/50">
                      <ArrowUpRight className="h-3 w-3" /> TX (Out)
                    </span>
                  ) : log.direction === "in" ? (
                    <span className="flex items-center gap-1 font-semibold text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/50">
                      <ArrowDownLeft className="h-3 w-3" /> RX (In)
                    </span>
                  ) : (
                    <span className="font-semibold text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
                      SYS
                    </span>
                  )}

                  <span className="font-bold text-white uppercase">{log.type}</span>
                </div>

                <div className="flex items-center gap-2 text-slate-500">
                  {log.latencyMs !== undefined && (
                    <span className="px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800 text-[10px] font-bold">
                      RTT: {log.latencyMs} ms
                    </span>
                  )}
                  <span>{log.timestamp}</span>
                </div>
              </div>

              <pre className="text-[11px] overflow-x-auto text-slate-300 bg-black/40 p-2.5 rounded-lg border border-slate-800/60 font-mono">
                {JSON.stringify(log.payload, null, 2)}
              </pre>
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>

      {/* Console Footer */}
      <div className="bg-[#0c1222] border-t border-slate-800/80 px-4 py-2 flex items-center justify-between text-[11px] text-slate-500 font-mono">
        <span>Protocol: WebSocket (JSON/Base64)</span>
        <span>Channel: /ws/copilot/{sessionId || ":id"}</span>
      </div>
    </div>
  );
}
