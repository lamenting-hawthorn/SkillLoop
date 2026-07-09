import pytest

from skillloop.errors import InputError, PolicyError
from skillloop.policy import SkillLoopPolicy
from skillloop.sanitize import MAX_FIELD_CHARS


def test_default_policy_is_valid():
    assert SkillLoopPolicy.default().version == "1.0"


def test_unknown_ingestion_adapter_raises_policy_error():
    with pytest.raises(PolicyError):
        SkillLoopPolicy.from_dict({"ingestion": {"adapter": "unknown-adapter"}})


def test_unknown_dataset_kind_raises_policy_error():
    with pytest.raises(PolicyError):
        SkillLoopPolicy.from_dict({"dataset": {"kind": "weird"}})


def test_unknown_training_target_raises_policy_error():
    with pytest.raises(PolicyError):
        SkillLoopPolicy.from_dict({"training": {"target": "unsloth"}})


def test_unsupported_mode_raises_policy_error():
    with pytest.raises(PolicyError):
        SkillLoopPolicy.from_dict({"mode": "chaos"})


def test_out_of_range_scores_raise_policy_error():
    with pytest.raises(PolicyError):
        SkillLoopPolicy.from_dict({"evaluation": {"min_score": 200}})
    with pytest.raises(PolicyError):
        SkillLoopPolicy.from_dict({"dataset": {"min_score": -5}})


def test_non_positive_max_sessions_raises_policy_error():
    with pytest.raises(PolicyError):
        SkillLoopPolicy.from_dict({"ingestion": {"max_sessions": 0}})


def test_oversized_policy_field_raises_input_error():
    with pytest.raises(InputError):
        SkillLoopPolicy.from_dict({"ingestion": {"hermes_db_path": "x" * (MAX_FIELD_CHARS + 1)}})


def test_policy_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "policy.json"
    policy = SkillLoopPolicy.default()
    policy.ingestion.enabled = True
    policy.ingestion.adapter = "generic"
    policy.save(path)

    loaded = SkillLoopPolicy.load(path)
    assert loaded.ingestion.adapter == "generic"
    assert loaded.ingestion.enabled is True
