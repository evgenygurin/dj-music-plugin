# Swallow Boy Suno Voice Ladder — Design Spec

Date: 2026-07-18
Status: approved by direct execution request
Scope: research + short-variant ladder + Voice-ready handoff

## Purpose

Зафиксировать голос `swallow boy` в Suno с опорой на трек-референс
`ed011c66-bd94-4bb2-bfd8-ec96a78ddc93` и подготовить путь к настоящему
`Suno Voice` v5.5.

Первый deliverable этого цикла: **10 коротких vocal variants** (short-form,
15-35 s, v5.5 Pro / `chirp-fenix`) под один и тот же голос. После отбора
лучшего материала — подготовка к созданию настоящего `Voice`.

## Why This Is Feasible

В предыдущем short-form эксперименте голос уже начал стабилизироваться между
жанрами. Это произошло из-за комбинации:

1. фиксированного vocal DNA block (`mid-baritone`, `deadpan`, `close-mic`,
   `cold cocky`, `light autotune`, `wide ad-libs`)
2. короткой формы, которая уменьшает genre drift
3. узкого тембрового кластера удачных take'ов
4. выноса жанра в tail, а не в ядро голоса

По локальному анализу 15 удачных mp3 из `suno_out/rimjoba/gens_v20/`:

- `f0 median` чаще всего в диапазоне `70-90 Hz`
- `spectral centroid` примерно `1300-2200 Hz`
- dry/intimate male presence повторяется почти без отклонений

Это значит, что в v5.5 уже найден **устойчивый synthetic voice frame**, который
можно донастроить под `swallow boy`.

## Research Summary

### Official Suno / v5.5 guidance

- `v5.5` = наиболее expressive модель Suno; Voices доступны paid users.
- Для настоящего `Voice` нужны:
  - audio source, желательно чистый вокал
  - verification phrase
  - права на голос
- Voices лучше всего работают при:
  - тихой записи
  - достаточно длинном source
  - жанровом соответствии голоса и материала
  - high Audio Influence, если голос drift'ит
- `Style Persona` по-прежнему полезна как voice-equivalent слой, но не заменяет
  verified `Voice`.

### SunoAPI / technical docs

- `voice.generate` требует validation task + verification audio URL.
- `generate-persona` позволяет фиксировать style/vibe/voice character из готового
  трека, но это не заменяет verified Voice.
- `persona` лучше работает, когда описание детальное, а вокальное окно короткое
  и точное (10-30 s).

## Constraints

1. Настоящий `Voice` не делается из воздуха: нужен verify и реальный legal source.
2. Пользователь подтвердил, что голос `swallow boy` можно использовать легально.
3. Первый этап — не создавать Voice сразу, а **подобрать 10 short variants** под
   этот voice target.
4. Работа идёт на `v5.5 Pro`, то есть web-session model key `chirp-fenix`.
5. Если session bearer истёк, перед live-операциями нужен refresh токена.

## Approach Chosen

### Reference-first ladder

1. Использовать `ed011c66-bd94-4bb2-bfd8-ec96a78ddc93` как voice target.
2. Сгенерировать 10 коротких вариантов вокруг этого target.
3. Сравнить их по тембру, дикции, близости к референсу и стабильности.
4. Выбрать 1-2 лучших варианта.
5. Подготовить на их базе настоящий `Suno Voice` workflow.

Это лучше, чем `Voice-first`, потому что сначала находится реальный working DNA
голоса, а уже потом закрепляется в официальном объекте Voice.

## Target Voice Contract

Голос `swallow boy` для этого проекта должен быть:

- male Russian rap lead
- mid-to-low baritone
- close-mic, dry, intimate
- deadpan / understated, не театральный
- cold but not robotic
- light autotune, но не heavy melodic robot
- punchy consonants, короткая дикция
- короткий hook с контролируемыми ad-libs
- без female lead, choir lead, crooner melisma, operatic overreach

## Deliverables

### Deliverable A — analysis report

Описать, почему голос стал одинаковее между жанрами:

- какие именно теги удержали identity
- какие жанровые теги не ломают голос
- какие параметры короткой формы сработали
- какие локальные audio-признаки повторяются

### Deliverable B — 10 short variants pack

10 коротких генераций под `swallow boy` voice target. Каждая — отдельная vocal
hypothesis, но все под одним контрактом голоса.

Набор гипотез должен покрыть:

1. pure deadpan baritone
2. cold cocky
3. whisper menace
4. gritty overdrive
5. dry podcast-close rap
6. light-autotune chant hook
7. boom-bap classic diction
8. techno-rap warehouse timing
9. nasal modern RU rap edge
10. exact reference-clone control

### Deliverable C — Voice-ready recipe

Не финальный Voice object, а пакет для следующего шага:

- какой clip выбрать как source candidate
- какой 15-30 s window использовать
- какой description дать будущему Voice
- какой test set прогнать после Voice creation

## Architecture

Система делится на три слоя:

1. **Reference analysis**
   - reference song
   - local successful short takes
   - extracted voice rules

2. **Variant generator**
   - fixed voice core
   - per-variant twist
   - short-form lyrics templates
   - v5.5 Pro / `chirp-fenix`

3. **Voice handoff**
   - top clip selection
   - metadata for future Voice
   - operational checklist for verify flow

## Success Criteria

Проект считается успешным, если:

1. 10 short variants созданы под единый voice target.
2. Минимум 2 варианта слышатся как один и тот же исполнитель.
3. Есть явный лучший candidate для перехода к `Suno Voice`.
4. Понятно зафиксировано, почему голос удержался между жанрами.
5. Есть воспроизводимый plan для следующего live шага.

## Non-goals

- немедленное создание verified Voice в этом design doc
- длинные песни
- полный каталог жанров
- кодовое внедрение в MCP surface без необходимости
- юридическая проверка прав вне подтверждения пользователя

## Operational Notes

- `chirp-fenix` подтверждён в account usable models.
- Bearer сессии может истечь примерно через час; live phase должна начинаться с
  проверки auth и при необходимости `uv run python scripts/suno_refresh_token.py`.
- Short takes могут выходить 8-15 s даже при запросе на 30 s; это допустимо на
  analysis ladder, потому что цель — поймать тембр, а не длину как таковую.

## Next Step

Сразу после этой спеки нужен implementation plan для:

1. аналитического отчёта по уже сгенерированным variant'ам
2. генерации/добора 10 variant'ов именно под `swallow boy`
3. фиксации shortlist для будущего `Suno Voice`
