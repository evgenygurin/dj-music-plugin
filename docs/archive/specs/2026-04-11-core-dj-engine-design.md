# Core DJ Engine — Design Spec

> Sub-project 1 of 6 for djay Pro AI clone implementation.

## Goal

Add real-time Loop, per-deck FX (Echo/Reverb/Filter), Beat Sync (phase lock), and functional crossfader to the existing dual-deck Web Audio engine. All audio processing happens in the browser via Web Audio API. MCP tools persist state only.

## Scope

| Feature | What it does | Implementation |
|---------|-------------|----------------|
| **Loop** | IN/OUT markers, auto-size (1/2/4/8/16 bars), loop active toggle | Web Audio: schedule `audio.currentTime` jump at loop end |
| **Echo FX** | Beat-synced delay with feedback + LPF | Web Audio: `DelayNode` + `GainNode` (feedback) + `BiquadFilterNode` (LPF) |
| **Reverb FX** | Convolution reverb with dry/wet mix | Web Audio: `ConvolverNode` + impulse response buffer + dry/wet `GainNode` |
| **Filter FX** | Lowpass/highpass sweep with resonance | Web Audio: `BiquadFilterNode` (already exists as `hp1/hp2`, extend to user-controllable) |
| **Beat Sync** | Phase-lock incoming track to master beat grid | Frontend: compute beat phase offset, adjust `playbackRate` + seek micro-correction |
| **Crossfader** | Volume balance between Deck A and Deck B | Frontend: equal-power crossfade via `GainNode` per deck, driven by slider |

## Out of scope (later sub-projects)

- Neural Mix / stem separation
- Sampler / performance pads
- Cue point persistence to DB
- Dual deck parallel waveform view
- 4 Decks mode
- Tempo editor UI

## Architecture

### Signal chain per deck (AFTER changes)

```text
source → preGain → (dryGain ‖ hp→wetGain) → sum → LOW → MID → HIGH → fxSend → gain → masterLimiter
                                                                         ↕
                                                                    fxReturn ← echoNode
                                                                             ← reverbNode
                                                                             ← filterNode (user)
```

New nodes per deck:
- `fxSend: GainNode` — taps signal before final gain
- `fxReturn: GainNode` — mixes FX back in (dry/wet)
- `echoDelay: DelayNode` — beat-synced delay time
- `echoFeedback: GainNode` — feedback loop (clamped ≤0.7)
- `echoLpf: BiquadFilterNode` — darkens repeats (3.5kHz lowpass)
- `reverbConvolver: ConvolverNode` — loaded with IR buffer
- `userFilter: BiquadFilterNode` — lowpass/highpass sweep

### Loop implementation

Loop uses `requestAnimationFrame` polling (already exists for position tracking). When loop is active and position exceeds `loopOutSec`, seek to `loopInSec`. Quantize to nearest downbeat using `firstDownbeatSec` from DB.

State:
```typescript
interface LoopState {
  active: boolean
  inSec: number | null    // loop start
  outSec: number | null   // loop end
  bars: number            // 1, 2, 4, 8, 16
}
```

Methods added to `AudioPlayerApi`:
```typescript
setLoopIn: () => void           // mark current position as loop IN
setLoopOut: () => void          // mark current position as loop OUT, activate
setLoopBars: (bars: number) => void  // auto-set loop from current position
toggleLoop: () => void          // activate/deactivate
loopState: LoopState            // read-only
```

### FX implementation

Each FX has: `enabled: boolean`, `wetMix: number` (0..1), `param: number` (effect-specific).

Methods added to `AudioPlayerApi`:
```typescript
setFxEnabled: (fx: 'echo' | 'reverb' | 'filter', enabled: boolean) => void
setFxWet: (fx: 'echo' | 'reverb' | 'filter', wet: number) => void
setFxParam: (fx: 'echo' | 'reverb' | 'filter', value: number) => void
fxState: { echo: FxSlot; reverb: FxSlot; filter: FxSlot }
```

Echo param = delay time in beats (1/16, 1/8, 1/4, 1/2, 1).
Reverb param = room size (small/medium/large IR).
Filter param = cutoff frequency (20..20000 Hz).

### Beat Sync

Uses existing `masterTempoBpm` and `firstDownbeatSec` from DB.

SYNC button behavior:
1. Lock incoming deck's `playbackRate` to match master BPM (already done)
2. Compute phase offset: `(currentTime - firstDownbeat) % beatDuration`
3. Apply micro-seek to align beats (±10ms correction)
4. Maintain lock during playback via periodic correction (every 4 bars)

Methods:
```typescript
syncEnabled: boolean
toggleSync: () => void
```

### Crossfader

Slider 0..1 maps to equal-power gain:
- Deck A gain = `cos(crossfader * π/2)`
- Deck B gain = `sin(crossfader * π/2)`

Applied to existing `gain` nodes on each deck.

Methods:
```typescript
crossfaderPosition: number  // 0..1
setCrossfaderPosition: (pos: number) => void
```

## MCP Tools (backend state persistence)

New tools in `app/controllers/tools/mixer.py`:

| Tool | Params | Purpose |
|------|--------|---------|
| `set_loop` | `deck_id, in_ms, out_ms, bars, active` | Persist loop state |
| `set_fx` | `deck_id, fx_type, enabled, wet, param` | Persist FX state |
| `set_sync` | `deck_id, enabled` | Persist sync state |
| `set_crossfader` | `position` | Already exists, just connect |

## UI Changes (`panel/app/page.tsx`)

### Loop panel (new tab ⟲)
- Auto/Saved/Bounce tabs (Auto only for now)
- Loop size selector: ⟲1 ⟲2 ⟲4 ⟲8 ⟲16
- IN / OUT buttons
- Active indicator (glow when loop is on)

### FX panel (enhance existing)
- Echo: ON toggle + delay time selector (1/16..1 beat) + D/W knob
- Reverb: ON toggle + D/W knob
- Filter: ON toggle + cutoff slider + resonance (Q)
- All connected to real Web Audio via `audio.setFxEnabled/setFxWet/setFxParam`

### Beat Sync
- Blue SYNC button already in bottom bar
- Connect to `audio.toggleSync()`
- Active state = blue bg when synced

### Crossfader
- Slider already in bottom bar
- Connect `onValueChange` to `audio.setCrossfaderPosition()`

## Files to modify

| File | Changes |
|------|---------|
| `audio-player-context.tsx` | Add FX nodes to `buildDeck`, loop state, sync logic, crossfader, new API methods |
| `page.tsx` | Connect Loop tab, FX panel, SYNC button, crossfader to new API |
| `app/engines/mixer/engine.py` | Add loop/fx/sync state |
| `app/controllers/tools/mixer.py` | Add `set_loop`, `set_fx`, `set_sync` tools |
| `app/schemas/mixer.py` | Add loop/fx/sync fields |

## Testing

- Play a track → activate Loop 4 bars → verify audio loops at correct beat boundary
- Enable Echo FX → hear beat-synced delay repeats
- Enable Reverb FX → hear reverb tail
- Move Filter cutoff → hear lowpass sweep
- Press SYNC → incoming track locks to master beat phase
- Move crossfader → volume shifts between decks

## Risks

1. **audio-player-context.tsx is 2200+ LOC** — adding FX nodes increases complexity. Mitigate: add FX as a separate `buildFxChain()` helper function.
2. **Loop timing precision** — `requestAnimationFrame` has ~16ms granularity. For techno at 128 BPM, one beat = 469ms, so 16ms jitter is 3.4% of a beat. Acceptable for auto-DJ, problematic for manual DJ. Mitigate: use `AudioContext.currentTime` for scheduling.
3. **Reverb IR loading** — ConvolverNode needs an impulse response buffer. Options: embed small IR as base64, or fetch from server. Recommend: embed 0.5s synthetic IR generated at startup.
4. **Crossfader conflicts with existing crossfade engine** — current auto-DJ crossfade uses gain envelopes directly. Crossfader must NOT interfere during active crossfade. Mitigate: crossfader only active when NOT crossfading.
