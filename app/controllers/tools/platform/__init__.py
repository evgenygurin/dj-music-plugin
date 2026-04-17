"""Platform tool package.

Thin adapters that delegate to :class:`~app.providers.protocol.MusicProvider`.
Split by platform entity for navigability; :class:`FileSystemProvider` picks
up ``@tool`` definitions from every submodule automatically.

- :mod:`search` — ``search_platform``
- :mod:`tracks` — ``get_platform_tracks``, ``get_platform_artist_tracks``, ``resolve_platform_track_ids``
- :mod:`albums` — ``get_platform_album``
- :mod:`playlists` — ``platform_playlists`` (ActionDispatcher, 8 actions)
- :mod:`likes` — ``platform_liked_tracks`` (ActionDispatcher, 3 actions)
"""
