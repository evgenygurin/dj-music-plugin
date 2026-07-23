---
description: Build a DJ techno set from a playlist
agent: dj-music
---

Построй DJ-сет из плейлиста по инструкции.

## Шаги

1. Спроси пользователя: ID плейлиста (или название, найди через `dj_entity_list`),
   желаемую длительность (в треках или минутах), стиль/настроение, template если есть.

2. Получи треки плейлиста через `dj_entity_list(track)` с фильтром по плейлисту.

3. Запусти `dj_transition_score_pool` для пула треков.

4. Запусти `dj_sequence_optimize` — по умолчанию auto (GA для <200 треков).

5. Создай сет через `dj_entity_create(set)` и версию через `dj_entity_create(set_version)`.

6. Предложи пользователю рендер: `dj_render_beatgrid` → `dj_render_mixdown`.

7. Покажи результат через `dj_ui_set_view`.
