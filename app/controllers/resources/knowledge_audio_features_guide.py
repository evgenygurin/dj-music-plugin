"""Справочник полей трека и аудиопризнаков для диджея (knowledge://)."""

from __future__ import annotations

import json
from typing import Any

from fastmcp.resources import resource

from app.config import settings
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_REFERENCE,
    RESOURCE_META,
    RESOURCE_VERSION,
)


def _build_payload() -> dict[str, Any]:
    """Структурированный справочник: имена колонок = ключи в ``fields``."""
    return {
        "title": "Справочник полей трека и audio features для DJ (techno / EDM)",
        "document_version": "1.1.0",
        "language": "ru",
        "scope": (
            "Описание смысла полей из таблицы ``tracks`` и ``track_audio_features_computed``, "
            "как их использовать при отборе треков, сведении и построении сета в техно и родственных "
            "жанрах. Диапазоны ориентировочные; в клубе добавляются компрессия звуковой системы и "
            "акустика зала."
        ),
        "methodology": {
            "how_to_read_ranges": [
                "hard_bounds: жёсткие границы (схема/алгоритм/стандарт).",
                "project_gates: практические quality-gates из конфигурации текущего проекта.",
                "dj_working_range: рабочие диапазоны для клубного отбора и сведения в техно.",
            ],
            "important_note": (
                "Многие признаки (особенно spectral/perceptual) интерпретируются "
                "относительно вашей библиотеки. Сравнивать лучше percentiles внутри каталога, "
                "а не абсолютные числа между разными пайплайнами."
            ),
        },
        "pair_with_runtime": (
            "Актуальные значения для трека: ресурс ``track://{track_id}/features`` "
            "(поле ``audio_features`` — полная строка анализа)."
        ),
        "sources": [
            {
                "id": "essentia_danceability",
                "label": "Essentia: Danceability",
                "url": "https://essentia.upf.edu/reference/std_Danceability.html",
            },
            {
                "id": "essentia_dynamic_complexity",
                "label": "Essentia: DynamicComplexity",
                "url": "https://essentia.upf.edu/reference/std_DynamicComplexity.html",
            },
            {
                "id": "essentia_dissonance",
                "label": "Essentia: Dissonance",
                "url": "https://essentia.upf.edu/reference/std_Dissonance.html",
            },
            {
                "id": "essentia_pitch_salience",
                "label": "Essentia: PitchSalience",
                "url": "https://essentia.upf.edu/reference/std_PitchSalience.html",
            },
            {
                "id": "essentia_rhythm_extractor",
                "label": "Essentia: RhythmExtractor2013",
                "url": "https://essentia.upf.edu/reference/std_RhythmExtractor2013.html",
            },
            {
                "id": "essentia_bpm_histogram",
                "label": "Essentia: BpmHistogramDescriptors",
                "url": "https://essentia.upf.edu/reference/std_BpmHistogramDescriptors.html",
            },
            {
                "id": "essentia_beats_loudness",
                "label": "Essentia: BeatsLoudness",
                "url": "https://essentia.upf.edu/reference/std_BeatsLoudness.html",
            },
            {
                "id": "essentia_key",
                "label": "Essentia: Key (HPCP-based, EDM profiles incl. edma/edmm)",
                "url": "https://essentia.upf.edu/reference/std_Key.html",
            },
            {
                "id": "essentia_spectral_complexity",
                "label": "Essentia: SpectralComplexity",
                "url": "https://essentia.upf.edu/reference/std_SpectralComplexity.html",
            },
            {
                "id": "librosa_spectral_centroid",
                "label": "librosa: spectral_centroid",
                "url": "https://librosa.org/doc/latest/generated/librosa.feature.spectral_centroid.html",
            },
            {
                "id": "librosa_spectral_rolloff",
                "label": "librosa: spectral_rolloff",
                "url": "https://librosa.org/doc/latest/generated/librosa.feature.spectral_rolloff.html",
            },
            {
                "id": "librosa_spectral_flatness",
                "label": "librosa: spectral_flatness",
                "url": "https://librosa.org/doc/latest/generated/librosa.feature.spectral_flatness.html",
            },
            {
                "id": "librosa_spectral_contrast",
                "label": "librosa: spectral_contrast",
                "url": "https://librosa.org/doc/latest/generated/librosa.feature.spectral_contrast.html",
            },
            {
                "id": "librosa_mfcc",
                "label": "librosa: MFCC",
                "url": "https://librosa.org/doc/latest/generated/librosa.feature.mfcc.html",
            },
            {
                "id": "librosa_tempogram",
                "label": "librosa: tempogram",
                "url": "https://librosa.org/doc/latest/generated/librosa.feature.tempogram.html",
            },
            {
                "id": "librosa_tonnetz",
                "label": "librosa: tonnetz",
                "url": "https://librosa.org/doc/latest/generated/librosa.feature.tonnetz.html",
            },
            {
                "id": "librosa_hpss",
                "label": "librosa: HPSS",
                "url": "https://librosa.org/doc/main/generated/librosa.effects.hpss.html",
            },
            {
                "id": "ebu_r128",
                "label": "EBU R 128 (2023): LUFS/LRA/True Peak recommendations",
                "url": "https://tech.ebu.ch/files/live/sites/tech/files/shared/r/r128.pdf",
            },
            {
                "id": "itu_bs1770",
                "label": "ITU-R BS.1770: loudness and true-peak algorithm family",
                "url": "https://www.itu.int/rec/R-REC-BS.1770/en",
            },
            {
                "id": "wikipedia_techno",
                "label": "Techno overview (genre-level baseline tempo + 4/4 context)",
                "url": "https://en.wikipedia.org/wiki/Techno",
            },
        ],
        "techno_baseline": {
            "genre_level_context": {
                "tempo_and_meter": (
                    "Базовый контекст жанра: 4/4 и часто ~120–150 BPM "
                    "(исторический диапазон жанра, см. wikipedia_techno)."
                ),
                "practical_note": (
                    "Поджанровые границы плавают по сценам и эпохам; "
                    "для live-DJ важнее совместимость пары треков (BPM/key/energy), "
                    "чем жёсткая принадлежность к поджанру."
                ),
            },
            "project_quality_gates_from_settings": {
                "bpm_min_max": [settings.techno_bpm_min, settings.techno_bpm_max],
                "integrated_lufs_min_max": [settings.techno_lufs_min, settings.techno_lufs_max],
                "energy_mean_min": settings.techno_energy_min,
                "onset_rate_min": settings.techno_onset_rate_min,
                "kick_prominence_min": settings.techno_kick_prominence_min,
                "pulse_clarity_min": settings.techno_pulse_clarity_min,
                "hp_ratio_max": settings.techno_hp_ratio_max,
                "centroid_hz_min_max": [settings.techno_centroid_min, settings.techno_centroid_max],
                "spectral_flatness_max": settings.techno_flatness_max,
                "tempo_confidence_min": settings.techno_tempo_confidence_min,
                "bpm_stability_min": settings.techno_bpm_stability_min,
                "crest_factor_db_max": settings.techno_crest_factor_max,
                "loudness_range_lu_max": settings.techno_lra_max,
                "hnr_db_min": settings.techno_hnr_min,
            },
            "mixing_constraints_from_settings": {
                "transition_hard_reject_bpm_diff": settings.transition_hard_reject_bpm_diff,
                "transition_hard_reject_camelot_dist": settings.transition_hard_reject_camelot_dist,
                "transition_hard_reject_energy_gap_lufs": settings.transition_hard_reject_energy_gap,
            },
        },
        "techno_bpm_context": {
            "typical_subgenre_ranges_bpm": {
                "note": (
                    "Ориентир для DJ-планирования (не стандарт): использовать вместе "
                    "с BPM из ``track://{id}/features`` и quality-gates проекта."
                ),
                "ambient_dub_dub_techno": "≈115–128",
                "minimal_detroit_progressive": "≈122–135",
                "driving_peak_time": "≈128–140",
                "hard_industrial": "≈135–155+",
            },
            "dj_takeaway": (
                "Для плавного бит-матчинга удобно подбирать соседние треки с близким BPM; "
                "переходы >3–5 BPM за один микс часто требуют EQ, короткой фразы или моста "
                "(аутро/брейк, изменение pitch)."
            ),
        },
        "library_track_columns": {
            "id": {
                "label_ru": "ID трека",
                "meaning": "Внутренний первичный ключ в каталоге.",
                "dj_use": "Ссылки в сетах, плейлистах, переходах; стабильный идентификатор.",
            },
            "title": {
                "label_ru": "Название",
                "meaning": "Человекочитаемое имя трека.",
                "dj_use": "Навигация в библиотеке, поиск, чтение сет-листа.",
            },
            "sort_title": {
                "label_ru": "Сортировочное имя",
                "meaning": "Нормализованная строка для сортировки (без артиклей и т.п.).",
                "dj_use": "Упорядочивание каталога.",
            },
            "duration_ms": {
                "label_ru": "Длительность, мс",
                "meaning": "Длина трека.",
                "dj_use": "Планирование слота, расчёт тайминга, переходы к краям трека (интро/аутро).",
            },
            "status": {
                "label_ru": "Статус",
                "meaning": "Активен / архив в локальном каталоге.",
                "dj_use": "Исключать архив из кандидатов на живой сет при необходимости.",
            },
            "created_at": {
                "label_ru": "Создан",
                "meaning": "Время записи в БД.",
                "dj_use": "Аудит, сортировка импорта.",
            },
            "updated_at": {
                "label_ru": "Обновлён",
                "meaning": "Последнее изменение метаданных.",
                "dj_use": "Отладка синхронизации.",
            },
        },
        "fields": {
            "track_id": {
                "group": "meta",
                "label_ru": "ID трека (FK)",
                "meaning": "Связь строки признаков с записью в ``tracks``.",
                "dj_use": "Тот же ID, что в ``track://…/features`` и в инструментах библиотеки.",
                "typical_range": "целое > 0",
            },
            "pipeline_run_id": {
                "group": "meta",
                "label_ru": "Запуск пайплайна",
                "meaning": "Ссылка на прогон анализа (версия пайплайна, параметры в связанной таблице).",
                "dj_use": "Если сравниваешь старые и новые анализы одного трека.",
                "typical_range": "целое или null",
            },
            "analysis_level": {
                "group": "meta",
                "label_ru": "Уровень анализа",
                "meaning": "0 — нет; в проекте: 2 — L1+L2; 3 — + L3 (расширенный набор дескрипторов).",
                "dj_use": "Понимать полноту полей (часть признаков может отсутствовать на низком уровне).",
                "typical_range": "0, 2 или 3",
            },
            "bpm": {
                "group": "tempo",
                "label_ru": "Темп (BPM)",
                "meaning": "Оценка ударов в минуту; для техно обычно по сетке кика.",
                "dj_use": "Подбор совместимых треков, pitch-стретч, расчёт длительности фразы.",
                "typical_range": (
                    "hard_bounds: 20–300 (DB check), "
                    f"project_gates: {settings.techno_bpm_min:.0f}–{settings.techno_bpm_max:.0f}, "
                    "genre_context: обычно ~120–150"
                ),
                "techno_notes": (
                    "Для live-сведения важнее расстояние между соседними треками, чем абсолютный BPM. "
                    f"В проекте hard-reject при ΔBPM > {settings.transition_hard_reject_bpm_diff:.0f}."
                ),
            },
            "bpm_confidence": {
                "group": "tempo",
                "label_ru": "Уверенность BPM",
                "meaning": "Насколько устойчиво определён темп (0–1 в типичной шкале проекта).",
                "dj_use": "Низкая уверенность — бит может быть размыт, ломан ритм, live-микс; ручная проверка ушами.",
                "typical_range": "0.0–1.0",
            },
            "bpm_stability": {
                "group": "tempo",
                "label_ru": "Стабильность темпа",
                "meaning": "Насколько ровная сетка во времени (дрифт / live).",
                "dj_use": "Высокая — проще длинные оверлеи в техно; низкая — возможны плавающие бочки (джаз/иви, сломанный бит).",
                "typical_range": "0.0–1.0",
            },
            "variable_tempo": {
                "group": "tempo",
                "label_ru": "Переменный темп",
                "meaning": "Признак, что темп не постоянен по всему треку.",
                "dj_use": "Осторожнее с автоматическим бит-матчем; при необходимости — ручной бит, фразы.",
                "typical_range": "true / false / null",
            },
            "integrated_lufs": {
                "group": "loudness",
                "label_ru": "Интегральная громкость (LUFS)",
                "meaning": "Средняя перцептивная громкость (K-weighted) по треку — удобнее RMS для матчинга «на громкость».",
                "dj_use": "Выравнивание gain между треками; переходы без скачка громкости. Клубные мастера часто громче стриминговых норм (-14 LUFS).",
                "typical_range": (
                    f"project_gates: {settings.techno_lufs_min:.0f}…{settings.techno_lufs_max:.0f} LUFS; "
                    "DJ_working: часто около -14…-8 LUFS (в зависимости от мастеринга/площадки)"
                ),
                "techno_notes": "Стриминг нормализует; в клубе — нет: баланс gain на пульте/канале по-прежнему важен.",
            },
            "short_term_lufs_mean": {
                "group": "loudness",
                "label_ru": "Кратковременная громкость (среднее)",
                "meaning": "Локальные колебания громкости (сверху интегральной картины).",
                "dj_use": "Оценка «насколько сжат» клип относительно соседних секунд; сочетается с integrated для динамики.",
                "typical_range": "обычно в том же порядке, что integrated, но с большим разбросом по фразам",
            },
            "momentary_max": {
                "group": "loudness",
                "label_ru": "Максимум моментальной громкости",
                "meaning": "Пики краткосрочной громкости (удар, транзиенты).",
                "dj_use": "Риск клипа на мастере; согласование с другими треками и headroom.",
                "typical_range": "LUFS-шкала; интерпретация в паре с crest",
            },
            "rms_dbfs": {
                "group": "loudness",
                "label_ru": "RMS, dBFS",
                "meaning": "Среднеквадратичный уровень — классическая «плотность» микса.",
                "dj_use": "Сравнение плотности kick/bass относительно LUFS; важно не путать с пиковыми метрами.",
                "typical_range": "зависит от калибровки; сравнивать внутри одной библиотеки",
            },
            "true_peak_db": {
                "group": "loudness",
                "label_ru": "True Peak, dBTP",
                "meaning": "Перцепция межсэмпловых пиков после конвертаций.",
                "dj_use": "Мастера оставляют запас (часто ≤ -1 dBTP) чтобы избежать клипов на ЦАП/стрим-кодеках.",
                "typical_range": "отрицательные dBTP",
            },
            "crest_factor_db": {
                "group": "loudness",
                "label_ru": "Крест-фактор",
                "meaning": "Разница между пиком и средним уровнем — «удар» vs «кирпич».",
                "dj_use": "Высокий crest — больше динамики транзиентов; низкий — плотно сжато (возможен fatigue).",
                "typical_range": "зависит от жанра; электроника с сильным лимитером — ниже",
            },
            "loudness_range_lu": {
                "group": "loudness",
                "label_ru": "Динамический диапазон громкости (LU)",
                "meaning": "Разброс локальной громкости (контраст тихих и громких участков).",
                "dj_use": "Большой диапазон — длинные автобрейки/дайв в минимал и эмбиентах; малый — сплошное давление (peak techno).",
                "typical_range": "широкий у живых аранжировок, узкий у пережатых промо",
            },
            "energy_mean": {
                "group": "energy",
                "label_ru": "Средняя энергия (RMS-подобный контур)",
                "meaning": "Общий уровень «силы» сигнала по фреймам (в шкале анализатора).",
                "dj_use": "Сопоставление интенсивности треков в сете; нарастание/спад энергии.",
                "typical_range": "0–1 в проекте",
            },
            "energy_max": {
                "group": "energy",
                "label_ru": "Макс. энергия",
                "meaning": "Пиковая активность по фреймам.",
                "dj_use": "Насколько «ударный» пик трека (дроп, климакс).",
                "typical_range": "0–1",
            },
            "energy_std": {
                "group": "energy",
                "label_ru": "Разброс энергии",
                "meaning": "Вариативность громкости во времени.",
                "dj_use": "Низкая — монотонный пресс (гипнотик); высокая — меняющиеся секции.",
                "typical_range": "малые значения у луповых техно",
            },
            "energy_slope": {
                "group": "energy",
                "label_ru": "Наклон энергии",
                "meaning": "Тенденция нарастания или спада энергии по треку.",
                "dj_use": "Подводка к дропу vs ровный кат; планирование входа в микс.",
                "typical_range": "знак и величина зависят от анализатора",
            },
            "energy_sub": {
                "group": "energy_bands",
                "label_ru": "Энергия саба",
                "meaning": "Доля/уровень в саб-полосе (низ для kick/sub).",
                "dj_use": "Совмещение баса при сведении: два сильных саба → EQ high-pass одной деки.",
                "typical_range": "относительная шкала",
            },
            "energy_low": {
                "group": "energy_bands",
                "label_ru": "Энергия low",
                "meaning": "Низкочастотная энергия (бас/низкий мид).",
                "dj_use": "Баланс с kick; конфликты при длинных оверлеях.",
                "typical_range": "относительная шкала",
            },
            "energy_lowmid": {
                "group": "energy_bands",
                "label_ru": "Low-mid энергия",
                "meaning": "Носовитость, «коробочность», часть телесности баса.",
                "dj_use": "Грязь в лоу-миду при наслоении — EQ.",
                "typical_range": "относительная шкала",
            },
            "energy_mid": {
                "group": "energy_bands",
                "label_ru": "Середина",
                "meaning": "Присутствие хэтов, перкуссии, части атак.",
                "dj_use": "Перекрытие perc-слоёв в техно.",
                "typical_range": "относительная шкала",
            },
            "energy_highmid": {
                "group": "energy_bands",
                "label_ru": "Верхняя середина",
                "meaning": "Яркость, атака хэтов, присутствие вокала/лида.",
                "dj_use": "Резкость в миксе; совместимость с тарелками соседнего трека.",
                "typical_range": "относительная шкала",
            },
            "energy_high": {
                "group": "energy_bands",
                "label_ru": "Верха",
                "meaning": "Высокочастотная энергия (air, шипение, хай-хэты).",
                "dj_use": "На больших системах «съедает» ухо — фильтрация при длинном бленде.",
                "typical_range": "относительная шкала",
            },
            "energy_sub_ratio": {
                "group": "energy_bands",
                "label_ru": "Доля саба",
                "meaning": "Нормализованная доля энергии в саб-полосе.",
                "dj_use": "Сравнение «насколько сабовый» трек относительно других в каталоге.",
                "typical_range": "0–1",
            },
            "energy_low_ratio": {
                "group": "energy_bands",
                "label_ru": "Доля low",
                "meaning": "Доля низкого регистра в суммарной энергетике.",
                "dj_use": "Переключение emphasis баса между треками.",
                "typical_range": "0–1",
            },
            "energy_lowmid_ratio": {
                "group": "energy_bands",
                "label_ru": "Доля low-mid",
                "meaning": "Плотность «тела» и носа в миксе.",
                "dj_use": "Подбор по окрасу микса (тёмный/сухой).",
                "typical_range": "0–1",
            },
            "energy_mid_ratio": {
                "group": "energy_bands",
                "label_ru": "Доля mid",
                "meaning": "Середина — ритм-гребень, часть синтов.",
                "dj_use": "Классический диапазон для клэшей при оверлее.",
                "typical_range": "0–1",
            },
            "energy_highmid_ratio": {
                "group": "energy_bands",
                "label_ru": "Доля high-mid",
                "meaning": "Свет и атака в верхней середине.",
                "dj_use": "Совместимость ярких перкуссий.",
                "typical_range": "0–1",
            },
            "energy_high_ratio": {
                "group": "energy_bands",
                "label_ru": "Доля high",
                "meaning": "Вклад верхних частот.",
                "dj_use": "Яркий минимал vs приглушённый даб.",
                "typical_range": "0–1",
            },
            "spectral_centroid_hz": {
                "group": "spectral",
                "label_ru": "Спектральный центроид, Гц",
                "meaning": "Центр масс спектра — «яркость» тембра (выше — больше высоких).",
                "dj_use": "Стыковка по яркости; техно с кислотой/хай-хэтами — выше центроид.",
                "typical_range": "типично сотни–тысячи Гц для бас-лупов ниже, для ярких хэтов выше",
            },
            "spectral_rolloff_85": {
                "group": "spectral",
                "label_ru": "Rolloff 85% (Гц)",
                "meaning": "Частота, ниже которой сосредоточено 85% спектральной энергии.",
                "dj_use": "Мониторинг «где сидит масса спектра»; связка с басом и яркостью.",
                "typical_range": "зависит от контента",
            },
            "spectral_rolloff_95": {
                "group": "spectral",
                "label_ru": "Rolloff 95% (Гц)",
                "meaning": "Более «дальний» роллофф — верхний хвост.",
                "dj_use": "Оценка хай-ээра и шипения; осторожность с фильтром на оверлее.",
                "typical_range": "зависит от контента",
            },
            "spectral_flatness": {
                "group": "spectral",
                "label_ru": "Спектральная плоскостность",
                "meaning": "Близость спектра к шуму (выше — более «шумоподобно», ниже — тональнее).",
                "dj_use": "Сырая/пыльная текстура (индастриал) vs чистые синусоиды (мелодик).",
                "typical_range": f"0–1 (librosa); project_gate max: {settings.techno_flatness_max}",
            },
            "spectral_flux_mean": {
                "group": "spectral",
                "label_ru": "Спектральный поток (среднее)",
                "meaning": "Скорость изменения спектра между кадрами — «сколько движения» в текстуре.",
                "dj_use": "Высокий flux — перкуссивные/режущие переходы; низкий — статика.",
                "typical_range": "неотрицательное",
            },
            "spectral_flux_std": {
                "group": "spectral",
                "label_ru": "Разброс spectral flux",
                "meaning": "Насколько неравномерно меняется спектр.",
                "dj_use": "Гипнотический минимал: низкий std; брейкбит: выше.",
                "typical_range": "≥ 0",
            },
            "spectral_slope": {
                "group": "spectral",
                "label_ru": "Наклон спектра",
                "meaning": "Баланс низ/верх в лог-шкале.",
                "dj_use": "Тёмный rolling бас vs светлый с хэетами.",
                "typical_range": "знак зависит от реализации",
            },
            "spectral_contrast": {
                "group": "spectral",
                "label_ru": "Спектральный контраст",
                "meaning": "Контраст между пиками и долинами в полосах (в духе MPEG-7).",
                "dj_use": "Показатель «перфорированности» текстуры; полезно для тимбрального сходства.",
                "typical_range": "в единицах реализации анализатора",
            },
            "key_code": {
                "group": "key",
                "label_ru": "Код тональности (Camelot index)",
                "meaning": "0–23 — соответствие нотации Camelot/внутреннему кругу (см. reference://camelot).",
                "dj_use": "Гармоническое и квази-гармоническое сведение; смена ±1 по колесу, energy boost A↔B.",
                "typical_range": "0–23",
                "techno_notes": "Персушка/минимал с моно-басом терпят более длинные миксы; открытые кислотные лиды — критичнее совпадение.",
            },
            "key_confidence": {
                "group": "key",
                "label_ru": "Уверенность тональности",
                "meaning": "Надёжность оценки key.",
                "dj_use": "Низкая — атональность, перкурсивный минимал, шум; опора на ухо и Camelot как подсказку.",
                "typical_range": "0–1",
            },
            "atonality": {
                "group": "key",
                "label_ru": "Атональность",
                "meaning": "Признак слабой тональности / шумового материала.",
                "dj_use": "Не полагаться на гармоник-микс по номеру; ориентир на перкуссию и EQ.",
                "typical_range": "bool / null",
            },
            "hnr_db": {
                "group": "key",
                "label_ru": "HNR (гармонический/шумовой)",
                "meaning": "Отношение гармонической компоненты к шумовой (упрощённо).",
                "dj_use": "Низкий HNR — шип/shimmer, акцент шума (индастриал); высокий — более «тональные» источники.",
                "typical_range": "dB-шкала анализатора",
            },
            "chroma_entropy": {
                "group": "key",
                "label_ru": "Энтропия хромы",
                "meaning": "Разнообразие распределения питч-классов (насколько «размазан» тональный центр).",
                "dj_use": "Высокая энтропия — полихония/кластеры; длинные гармонические бленды сложнее.",
                "typical_range": "0–1 в текущем анализаторе; atonality=true при > 0.92",
            },
            "mfcc_vector": {
                "group": "timbre",
                "label_ru": "MFCC (строка JSON)",
                "meaning": "Мел-кепстральные коэффициенты — компактное описание тембра (см. MIR/EDM исследования).",
                "dj_use": "Семантическое сходство треков, а не ручной контроль в живом миксе; для ИИ-отбора и группировки.",
                "typical_range": "JSON-массив в строке",
            },
            "hp_ratio": {
                "group": "rhythm",
                "label_ru": "Harmonic-percussive ratio",
                "meaning": "Баланс гармонической и перкуссионной компоненты (в рамках модели HPSS).",
                "dj_use": "Высокая перкуссия — чёткий кик/хэты; гармоническая — пад/синт.",
                "typical_range": f"≥0; project_gate max: {settings.techno_hp_ratio_max}",
            },
            "onset_rate": {
                "group": "rhythm",
                "label_ru": "Плотность атак (onsets)",
                "meaning": "Сколько заметных атак в условных единицах времени.",
                "dj_use": "Трипол/трайбл vs редкий кик; перегруз по перкуссии при суммировании.",
                "typical_range": (
                    "событий/секунда; "
                    f"project_gate min: {settings.techno_onset_rate_min}; "
                    "для плотного техно обычно выше, чем у ambient/dub"
                ),
            },
            "pulse_clarity": {
                "group": "rhythm",
                "label_ru": "Ясность пульса",
                "meaning": "Насколько четко слышна долевая решётка.",
                "dj_use": "Низкая — ломан грув, syncopation; сложнее бит-матч для начинающих.",
                "typical_range": f"0–1 (нормализованная автокорреляция onset-env); project_gate min: {settings.techno_pulse_clarity_min}",
            },
            "kick_prominence": {
                "group": "rhythm",
                "label_ru": "Выраженность кика",
                "meaning": "Доля/заметность ударной бочки в ритм-слое.",
                "dj_use": "Два ярких кика в оверлее — EQ саба на одной деке; важно для peak/hard техно.",
                "typical_range": "0–1",
            },
            "danceability": {
                "group": "perceptual",
                "label_ru": "Танцевальность (оценка)",
                "meaning": "Обобщённая эвристика «насколько трек тянет в тело» (не гарантия клубного хита).",
                "dj_use": "Фильтр кандидатов для танцпола vs идущих записей.",
                "typical_range": "Essentia: обычно 0…~3 (выше = более danceable)",
            },
            "dynamic_complexity": {
                "group": "perceptual",
                "label_ru": "Динамическая сложность",
                "meaning": "Вариативность силы и/или спектра во времени.",
                "dj_use": "Драматургия сета: смена плотных и «дышащих» треков.",
                "typical_range": "Essentia: неотрицательное, часто ~0…10",
            },
            "dissonance_mean": {
                "group": "perceptual",
                "label_ru": "Средняя диссонансность",
                "meaning": "Перцептивная натянутость/roughness гармоний.",
                "dj_use": "Индустриал/кислота — выше; для длинных пэдов в миксе — осторожность.",
                "typical_range": "0–1 в типичной шкале",
            },
            "tonnetz_vector": {
                "group": "harmony_advanced",
                "label_ru": "Tonnetz-признаки (JSON)",
                "meaning": "Вектор в тональной сетке (тональные отношения).",
                "dj_use": "Продвинутый анализ гармонии; для dj — вторично по сравнению с key_code.",
                "typical_range": "JSON в строке",
            },
            "tempogram_ratio_vector": {
                "group": "rhythm_advanced",
                "label_ru": "Темпограмма (отношения, JSON)",
                "meaning": "Мультимасштабные ритмические отношения (мультипли-кативные темпа).",
                "dj_use": "Детекция полиритмики/галопа; для классического 4/4 техно реже критично.",
                "typical_range": "JSON в строке",
            },
            "beat_loudness_band_ratio": {
                "group": "rhythm_advanced",
                "label_ru": "Соотношение громкостей по полосам такта",
                "meaning": "Ритм-паттерн громкости внутри доли.",
                "dj_use": "Грув-фразировка; тонкая настройка when-to-mix.",
                "typical_range": "JSON или null",
            },
            "spectral_complexity_mean": {
                "group": "perceptual",
                "label_ru": "Средняя спектральная сложность",
                "meaning": "Богатство спектрального состава (больше независимых компонент).",
                "dj_use": "Плотные аранжировки vs минимал.",
                "typical_range": "Essentia: среднее число спектральных пиков на фрейм (относительная мера внутри библиотеки)",
            },
            "pitch_salience_mean": {
                "group": "perceptual",
                "label_ru": "Средняя выраженность питча",
                "meaning": "Насколько выделяются стабильные высотные линии.",
                "dj_use": "Мелодик/лид vs перкуссивный минимал.",
                "typical_range": f"0–1; в проекте vocal-present эвристика часто от {settings.vocal_pitch_salience_threshold}",
            },
            "bpm_histogram_first_peak_weight": {
                "group": "tempo_advanced",
                "label_ru": "Вес первого пика BPM-гистограммы",
                "meaning": "Сила доминирующего темпа в спектре гипотез.",
                "dj_use": "Низкий вес — многовариантный темп/политемпо.",
                "typical_range": "0–1 или null (Essentia BpmHistogramDescriptors)",
            },
            "bpm_histogram_second_peak_bpm": {
                "group": "tempo_advanced",
                "label_ru": "Второй пик BPM",
                "meaning": "Альтернативный темп (половинный/двойной и др.).",
                "dj_use": "Подсказка к half-time/double-time переходам.",
                "typical_range": "BPM или null",
            },
            "bpm_histogram_second_peak_weight": {
                "group": "tempo_advanced",
                "label_ru": "Вес второго пика",
                "meaning": "Насколько силён альтернативный темп.",
                "dj_use": "Оценка надёжности основного BPM.",
                "typical_range": "0–1 или null (Essentia BpmHistogramDescriptors)",
            },
            "phrase_boundaries_ms": {
                "group": "structure",
                "label_ru": "Границы фраз (JSON/строка)",
                "meaning": "Временные метки музыкальных фраз (16/32 такта и т.д.).",
                "dj_use": "Когда входить/выходить из микса на границе фразы — ключевой навык техно-диджеинга.",
                "typical_range": "JSON-массив мс или null, если не извлечено",
            },
            "dominant_phrase_bars": {
                "group": "structure",
                "label_ru": "Доминантная длина фразы (такты)",
                "meaning": "Типичный размер фразы в тактах.",
                "dj_use": "Подгонка переключений под грид 16/32.",
                "typical_range": "в текущем анализаторе обычно 8/16/32 или fallback=16",
            },
            "first_downbeat_ms": {
                "group": "structure",
                "label_ru": "Первый даунбит (мс)",
                "meaning": "Фаза относительно начала файла (выравнивание грида).",
                "dj_use": "Совмещение бочек при старте трека и автономическом бите.",
                "typical_range": "мс от 0",
            },
            "mood": {
                "group": "classification",
                "label_ru": "Поджанр (классификатор)",
                "meaning": "Один из ``TechnoSubgenre`` (см. reference://subgenres).",
                "dj_use": "Нарратив сета, подбор соседей в стиле; не абсолютная истина.",
                "typical_range": "строка из TechnoSubgenre / app.core.constants",
            },
            "mood_confidence": {
                "group": "classification",
                "label_ru": "Уверенность классификатора",
                "meaning": "Насколько модель уверена в метке mood.",
                "dj_use": "Низкая — пересечение классов (напр. driving/hypnotic).",
                "typical_range": "0–1",
            },
            "created_at": {
                "group": "meta",
                "label_ru": "Создано (признаки)",
                "meaning": "Метка времени записи строки признаков.",
                "dj_use": "Аудит пересчёта анализа.",
                "typical_range": "ISO datetime",
            },
            "updated_at": {
                "group": "meta",
                "label_ru": "Обновлено (признаки)",
                "meaning": "Последнее обновление признаков.",
                "dj_use": "Свежий анализ после смены пайплайна.",
                "typical_range": "ISO datetime",
            },
        },
    }


@resource(
    uri="knowledge://audio-features-field-guide",
    name="Audio Features Field Guide",
    title="Справочник полей трека и признаков для DJ",
    description=(
        "Смысл колонок ``tracks`` и ``track_audio_features_computed``: роли в техно/EDM, "
        "диапазоны, использование при сведении. Читать вместе с ``track://{id}/features``."
    ),
    mime_type="application/json",
    tags={"knowledge"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_REFERENCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def audio_features_field_guide() -> str:
    """Вернуть JSON со справочником по всем полям каталога и анализа."""
    return json.dumps(_build_payload(), ensure_ascii=False, indent=2)
