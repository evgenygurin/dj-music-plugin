"""Smoke-test all new MCP tools via in-process client."""
import asyncio

from fastmcp import Client
from app.server.app import build_mcp_app_for_tests


async def main():
    mcp = await build_mcp_app_for_tests(with_transforms=False)
    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}

        expected = [
            "subgenre_preset", "energy_arc_plan",
            "filter_sweep_builder", "echo_builder", "reverb_builder",
            "auto_fix", "cue_points", "transition_window",
            "key_compatibility", "multi_deck_plan", "stem_matrix",
        ]
        missing = [n for n in expected if n not in names]
        if missing:
            print(f"MISSING TOOLS: {missing}")
            return 1
        print(f"All {len(expected)} new tools discovered")

        # Quick test: subgenre_preset
        r = await client.call_tool("subgenre_preset", {"subgenre": "industrial_techno"})
        d = r.structured_content
        assert isinstance(d, dict)
        assert d["subgenre"] == "industrial_techno"
        assert d["transition_bars"] == 16
        print("  subgenre_preset OK")

        # Quick test: energy_arc_plan
        r = await client.call_tool("energy_arc_plan", {"shape": "roller", "num_tracks": 8})
        d = r.structured_content
        assert isinstance(d, dict)
        assert len(d["slots"]) == 8
        print("  energy_arc_plan OK")

        # Quick test: filter_sweep_builder
        r = await client.call_tool("filter_sweep_builder", {"preset": "classic_lowpass"})
        d = r.structured_content
        assert isinstance(d, dict)
        assert d.get("outgoing") is not None
        print("  filter_sweep_builder OK")

        # Quick test: echo_builder
        r = await client.call_tool("echo_builder", {"preset": "techno_standard"})
        d = r.structured_content
        assert isinstance(d, dict)
        assert d["delay_ms"] > 0
        print("  echo_builder OK")

        # Quick test: reverb_builder
        r = await client.call_tool("reverb_builder", {"preset": "techno_hall"})
        d = r.structured_content
        assert isinstance(d, dict)
        assert d["decay_s"] > 0
        print("  reverb_builder OK")

        # Quick test: key_compatibility
        r = await client.call_tool("key_compatibility", {"from_key": 13, "to_key": 14})
        d = r.structured_content
        assert isinstance(d, dict)
        assert "same" in d["relation"] or "perfect" in d["relation"]
        print("  key_compatibility OK")

        print("\nALL SMOKE TESTS PASSED")
        return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
