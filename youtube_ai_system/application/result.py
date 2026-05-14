"""Small result objects shared by application use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class UseCaseResult:
    """Outcome returned by application use cases.

    Use cases should carry workflow intent without knowing Flask flash,
    redirect, or template details.
    """

    success: bool
    message: str = ""
    errors: tuple[str, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)
    redirect_endpoint: str = ""

    @classmethod
    def ok(
        cls,
        message: str = "",
        *,
        data: dict[str, Any] | None = None,
        redirect_endpoint: str = "",
    ) -> "UseCaseResult":
        return cls(
            success=True,
            message=message,
            data=data or {},
            redirect_endpoint=redirect_endpoint,
        )

    @classmethod
    def fail(
        cls,
        message: str,
        *,
        errors: tuple[str, ...] | list[str] = (),
        data: dict[str, Any] | None = None,
        redirect_endpoint: str = "",
    ) -> "UseCaseResult":
        error_tuple = tuple(errors) if errors else (message,)
        return cls(
            success=False,
            message=message,
            errors=error_tuple,
            data=data or {},
            redirect_endpoint=redirect_endpoint,
        )

    @property
    def primary_message(self) -> str:
        return self.message or (self.errors[0] if self.errors else "")

