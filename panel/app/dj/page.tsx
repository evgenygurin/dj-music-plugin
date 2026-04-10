"use client";

import { useState, useEffect, useMemo } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  IconPlayerPlayFilled,
  IconPlayerPauseFilled,
  IconPlayerSkipBackFilled,
  IconPlayerSkipForwardFilled,
  IconHeadphones,
  IconVinyl,
} from "@tabler/icons-react";

type DeckId = "A" | "B";

interface DeckState {
  title: string;
  artist: string;
  bpm: number;
  key: string;
  playing: boolean;
  position: number; // 0..100
  pitch: number; // -8..+8
  gain: number; // 0..100
  hi: number;
  mid: number;
  lo: number;
  filter: number; // -50..50
  cue: boolean;
}

const initial = (title: string, artist: string, bpm: number, key: string): DeckState => ({
  title,
  artist,
  bpm,
  key,
  playing: false,
  position: 0,
  pitch: 0,
  gain: 75,
  hi: 50,
  mid: 50,
  lo: 50,
  filter: 0,
  cue: false,
});

function Knob({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  color = "cyan",
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  color?: "cyan" | "magenta" | "amber" | "green";
}) {
  const pct = ((value - min) / (max - min)) * 100;
  const angle = -135 + (pct / 100) * 270;
  const colorMap = {
    cyan: "stroke-cyan-400 text-cyan-400",
    magenta: "stroke-fuchsia-500 text-fuchsia-500",
    amber: "stroke-amber-400 text-amber-400",
    green: "stroke-emerald-400 text-emerald-400",
  };
  return (
    <div className="flex flex-col items-center gap-1">
      <button
        type="button"
        onDoubleClick={() => onChange((min + max) / 2)}
        onWheel={(e) => {
          e.preventDefault();
          const step = (max - min) / 100;
          const next = Math.max(min, Math.min(max, value + (e.deltaY < 0 ? step : -step) * 2));
          onChange(next);
        }}
        className="relative h-12 w-12 rounded-full bg-zinc-900 border border-zinc-700 shadow-inner hover:border-zinc-500 transition"
      >
        <svg className="absolute inset-0" viewBox="0 0 48 48">
          <circle cx="24" cy="24" r="20" fill="none" stroke="#27272a" strokeWidth="3" />
          <circle
            cx="24"
            cy="24"
            r="20"
            fill="none"
            className={colorMap[color]}
            strokeWidth="3"
            strokeDasharray={`${(pct / 100) * 94} 999`}
            strokeDashoffset="0"
            transform="rotate(135 24 24)"
            strokeLinecap="round"
          />
        </svg>
        <div
          className="absolute top-1/2 left-1/2 h-4 w-0.5 bg-white origin-bottom"
          style={{ transform: `translate(-50%, -100%) rotate(${angle}deg)` }}
        />
      </button>
      <span className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</span>
    </div>
  );
}

function Vinyl({ playing, deckId }: { playing: boolean; deckId: DeckId }) {
  const accent = deckId === "A" ? "ring-emerald-400/60" : "ring-cyan-400/60";
  return (
    <div
      className={cn(
        "relative aspect-square w-full max-w-[260px] mx-auto rounded-full bg-black ring-2 shadow-2xl",
        accent,
        playing && "animate-[spin_3s_linear_infinite]"
      )}
    >
      <div className="absolute inset-2 rounded-full border border-zinc-800" />
      <div className="absolute inset-6 rounded-full border border-zinc-800" />
      <div className="absolute inset-10 rounded-full border border-zinc-800" />
      <div
        className={cn(
          "absolute inset-[38%] rounded-full flex items-center justify-center text-[10px] font-bold",
          deckId === "A" ? "bg-emerald-500 text-black" : "bg-cyan-500 text-black"
        )}
      >
        {deckId}
      </div>
      <div className="absolute top-1/2 left-1/2 h-1 w-1 rounded-full bg-white -translate-x-1/2 -translate-y-1/2" />
    </div>
  );
}

function Deck({
  id,
  state,
  setState,
}: {
  id: DeckId;
  state: DeckState;
  setState: (s: DeckState) => void;
}) {
  const accent = id === "A" ? "text-emerald-400" : "text-cyan-400";
  const accentBg = id === "A" ? "bg-emerald-500" : "bg-cyan-500";
  const knobColor = id === "A" ? "green" : "cyan";

  // waveform bars — deterministic mock pattern (id-seeded LCG). Held
  // in useMemo (not useRef) so the React Compiler sees a pure value
  // instead of a mutable .current access during render. Switch to
  // real WaveSurfer peaks when /api/audio/[id]/peaks is wired up.
  const bars = useMemo<number[]>(
    () =>
      Array.from({ length: 80 }, (_, i) => {
        const seed = (id === "A" ? 1 : 2) * 1103515245 + i * 12345;
        return 0.3 + (((seed >>> 16) & 0xff) / 255) * 0.7;
      }),
    [id],
  );

  return (
    <Card className="bg-zinc-950/80 border-zinc-800 p-4 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={cn("h-6 w-6 rounded-sm flex items-center justify-center text-xs font-bold text-black", accentBg)}>
            {id}
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-semibold text-white">{state.title}</span>
            <span className="text-xs text-zinc-500">{state.artist}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <Badge variant="outline" className={cn("border-zinc-700 font-mono", accent)}>
            {(state.bpm * (1 + state.pitch / 100)).toFixed(2)} BPM
          </Badge>
          <Badge variant="outline" className="border-zinc-700 font-mono text-amber-400">
            {state.key}
          </Badge>
        </div>
      </div>

      {/* Vinyl */}
      <Vinyl playing={state.playing} deckId={id} />

      {/* Waveform */}
      <div className="relative h-16 bg-black/60 rounded border border-zinc-800 overflow-hidden">
        <div className="flex h-full items-center gap-[1px] px-1">
          {bars.map((h, i) => {
            const active = (i / bars.length) * 100 <= state.position;
            return (
              <div
                key={i}
                className={cn(
                  "flex-1 rounded-[1px]",
                  active ? accentBg : "bg-zinc-700"
                )}
                style={{ height: `${h * 100}%` }}
              />
            );
          })}
        </div>
        <div
          className="absolute top-0 bottom-0 w-[2px] bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)]"
          style={{ left: `${state.position}%` }}
        />
      </div>

      {/* Transport */}
      <div className="flex items-center justify-center gap-2">
        <Button
          size="icon"
          variant="outline"
          className="border-zinc-700 bg-zinc-900"
          onClick={() => setState({ ...state, position: 0 })}
        >
          <IconPlayerSkipBackFilled className="h-4 w-4" />
        </Button>
        <Button
          size="icon"
          variant={state.cue ? "default" : "outline"}
          className={cn("border-zinc-700", state.cue ? "bg-amber-500 text-black" : "bg-zinc-900")}
          onClick={() => setState({ ...state, cue: !state.cue })}
        >
          <IconHeadphones className="h-4 w-4" />
        </Button>
        <Button
          size="lg"
          className={cn("h-12 w-20 text-black font-bold", accentBg)}
          onClick={() => setState({ ...state, playing: !state.playing })}
        >
          {state.playing ? (
            <IconPlayerPauseFilled className="h-6 w-6" />
          ) : (
            <IconPlayerPlayFilled className="h-6 w-6" />
          )}
        </Button>
        <Button
          size="icon"
          variant="outline"
          className="border-zinc-700 bg-zinc-900"
          onClick={() => setState({ ...state, position: 100 })}
        >
          <IconPlayerSkipForwardFilled className="h-4 w-4" />
        </Button>
      </div>

      {/* EQ + Filter knobs */}
      <div className="grid grid-cols-4 gap-2 justify-items-center border-t border-zinc-800 pt-3">
        <Knob label="HI" value={state.hi} onChange={(v) => setState({ ...state, hi: v })} color={knobColor} />
        <Knob label="MID" value={state.mid} onChange={(v) => setState({ ...state, mid: v })} color={knobColor} />
        <Knob label="LO" value={state.lo} onChange={(v) => setState({ ...state, lo: v })} color={knobColor} />
        <Knob
          label="FILTER"
          value={state.filter}
          onChange={(v) => setState({ ...state, filter: v })}
          min={-50}
          max={50}
          color="magenta"
        />
      </div>

      {/* Pitch fader */}
      <div className="flex items-center gap-3">
        <span className="text-[10px] uppercase text-zinc-500 w-10">Pitch</span>
        <Slider
          value={[state.pitch]}
          min={-8}
          max={8}
          step={0.05}
          onValueChange={(v) => setState({ ...state, pitch: v[0] })}
          className="flex-1"
        />
        <span className={cn("text-xs font-mono w-12 text-right", accent)}>
          {state.pitch >= 0 ? "+" : ""}
          {state.pitch.toFixed(2)}%
        </span>
      </div>
    </Card>
  );
}

function Mixer({
  deckA,
  deckB,
  crossfader,
  setCrossfader,
  master,
  setMaster,
  setDeckA,
  setDeckB,
}: {
  deckA: DeckState;
  deckB: DeckState;
  crossfader: number;
  setCrossfader: (v: number) => void;
  master: number;
  setMaster: (v: number) => void;
  setDeckA: (s: DeckState) => void;
  setDeckB: (s: DeckState) => void;
}) {
  return (
    <Card className="bg-zinc-950/80 border-zinc-800 p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs uppercase tracking-widest text-zinc-400">Mixer</h3>
        <Badge variant="outline" className="border-zinc-700 font-mono text-fuchsia-400">
          MASTER {master}%
        </Badge>
      </div>

      {/* Channel faders */}
      <div className="grid grid-cols-2 gap-6 flex-1">
        {/* Channel A */}
        <div className="flex flex-col items-center gap-3">
          <Knob label="GAIN A" value={deckA.gain} onChange={(v) => setDeckA({ ...deckA, gain: v })} color="green" />
          <div className="relative h-48 w-8 bg-zinc-900 border border-zinc-800 rounded flex items-end justify-center">
            <div
              className="w-full bg-gradient-to-t from-emerald-500 to-emerald-300 rounded-b transition-all"
              style={{ height: `${deckA.gain * (1 - Math.max(0, (crossfader - 50) / 50))}%` }}
            />
          </div>
          <span className="text-[10px] text-emerald-400 font-mono">CH A</span>
        </div>

        {/* Channel B */}
        <div className="flex flex-col items-center gap-3">
          <Knob label="GAIN B" value={deckB.gain} onChange={(v) => setDeckB({ ...deckB, gain: v })} color="cyan" />
          <div className="relative h-48 w-8 bg-zinc-900 border border-zinc-800 rounded flex items-end justify-center">
            <div
              className="w-full bg-gradient-to-t from-cyan-500 to-cyan-300 rounded-b transition-all"
              style={{ height: `${deckB.gain * (1 - Math.max(0, (50 - crossfader) / 50))}%` }}
            />
          </div>
          <span className="text-[10px] text-cyan-400 font-mono">CH B</span>
        </div>
      </div>

      {/* Crossfader */}
      <div className="flex flex-col gap-2 border-t border-zinc-800 pt-3">
        <div className="flex justify-between text-[10px] font-mono">
          <span className="text-emerald-400">A</span>
          <span className="text-zinc-500 uppercase">Crossfader</span>
          <span className="text-cyan-400">B</span>
        </div>
        <Slider
          value={[crossfader]}
          min={0}
          max={100}
          step={1}
          onValueChange={(v) => setCrossfader(v[0])}
        />
      </div>

      {/* Master */}
      <div className="flex items-center gap-3">
        <span className="text-[10px] uppercase text-zinc-500 w-14">Master</span>
        <Slider
          value={[master]}
          min={0}
          max={100}
          step={1}
          onValueChange={(v) => setMaster(v[0])}
          className="flex-1"
        />
      </div>
    </Card>
  );
}

export default function DjConsolePage() {
  const [deckA, setDeckA] = useState<DeckState>(
    initial("Hypnotic Groove", "Amelie Lens", 132, "8A")
  );
  const [deckB, setDeckB] = useState<DeckState>(
    initial("Peak Time Drift", "FJAAK", 134, "9A")
  );
  const [crossfader, setCrossfader] = useState(50);
  const [master, setMaster] = useState(80);

  // animate playback position
  useEffect(() => {
    const id = setInterval(() => {
      setDeckA((s) => (s.playing ? { ...s, position: (s.position + 0.2) % 100 } : s));
      setDeckB((s) => (s.playing ? { ...s, position: (s.position + 0.2) % 100 } : s));
    }, 100);
    return () => clearInterval(id);
  }, []);

  const bpmMatch = Math.abs(deckA.bpm * (1 + deckA.pitch / 100) - deckB.bpm * (1 + deckB.pitch / 100));

  return (
    <div className="min-h-screen bg-gradient-to-b from-black via-zinc-950 to-black p-6">
      <div className="max-w-[1400px] mx-auto flex flex-col gap-4">
        {/* Header bar */}
        <div className="flex items-center justify-between bg-zinc-950/80 border border-zinc-800 rounded-lg px-4 py-3">
          <div className="flex items-center gap-3">
            <IconVinyl className="h-6 w-6 text-fuchsia-500" />
            <h1 className="text-lg font-bold tracking-wider text-white">DJ CONSOLE</h1>
            <Badge variant="outline" className="border-fuchsia-500/50 text-fuchsia-400">
              BEATPORT-STYLE
            </Badge>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="text-zinc-500">
              ΔBPM <span className={bpmMatch < 0.5 ? "text-emerald-400" : "text-amber-400"}>{bpmMatch.toFixed(2)}</span>
            </span>
            <span className="text-zinc-500">
              XFADE <span className="text-white">{crossfader}</span>
            </span>
          </div>
        </div>

        {/* Main layout: Deck A | Mixer | Deck B */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px_1fr] gap-4">
          <Deck id="A" state={deckA} setState={setDeckA} />
          <Mixer
            deckA={deckA}
            deckB={deckB}
            crossfader={crossfader}
            setCrossfader={setCrossfader}
            master={master}
            setMaster={setMaster}
            setDeckA={setDeckA}
            setDeckB={setDeckB}
          />
          <Deck id="B" state={deckB} setState={setDeckB} />
        </div>

        <p className="text-center text-[10px] text-zinc-600 uppercase tracking-widest">
          Scroll on knobs to change · Double-click to center · Click play to spin the vinyl
        </p>
      </div>
    </div>
  );
}
