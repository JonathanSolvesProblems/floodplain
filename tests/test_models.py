import pytest

from floodplain.llm import TokenFactory

TODAY = ["nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "nvidia/nemotron-3-super-120b-a12b",
         "nvidia/Nemotron-3-Ultra-550b-a55b", "nvidia/Nemotron-3.5-Super-VL", "nvidia/Nemotron-3_5-Lightning"]
AFTER_RETIREMENT = ["nvidia/Nemotron-3-Ultra-550b-a55b", "nvidia/Nemotron-3.5-Super-VL",
                    "nvidia/Nemotron-3_5-Lightning", "zai-org/GLM-5.2"]


def tf(monkeypatch):
    for t in ("NANO", "SUPER", "ULTRA"):
        monkeypatch.delenv(f"FLOODPLAIN_MODEL_{t}", raising=False)
    monkeypatch.setenv("NEBIUS_API_KEY", "test")
    return TokenFactory()


def test_each_tier_gets_its_own_model_while_all_three_are_served(monkeypatch):
    t = tf(monkeypatch)
    m = t.pick_models(TODAY)
    assert m == {"nano": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "super": "nvidia/nemotron-3-super-120b-a12b",
                 "ultra": "nvidia/Nemotron-3-Ultra-550b-a55b"}
    assert t.substituted == {}


def test_a_retired_tier_falls_back_to_one_still_served_instead_of_failing(monkeypatch):
    t = tf(monkeypatch)
    m = t.pick_models(AFTER_RETIREMENT)
    assert m["nano"] == m["super"] == m["ultra"] == "nvidia/Nemotron-3-Ultra-550b-a55b"
    assert t.substituted == {"nano": "ultra", "super": "ultra"}


def test_no_nemotron_at_all_is_still_an_error(monkeypatch):
    with pytest.raises(RuntimeError):
        tf(monkeypatch).pick_models(["zai-org/GLM-5.2"])
