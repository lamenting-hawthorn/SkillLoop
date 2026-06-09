import json

from skillloop.training_config import TrainingConfigRequest, generate_training_config


def _manifest(tmp_path):
    train = tmp_path / "sft.train.jsonl"
    train.write_text('{"messages":[]}\n')
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "id": "manifest-1",
                "kind": "sft",
                "records": 1,
                "estimated_tokens": 12,
                "output_files": {"train": str(train)},
            }
        )
    )
    return manifest


def test_generate_trl_config(tmp_path):
    manifest = _manifest(tmp_path)
    summary = generate_training_config(
        TrainingConfigRequest(
            target="trl",
            dataset_manifest=str(manifest),
            base_model="NousResearch/Test",
            output_dir=str(tmp_path / "out"),
            config_dir=tmp_path / "configs",
        )
    )

    config = tmp_path / "configs" / "trl_sft_config.json"
    payload = json.loads(config.read_text())
    assert summary["training_auto_run"] is False
    assert payload["safety"]["training_auto_run"] is False
    assert payload["dataset_manifest_id"] == "manifest-1"
    assert payload["train_file"].endswith("sft.train.jsonl")


def test_generate_unsloth_config_and_skeleton(tmp_path):
    manifest = _manifest(tmp_path)
    summary = generate_training_config(
        TrainingConfigRequest(
            target="unsloth",
            dataset_manifest=str(manifest),
            base_model="NousResearch/Test",
            output_dir=str(tmp_path / "out"),
            config_dir=tmp_path / "configs",
        )
    )

    assert (tmp_path / "configs" / "unsloth_config.json").exists()
    script = (tmp_path / "configs" / "unsloth_sft_skeleton.py").read_text()
    assert "trainer.train()" in script
    assert "# trainer.train()" in script
    assert summary["execution"] == "config_generation_only"


def test_generate_axolotl_config(tmp_path):
    manifest = _manifest(tmp_path)
    generate_training_config(
        TrainingConfigRequest(
            target="axolotl",
            dataset_manifest=str(manifest),
            base_model="NousResearch/Test",
            output_dir=str(tmp_path / "out"),
            config_dir=tmp_path / "configs",
        )
    )

    config = (tmp_path / "configs" / "axolotl_config.yml").read_text()
    assert "base_model" in config
    assert "training_auto_run: false" in config
    assert "sft.train.jsonl" in config
