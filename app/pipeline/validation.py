from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, TYPE_CHECKING

from app.pipeline.types import ValidationIssue

if TYPE_CHECKING:
    from app.pipeline.node import Node


def is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


class ValidationRule(Protocol):
    def validate(
        self,
        node: Node,
        inputs: dict[str, Any],
        params: dict[str, Any],
    ) -> list[ValidationIssue]:
        ...


@dataclass(frozen=True)
class RequiredInputRule:
    def validate(
        self,
        node: Node,
        inputs: dict[str, Any],
        params: dict[str, Any],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for name, spec in node.inputs.items():
            if spec.required and (name not in inputs or is_missing_value(inputs.get(name))):
                issues.append(
                    ValidationIssue(
                        level="error",
                        code="missing_input",
                        message=f"{name} is required",
                        field=name,
                        node_id=node.id,
                    )
                )
        return issues


@dataclass(frozen=True)
class RequiredParamRule:
    def validate(
        self,
        node: Node,
        inputs: dict[str, Any],
        params: dict[str, Any],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for name, spec in node.params.items():
            if spec.required and (name not in params or is_missing_value(params.get(name))):
                issues.append(
                    ValidationIssue(
                        level="error",
                        code="missing_param",
                        message=f"{name} is required",
                        field=name,
                        node_id=node.id,
                    )
                )
        return issues


@dataclass(frozen=True)
class RequiredParamOrEnvRule:
    param_name: str
    env_names: tuple[str, ...]

    def validate(
        self,
        node: Node,
        inputs: dict[str, Any],
        params: dict[str, Any],
    ) -> list[ValidationIssue]:
        value = params.get(self.param_name)
        has_env_value = any(not is_missing_value(os.environ.get(name)) for name in self.env_names)
        if not is_missing_value(value) or has_env_value:
            return []
        env_hint = " or ".join(self.env_names)
        return [
            ValidationIssue(
                level="error",
                code="missing_param",
                message=f"{self.param_name} is required or set {env_hint}",
                field=self.param_name,
                node_id=node.id,
            )
        ]


@dataclass(frozen=True)
class PathExistsRule:
    field: str
    source: str = "param"
    code: str = "missing_path"
    label: str | None = None
    resolver: Callable[[str], Path] | None = None

    def validate(
        self,
        node: Node,
        inputs: dict[str, Any],
        params: dict[str, Any],
    ) -> list[ValidationIssue]:
        values = params if self.source == "param" else inputs
        raw_value = values.get(self.field)
        if is_missing_value(raw_value):
            return []

        path = self.resolver(str(raw_value)) if self.resolver else Path(str(raw_value))
        if path.exists():
            return []

        name = self.label or self.field
        return [
            ValidationIssue(
                level="error",
                code=self.code,
                message=f"{name} not found: {path}",
                field=self.field,
                node_id=node.id,
            )
        ]
