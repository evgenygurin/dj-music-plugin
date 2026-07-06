from app.config.delivery import DeliverySettings


def test_emit_continuous_mix_default_true():
    assert DeliverySettings().emit_continuous_mix is True


def test_emit_continuous_mix_env_override(monkeypatch):
    monkeypatch.setenv("DJ_DELIVERY_EMIT_CONTINUOUS_MIX", "false")
    assert DeliverySettings().emit_continuous_mix is False
