from app.domain.configuration.resolver import LegacyConfigAdapter


def test_legacy_adapter_maps_existing_transition_settings() -> None:
    resolved = LegacyConfigAdapter().transition_values(
        {"hard_reject_bpm_diff": 10.0, "hard_reject_energy_gap_lufs": 6.0}
    )
    assert resolved == {
        "tempo.max_bpm_difference": 10.0,
        "energy.max_gap_lufs": 6.0,
    }
