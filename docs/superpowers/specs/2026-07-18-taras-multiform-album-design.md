# Taras Multiform Album — Design Spec

Date: 2026-07-18
Status: approved by direct execution request

## Purpose

Собрать новый альбом для персонажа **Тарас Вальфрамовичуровъёбович** в Suno.
Альбом должен быть не жанрово-ровным, а **максимально разносящим**, чтобы Тарас
звучал как один монстр в разных музыкальных телах: trap, phonk, techno-rap,
boom-bap, industrial, absurd chant, dark pop-rap и anthem mode.

## Core Idea

Это не "набор случайных генераций", а **persona album**:

- голос Тараса остаётся узнаваемым
- production shell каждый раз меняется радикально
- каждый трек должен иметь собственную фишку и собственный угол разъёба
- альбом слушается как многоликий персонаж, а не как плейлист жанров

## Taras Voice Contract

Тарас во всех треках:

- low / mid-low male baritone
- deadpan / cold-cocky delivery
- close-mic dry presence
- punchy consonants
- light autotune only
- slightly theatrical posture, но без оперности
- recognisable absurd aristocratic menace

Нельзя:

- female lead
- choir as lead
- crooner melisma
- heavy robotic autotune
- EDM diva topline
- long cinematic intros that hide the voice

## Album Format

Формат принимается как **8-track album**.

Working title:

`Тарас Вальфрамовичуровъёбович — Многоликий Разъёб`

Tracklist concept:

1. `Графский Самовар 2.0` — trap aristocrat opener
2. `Пыльный Указ` — boom-bap decree
3. `Бетонный Этикет` — warehouse techno-rap
4. `Ковбелл и Кафтан` — phonk absurdist banger
5. `Холодный Устав` — industrial command track
6. `Сапоги в Неоне` — dark pop-rap crossover
7. `Пафос как Закон` — chant / absurd crowd piece
8. `Последний Поклон` — anthem closer

## Generation Strategy

- model: `chirp-fenix`
- one common Taras voice core
- each track gets a distinct genre tail
- each track has short, explicit lyrics so the voice enters immediately
- generation returns 2 variants per track; keep at least first clip and save both
- local manifest + listen sheet
- if possible, create a Suno playlist to act as the album container

## Success Criteria

The album is successful if:

1. all 8 tracks are generated
2. Taras is recognisable across all 8
3. at least 5 tracks feel clearly different in production shell
4. the set can be treated as a coherent album / Suno playlist
