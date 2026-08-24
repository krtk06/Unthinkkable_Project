import json
from typing import Any, get_args

from pydantic import BaseModel, ValidationError


class StructuredOutputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _extract_json_object(raw: str) -> Any:
    """Parse JSON, tolerating markdown fences or prose around the object."""
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        closing = text.rfind("```")
        if closing != -1:
            text = text[:closing]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _nested_model(annotation: Any) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for arg in get_args(annotation):
        if isinstance(arg, type) and issubclass(arg, BaseModel):
            return arg
    return None


def _allowed_keys(model: type[BaseModel], payload: dict[str, Any]) -> dict[str, Any]:
    """Drop keys a strict model rejects so minor LLM mistakes do not fail parsing.

    Removes unknown keys and null values for non-optional fields (pydantic then
    applies the field default, e.g. an empty list for ``languages``).
    """
    out: dict[str, Any] = {}
    for name, field in model.model_fields.items():
        if name not in payload:
            continue
        value = payload[name]
        if value is None and not field.is_required():
            continue
        sub = _nested_model(field.annotation)
        if isinstance(value, dict) and sub is not None:
            value = _allowed_keys(sub, value)
        elif isinstance(value, list) and value:
            args = get_args(field.annotation)
            item = _nested_model(args[0] if args else None)
            if item is not None and all(isinstance(entry, dict) for entry in value):
                value = [_allowed_keys(item, entry) for entry in value]
        out[name] = value
    return out


def parse_structured_output[ModelT: BaseModel](raw: str, model: type[ModelT]) -> ModelT:
    try:
        payload = _extract_json_object(raw)
    except json.JSONDecodeError as error:
        raise StructuredOutputError("INVALID_JSON", "LLM response is not valid JSON") from error
    try:
        return model.model_validate(payload)
    except ValidationError as error:
        if isinstance(payload, dict) and payload:
            try:
                return model.model_validate(_allowed_keys(model, payload))
            except ValidationError as inner_error:
                # sanitization also failed — log at debug and fall through to the
                # original StructuredOutputError so the failure is not swallowed.
                import logging

                logging.getLogger(__name__).debug("sanitized payload still invalid: %s", inner_error)
        raise StructuredOutputError("SCHEMA_VALIDATION_FAILED", str(error)) from error
