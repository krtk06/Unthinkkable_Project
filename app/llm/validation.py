import json
from typing import Any

from pydantic import BaseModel, ValidationError


class StructuredOutputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def parse_structured_output[ModelT: BaseModel](raw: str, model: type[ModelT]) -> ModelT:
    try:
        payload: Any = json.loads(raw)
    except json.JSONDecodeError as error:
        raise StructuredOutputError("INVALID_JSON", "LLM response is not valid JSON") from error
    try:
        return model.model_validate(payload)
    except ValidationError as error:
        raise StructuredOutputError("SCHEMA_VALIDATION_FAILED", str(error)) from error
