---
description: Durable DJ set construction rules for techno workflows
globs: "app/prompts/**/*.py,docs/**/*.md,CLAUDE.md"
---

# DJ Set Building Rules

Используй эти правила для workflow, где пользователь просит построить,
расширить, отревьюить, починить, экспортировать или подготовить techno-сет.

## 1. Сначала определить задачу, потом surface

- Для многошаговой музыкальной задачи предпочитай существующий MCP workflow/prompt.
- Для точечной задачи используй resources/tools напрямую.
- Перед mutating operations учитывай ожидаемый побочный эффект.
- Runtime identifiers, schema fields и operations проверяй через текущие MCP contracts, а не через старые каталоги.

## 2. Как использовать жанровые признаки

Поджанр — это пересечение нескольких осей: давление, groove, timbre, harmonic
content и сценарий выступления. Одно поле `mood` не является доказательством
жанра.

Для курации сопоставляй музыкальные ярлыки с наблюдаемыми признаками и контекстом
сета. Feature-first подход предпочтительнее слепого фильтра по одному label.

Некоторые сценические ярлыки могут не быть значениями runtime enum. В таком
случае рассматривай их как концептуальные overlays и мапь на реальные runtime
значения только на основании доступных признаков.

Подробные актуальные genre priors и исследования находятся в `docs/research/`.
Их не следует превращать в вечный runtime contract, если они не закреплены в
коде или reference resource.

## 3. Макро-дуга важнее локального score

Сначала проектируй драматургию: warm-up, build, peak, release/closing, roller,
wave или persona. После этого оптимизируй отдельные переходы.

Энергия должна двигаться блоками и волнами, а не механически возрастать на
каждом переходе. Не перегревай warm-up; в peak меняй текстуру, даже если общий
уровень давления остаётся высоким; closing должен давать понятный выход.

Если пользователь не указал контекст, предпочитай coherent journey/roller
вместо набора максимальных bangers.

## 4. Переходы

Разделяй техническую пригодность и музыкальное предпочтение.

- BPM compatibility — технический corridor, но не догма: большие изменения темпа
  требуют осмысленного bridge/reset решения.
- Harmonic compatibility — предпочтение, зависящее от надёжности key detection и
  характера материала. Для атонального/percussion-led материала harmonic score
  не должен переопределять слышимый groove.
- Energy/LUFS continuity — избегай резких скачков без художественной причины.
- При близких groove/harmony выбирай более длинные blends.
- При bass/percussion clash используй bass swap или другой transition recipe.
- Echo/filter/cut/reset техники допустимы как bridge для несовместимых пар.

Hard constraints должны отражать технически непригодные переходы. Музыкальные
предпочтения должны работать через scoring.

## 5. Key-shift и специальные приёмы

Нестандартные harmonic moves могут быть выразительным приёмом, но их следует
использовать экономно и подтверждать контекстом: позиция в драматургии, длина
blend, key reliability и наличие bridge/FX cue.

Loop-based mix-out, filter/echo transitions и другие ручные техники можно
предлагать в cheatsheet как DJ instruction, только если runtime действительно
не создаёт соответствующий artifact.

Не обещай точный cue/bar/beat result, если текущие beatgrid/cue contracts не
дают такой гарантии.

## 6. Качество данных

Никогда не придумывай BPM, key, energy, mood, scores или transition facts.
Используй runtime feature values и соответствующий уровень анализа.

NULL/unknown feature values должны трактоваться явно; неизвестное значение не
должно случайно превращаться в «плохой трек» из-за несовместимого фильтра.

Не применяй corpus-specific thresholds, ranking weights или feature assumptions
только потому, что они хорошо работали на прошлой выборке. Такие выводы должны
жить в исследовании, конфигурации или executable policy.

## 7. Persona и сценарий

Persona — это стилистическая рамка для выбора и драматургии, а не замена
объективным track features. Если для persona нет специализированной policy,
используй предусмотренный runtime fallback и не придумывай новый profile
внутри prompt.

B2B, festival, warehouse, opening, peak, closing и recovery — разные
сценарии. Используй их для выбора energy arc, novelty, blend style и tolerance
к harmonic/tempo deviations.

## 8. MCP honesty

Не обещай backend capability, которой runtime не предоставляет. Если функция
доступна только как manual DJ instruction, называй её manual instruction.
Если backend capability зависит от provider mode или optional backend, сначала
проверь capability.

## 9. Где хранить изменчивые знания

Современные сценические тренды, рыночные BPM bands, corpus measurements,
поставщик-специфичные quirks и экспериментальные scoring observations относятся
к research/reference/configuration layer, а не к этой постоянной policy.

Эти правила должны оставаться полезными после изменения количества треков,
версии модели, состава analyzer registry или текущего MCP surface.
