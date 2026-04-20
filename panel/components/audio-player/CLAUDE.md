# Audio Player Context

Single-file Web Audio engine (`audio-player-context.tsx`, ~2000 LOC). Dual-deck crossfade, LUFS normalization, bass-kick kill, 6-style transition dispatch.

## Deck signal chain

```text
source → preGain → (dryGain ‖ hp1 → hp2 → wetGain) → sum → mid → high → gain → masterLimiter → destination
```

- `preGain` — LUFS-normalization offset (attenuate-only, set at fade start)
- `dryGain` / `wetGain` — bass-kick kill crossfader (LR4 HP @ 150 Hz default)
- `gain` — per-deck equal-power fade envelope
- `masterLimiter` — shared `DynamicsCompressorNode`, last safety before `ctx.destination`

## Style → backend mapping

6 backend styles → 4 runtime dispatchers (`startCrossfade`):

- `cut` → `cut`
- `bass_swap_short` / `bass_swap_long` → `swap`
- `echo_out` → `echo_out`
- `filter_sweep` → `filter_sweep`
- `long_blend` → `harmonic`
- fallback → `fade`

Manual chip group (MediumPlayerBar) exposes only `cut`/`swap`/`harmonic`/`fade` — `echo_out` и `filter_sweep` приходят только от backend scorer. `manualStyleRef.current` побеждает scorer (читается из ref, не state, т.к. dispatch внутри `.then()`).

## Gotchas

- **`RuntimeStyle` дублируется в 3 местах.** Расширяя список стилей, правь все три или TypeScript молча пропустит: (1) `AudioPlayerApi.lastResolvedStyle` ~line 166, (2) `useState<...>` ~line 261, (3) `type RuntimeStyle = ...` внутри `startCrossfade` ~line 866.
- **Per-style cleanup pattern.** Стили, создающие транзиентные Web Audio nodes (ECHO_OUT's DelayNode + feedback graph) или мутирующие deck state (FILTER_SWEEP's HP cutoff automation), **должны** пушить disposer в `extraCleanup: Array<() => void>` (declared near gain-envelope dispatch). Fade finaliser `setTimeout` дренирует его перед освобождением deck'а.
- **ECHO_OUT bypasses master limiter.** Feedback loop идёт `echoDelay → echoWet → ctx.destination` напрямую, не через `masterLimiter`. Safety держится на `feedback ≤ 0.55` и `wetCeiling ≤ 0.7 * vol`. Не поднимай без выделенного limiter на wet branch.
- **Fast Refresh.** Модуль экспортирует components AND hooks — добавлять type exports сюда нельзя (триггерит full reload). Типы живут в `audio-player-types.ts`; `PlayerTrackMeta` / `ManualTransitionStyle` импортируй оттуда, не реэкспортируй через этот файл.
- **`manualStyle` persistence.** `localStorage['dj.player.manualStyle']`, initial `'auto'` (SSR-safe), hydration в mount effect с `isValidManualStyle` type-guard. Обе стороны в try/catch (private-mode / quota). `manualStyle` и `setManualStyle` обязаны быть в `useMemo` deps объекта `api`.
