"""Split workflow prompts (Phase 10).

Re-exports preserved for callers that import workflows by name.
FastMCP FileSystemProvider auto-discovers @prompt-decorated functions
from each submodule, so registration does not depend on these imports.
"""

from app.controllers.prompts.workflows.build_set import build_set_workflow
from app.controllers.prompts.workflows.deliver_set import deliver_set_workflow
from app.controllers.prompts.workflows.expand_playlist import expand_playlist_workflow
from app.controllers.prompts.workflows.full_pipeline import full_expansion_pipeline
from app.controllers.prompts.workflows.improve_set import improve_set_workflow
from app.controllers.prompts.workflows.llm_discovery import llm_discovery_workflow
from app.controllers.prompts.workflows.quick_mix_check import quick_mix_check
from app.controllers.prompts.workflows.taste_analysis import taste_analysis

__all__ = [
    "build_set_workflow",
    "deliver_set_workflow",
    "expand_playlist_workflow",
    "full_expansion_pipeline",
    "improve_set_workflow",
    "llm_discovery_workflow",
    "quick_mix_check",
    "taste_analysis",
]
