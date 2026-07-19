# Swallow Boy Voice Analysis

Date: 2026-07-18
Source set: `suno_out/rimjoba/gens_v20/*.mp3` (15 short takes)
Target: retarget voice lock from Taras-era control voice to `swallow boy`

## Executive Summary

Голос начал стабилизироваться между жанрами не из-за удачи, а из-за того, что
в prompt stack был найден устойчивый **voice-first template**:

1. voice descriptors шли **раньше жанра**
2. все эксперименты были **short-form**
3. модель v5.5 держала **один низкий мужской тембровый каркас**
4. genre tail менял бит и energy, но почти не трогал lead identity

Это и есть рабочая база для следующего шага под `swallow boy`.

## What Actually Caused Consistency

### 1. Fixed vocal DNA block

Самыми важными признаками оказались:

- `mid-baritone Russian rap MC`
- `deadpan delivery`
- `cold cocky swagger`
- `close-mic dry presence`
- `light autotune`
- `wide stereo ad-libs`
- `gang-chant hooks`
- `punchy consonants`

Ключевой вывод: Suno v5.5 очень сильно приоритизирует ранние vocal descriptors.
Пока эти слова стоят в начале style/tags, жанр меняется, но “кто читает” остаётся
более-менее тем же.

### 2. Short-form reduced character drift

Большинство take'ов длиной `5-15 s`. Это сильно ограничило модель:

- нет времени развернуть другой “character voice”
- нет длинных melodic bridges
- меньше риска уйти в поп-пение, хор или нового исполнителя

Вывод: для voice locking короткий формат оказался не компромиссом, а плюсом.

### 3. The successful takes form one acoustic cluster

По локальным измерениям (`/tmp/swallow_boy_existing_metrics.json`) удачные take'и
держатся в узком диапазоне:

- `f0 median`: чаще всего `70.0-90.3 Hz`
- `spectral centroid`: чаще всего `1295-2239 Hz`
- `rms`: примерно `0.145-0.195`

Практически это означает один и тот же тип lead voice:

- низкий/средне-низкий мужской голос
- сухой ближний микрофон
- минимум воздушной поп-эмоциональности
- плотная дикция вместо длинных распевов

### 4. Genre was moved to the background

Лучшие takes меняли production shell:

- trap
- phonk
- boom-bap
- techno-rap

Но не меняли voice core. Это произошло потому, что genre cues были вынесены в
tail (`Russian trap`, `phonk`, `warehouse`, `boom-bap`), а не смешивались с
описанием тембра и манеры исполнения.

## Keep Rules For Swallow Boy Retarget

Нужно сохранить:

1. **voice-first ordering** — сначала тембр/манера, потом жанр
2. **short-form generation** — target `15-35 s`, без long intro/outro
3. **dry/intimate male lead** — не widening lead, widening только ad-libs
4. **understated delivery** — deadpan, close, controlled
5. **light autotune only** — не `no autotune`, но и не heavy melodic robot
6. **short hooks** — 1 anchor line, 1-2 repeats, без длинной песенной формы

## Discard Rules For Swallow Boy Retarget

Нужно убрать или сильно ограничить:

- long-form lyrics
- melodic crooner bridges
- choir / crowd as lead instead of support
- bright EDM top-end phrasing
- theatrical punch-up, если уходит из understated male voice
- aggressive overdrive, если ломает дикцию

## What Must Change For Swallow Boy

Taras-lock был хорош как synthetic scaffold, но под `swallow boy` нужно сместить
фокус с “cold cocky trap caricature” к более конкретному референсному голосу.

Поэтому для нового core:

- оставить `mid-to-low male baritone`
- оставить `close-mic dry`
- оставить `controlled light autotune`
- ослабить `gang-chant` как обязательный признак
- ослабить `cold cocky swagger` до `restrained confident male lead`
- сильнее зафиксировать `diction clarity` и `consistent throat color`

## Top 5 Promising Existing Takes

Эти take'и лучше всего подходят как основа для `swallow boy` retarget, потому что
они уже сидят внутри нужного тембрового кластера и не слишком жанрово кричат.

1. `03_whisper_menace_42d2d442 [...]`
   - `f0 median 78.1`, `centroid 1295.7`
   - самый тёмный и интимный lead
   - хорошо показывает close-mic restraint

2. `03_whisper_menace_bdd763f0 [...]`
   - `f0 median 70.0`, `centroid 1502.7`
   - ещё ближе к low-baritone frame
   - хороший кандидат на “understated menace” baseline

3. `01_deadpan_baritone_c7da753d [...]`
   - `f0 median 70.0`, `centroid 1533.3`
   - чистый deadpan foundation без сильного genre stamp

4. `07_boom_bap_classic_5a3c8bfa [...]`
   - `f0 median 71.6`, `centroid 1787.6`
   - лучшая дикция среди более текстовых take'ов
   - полезен как reference for articulation

5. `06_light_at_melody_hook_cdb7cc7d [...]`
   - `f0 median 82.8`, `centroid 1674.6`
   - показывает верхний предел допустимого melodic/autotune coloration

## Secondary / More Fragile Takes

- `04_gritty_overdrive_0076cd41` — слишком короткий и яркий
- `08_techno_rap_warehouse_ef6ffbc6` — production shell слишком доминирует
- `07_boom_bap_classic_6b0d742a` — `f0 median 108.6`, уходит выше к менее стабильному тембру

## Final Recommendation For The Next 10 Variants

Новый `swallow boy` цикл должен строиться так:

1. один новый **voice core** с упором на restrained male lead
2. 10 controlled twists вокруг него
3. жанры только как secondary tail
4. короткие тексты и короткие hooks
5. ranking не по “самый эффектный”, а по:
   - timbre match
   - diction clarity
   - emotional restraint
   - portability to later verified Voice

## One-line Conclusion

Предыдущий цикл доказал, что **Suno v5.5 можно заставить держать один synthetic voice across genres**, если фиксировать тембр первым, держать short-form и не позволять production shell переписать lead identity.
