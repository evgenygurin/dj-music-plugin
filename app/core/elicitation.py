"""Elicitation utilities — re-export shim.

The real implementation lives in app.mcp.elicitation.
"""

from app.mcp.elicitation import safe_choice, safe_confirm, safe_elicit

__all__ = ["safe_choice", "safe_confirm", "safe_elicit"]
