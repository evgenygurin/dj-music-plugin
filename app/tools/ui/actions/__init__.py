"""App-hidden action wrappers for the DJ Control Center UI buttons.

Each tool here is ``visibility=["app"]`` — callable via ``CallTool`` from the
Prefab UI, hidden from the model. They orchestrate EXISTING tools/handlers
(sequence_optimize, set_version_build, audio_file_download,
track_features_reanalyze); no business logic lives here.
"""
