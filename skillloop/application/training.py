from __future__ import annotations

from skillloop.training_config import TrainingConfigRequest, generate_training_config


class TrainingService:
    def generate(self, request: TrainingConfigRequest) -> dict:
        return generate_training_config(request)


__all__ = ["TrainingService"]
