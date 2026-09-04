from app.domain.configuration.provenance import Provenance


def test_provenance_records_source_and_priority() -> None:
    provenance = Provenance(source="transition", priority=5)
    assert provenance.source == "transition"
    assert provenance.priority == 5
