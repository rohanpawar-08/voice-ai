"use client";

import { useEffect, useRef } from "react";

interface AudioWaveformProps {
  isRecording: boolean;
  stream: MediaStream | null;
}

export default function AudioWaveform({ isRecording, stream }: AudioWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);

  useEffect(() => {
    if (!stream || !isRecording) {
      // Clean up audio context if stream ends
      if (sourceRef.current) {
        sourceRef.current.disconnect();
        sourceRef.current = null;
      }
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close().catch(() => {});
        audioContextRef.current = null;
      }
      analyserRef.current = null;
      return;
    }

    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const ctx = new AudioContextClass();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      analyser.smoothingTimeConstant = 0.8;

      const source = ctx.createMediaStreamSource(stream);
      source.connect(analyser);

      audioContextRef.current = ctx;
      analyserRef.current = analyser;
      sourceRef.current = source;
    } catch (err) {
      console.error("Failed to initialize Web Audio API Analyser:", err);
    }

    return () => {
      if (sourceRef.current) {
        sourceRef.current.disconnect();
        sourceRef.current = null;
      }
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close().catch(() => {});
        audioContextRef.current = null;
      }
    };
  }, [stream, isRecording]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let phase = 0;

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      if (isRecording && analyserRef.current) {
        const bufferLength = analyserRef.current.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        analyserRef.current.getByteFrequencyData(dataArray);

        // Draw dynamic neon audio frequency bars
        const barCount = 28;
        const barWidth = 4;
        const gap = (width - barCount * barWidth) / (barCount + 1);

        for (let i = 0; i < barCount; i++) {
          const dataIndex = Math.floor((i / barCount) * bufferLength);
          const value = dataArray[dataIndex] || 0;
          const percent = value / 255;
          const barHeight = Math.max(4, percent * (height - 8));

          const x = gap + i * (barWidth + gap);
          const y = (height - barHeight) / 2;

          // Vibrant gradient from cyan to emerald to rose on peak
          const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
          gradient.addColorStop(0, percent > 0.8 ? "#f43f5e" : "#06b6d4");
          gradient.addColorStop(0.5, "#10b981");
          gradient.addColorStop(1, "#3b82f6");

          ctx.fillStyle = gradient;
          ctx.beginPath();
          ctx.roundRect(x, y, barWidth, barHeight, 2);
          ctx.fill();
        }
      } else {
        // Idle state: draw a gentle smooth animated resting sine wave
        phase += 0.04;
        ctx.beginPath();
        ctx.strokeStyle = "rgba(71, 85, 105, 0.45)";
        ctx.lineWidth = 2;

        const sliceWidth = width / 60;
        let x = 0;

        for (let i = 0; i <= 60; i++) {
          const y = height / 2 + Math.sin(i * 0.15 + phase) * 3;
          if (i === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
          x += sliceWidth;
        }
        ctx.stroke();
      }

      animationFrameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isRecording]);

  return (
    <div className="w-full flex items-center justify-center p-2 rounded-xl bg-slate-950/60 border border-slate-800/80">
      <canvas
        ref={canvasRef}
        width={340}
        height={48}
        className="w-full max-w-[340px] h-12 block"
      />
    </div>
  );
}
