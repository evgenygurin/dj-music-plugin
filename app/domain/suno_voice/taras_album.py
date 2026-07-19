# ruff: noqa: RUF001

"""Taras multiform album trackbook and prompt assembly."""

from __future__ import annotations

from dataclasses import dataclass

TARAS_ALBUM_TITLE = "Тарас Вальфрамовичуровъёбович — Многоликий Разъёб"

TARAS_VOICE_CORE = (
    "Taras Volfgramovichuroebovich signature male Russian rap lead, low to mid-low baritone, "
    "cold-cocky deadpan delivery, close-mic dry presence, punchy consonants, light autotune only, "
    "slightly theatrical aristocratic menace, absurd dignity, portable across genres"
)

TARAS_NEGATIVE = (
    "female lead, choir lead, crooner melisma, opera, big EDM diva topline, "
    "heavy robotic autotune, "
    "long cinematic intro, long ambient outro"
)


@dataclass(frozen=True, slots=True)
class TarasAlbumTrack:
    slug: str
    title: str
    genre_tail: str
    twist: str
    lyrics: str


TARAS_ALBUM_TRACKS: tuple[TarasAlbumTrack, ...] = (
    TarasAlbumTrack(
        slug="grafsky_samovar_20",
        title="Графский Самовар 2.0",
        genre_tail="Russian trap, dark bells, 140 BPM half-time, booming 808, no soft chorus",
        twist="aristocratic trap opener, absurd noble posture, cold grin",
        lyrics="""[Verse]
[deadpan, low]
Графский пар над районом лёг (е)
Самовар как военный бог (а)
Я вошёл — и дрогнул неон (ха)
Это Тарас. И это закон (скр)""",
    ),
    TarasAlbumTrack(
        slug="pylny_ukaz",
        title="Пыльный Указ",
        genre_tail="boom-bap, dusty breakbeat, vinyl scratch, head-nod groove",
        twist="old-school decree, formal but menacing diction",
        lyrics="""[Verse]
[boom-bap pocket]
Я подписал этот бит как указ (е)
Пыльный винил подтверждает приказ (а)
Тарас говорит — и тихеет квартал (ха)
Каждый мой слог как железный устав (скр)""",
    ),
    TarasAlbumTrack(
        slug="betonny_etiket",
        title="Бетонный Этикет",
        genre_tail="warehouse techno-rap, 140 BPM four-on-the-floor, cold synth pulse",
        twist="ceremonial warehouse command voice",
        lyrics="""[Hook]
[on-grid, cold]
Бетонный этикет (эй)
Ни шага мимо нет (а)
Тарас за пультом — лёд (ха)
И склад за мной идёт (скр)""",
    ),
    TarasAlbumTrack(
        slug="kovbell_i_kaftan",
        title="Ковбелл и Кафтан",
        genre_tail="phonk, Memphis bounce, chopped cowbell, hard sub, smoky half-time",
        twist="absurd phonk aristocrat, dark comic swing",
        lyrics="""[Hook]
[gritty, absurd]
Ковбелл и кафтан (эй)
Я снова тут, братан (а)
Тарас в дыму как храм (ха)
И бас качает стан (скр)""",
    ),
    TarasAlbumTrack(
        slug="holodny_ustav",
        title="Холодный Устав",
        genre_tail="industrial rap, metallic percussion, strict march pulse, dark low mids",
        twist="command-track, colder and harsher than the rest",
        lyrics="""[Verse]
[very low, command]
Холодный устав у меня под языком (е)
Я режу тишину металлическим кивком (а)
Тарас не спорит — Тарас закрепляет (ха)
И каждый ваш шёпот здесь строем шагает (скр)""",
    ),
    TarasAlbumTrack(
        slug="sapogi_v_neone",
        title="Сапоги в Неоне",
        genre_tail="dark pop-rap, neon synth haze, midtempo pulse, restrained hook",
        twist="more crossover, but still cold and dignified",
        lyrics="""[Hook]
[restrained, dark pop-rap]
Сапоги в неоне, лужи как стекло (эй)
Тарас идёт спокойно — всем и так тепло (а)
Низкий тон по крышам как печать во тьме (ха)
Я опять красивый в городском огне (скр)""",
    ),
    TarasAlbumTrack(
        slug="pafos_kak_zakon",
        title="Пафос как Закон",
        genre_tail="chant-rap, crowd stomp, absurd anthem energy, clipped drums",
        twist="crowd-facing absurd banger with slogan power",
        lyrics="""[Hook]
[chant, crowd]
Пафос как закон (эй)
Тарас как бастион (а)
Город встал смирно весь (ха)
Пока мой голос здесь (скр)""",
    ),
    TarasAlbumTrack(
        slug="posledny_poklon",
        title="Последний Поклон",
        genre_tail="anthem rap closer, dark brass, drums, final march energy",
        twist="album closer, victory bow without becoming sentimental",
        lyrics="""[Verse]
[deadpan, final]
Последний поклон, но я не устал (е)
Я только сейчас как следует встал (а)
Тарас завершает не точкой, а льдом (ха)
И весь этот альбом как мой каменный дом (скр)""",
    ),
)


def assemble_taras_album_prompt(slug: str) -> tuple[TarasAlbumTrack, str, str]:
    for track in TARAS_ALBUM_TRACKS:
        if track.slug == slug:
            style = (
                f"{TARAS_VOICE_CORE}. "
                f"Track mode: {track.twist}. "
                f"{track.genre_tail}. "
                "Immediate vocal entry, no long intro, strong hook identity."
            )
            return track, style, TARAS_NEGATIVE
    known = ", ".join(track.slug for track in TARAS_ALBUM_TRACKS)
    raise ValueError(f"unknown Taras album track {slug!r}; known: {known}")
