"""Yandex Music tool package.

Thin adapters that delegate to :class:`~app.ym.client.YandexMusicClient`.
Split by YM entity for navigability; :class:`FileSystemProvider` picks
up ``@tool`` definitions from every submodule automatically.

- :mod:`search` — ``ym_search``
- :mod:`tracks` — ``ym_get_tracks``, ``ym_artist_tracks``
- :mod:`albums` — ``ym_get_album``
- :mod:`playlists` — ``ym_playlists`` (ActionDispatcher, 8 actions)
- :mod:`likes` — ``ym_likes`` (ActionDispatcher, 3 actions)
"""
