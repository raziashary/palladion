"""Typed domain failures; authorization failures deliberately reveal no scope detail."""

from __future__ import annotations

from .models import ErrorCode


class EvidenceAgentError(Exception):
    code = ErrorCode.INTERNAL_ERROR
    retryable = False
    user_summary = "The request could not be completed."

    def __str__(self) -> str:
        return self.user_summary


class ValidationFailure(EvidenceAgentError):
    code = ErrorCode.VALIDATION_ERROR
    user_summary = "The request contains invalid data."


class PermissionDenied(EvidenceAgentError):
    code = ErrorCode.PERMISSION_DENIED
    user_summary = "Access denied."


class ResourceConflict(EvidenceAgentError):
    code = ErrorCode.CONFLICT
    user_summary = "The requested operation conflicts with current state."


class DependencyUnavailable(EvidenceAgentError):
    code = ErrorCode.UNAVAILABLE
    retryable = True
    user_summary = "A required dependency is unavailable."
