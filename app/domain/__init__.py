"""Pure domain layer (v2).

Blueprint §3: no I/O, no DB, no FastMCP, no SQLAlchemy, no httpx.
Import-linter contract `v2-domain-pure` enforces this.

Submodules:
- transition  — 6-component scoring formula, hard constraints, recipes
- optimization — GA, greedy, fitness function
- camelot      — Camelot wheel math
- template     — 8 set templates (singular per blueprint §3)
- audit        — techno quality criteria
"""
