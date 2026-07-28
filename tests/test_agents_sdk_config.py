from app.core.config import Settings


def test_agents_sdk_receives_key_loaded_from_application_settings(monkeypatch):
    captured = {}

    def fake_set_default_openai_key(key, *, use_for_tracing):
        captured["key"] = key
        captured["use_for_tracing"] = use_for_tracing

    monkeypatch.setattr(
        "app.core.agents_sdk.set_default_openai_key",
        fake_set_default_openai_key,
    )

    from app.core.agents_sdk import configure_agents_sdk

    configure_agents_sdk(Settings(openai_api_key="test-secret"))

    assert captured == {
        "key": "test-secret",
        "use_for_tracing": False,
    }


def test_empty_key_does_not_configure_agents_sdk(monkeypatch):
    called = False

    def fake_set_default_openai_key(key, *, use_for_tracing):
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.core.agents_sdk.set_default_openai_key",
        fake_set_default_openai_key,
    )

    from app.core.agents_sdk import configure_agents_sdk

    configure_agents_sdk(Settings(openai_api_key=""))

    assert called is False
