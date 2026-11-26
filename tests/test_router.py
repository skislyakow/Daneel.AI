from daneel.config import HEAVY_MODEL, LIGHT_MODEL
from daneel.router import ModelRouter


def test_router_prefers_light_model_for_simple_chat() -> None:
    router = ModelRouter()

    assert router.choose("Привет!") == LIGHT_MODEL
    assert router.choose("Скажи коротко, что такое Python") == LIGHT_MODEL


def test_router_prefers_heavy_model_for_tools_and_complex_tasks() -> None:
    router = ModelRouter()

    assert router.choose("Какая погода в Москве?") == HEAVY_MODEL
    assert router.choose("Прочитай README.md") == HEAVY_MODEL
    assert router.choose("Сравни эти два подхода и объясни подробно") == HEAVY_MODEL
    assert router.choose("Напиши функцию:\ndef foo(): pass") == HEAVY_MODEL
    assert router.choose("x" * 300) == HEAVY_MODEL
