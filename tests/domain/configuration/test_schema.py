import pytest

from app.domain.configuration.schema import ParameterClass, ParameterDefinition


def test_parameter_definition_carries_unit_range_default_and_classification() -> None:
    parameter = ParameterDefinition(
        "tempo.max_ratio", "ratio", 0.5, 2.0, 1.06, ParameterClass.HARD
    )
    assert parameter.default == 1.06
    assert parameter.classification is ParameterClass.HARD


def test_parameter_definition_rejects_default_outside_range() -> None:
    with pytest.raises(ValueError, match="default"):
        ParameterDefinition("tempo.max_ratio", "ratio", 0.5, 2.0, 3.0, ParameterClass.HARD)
