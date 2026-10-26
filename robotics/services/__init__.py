"""Сервисный слой: relay_service строит, проверяет и продолжает миссии.

errors.py содержит общие исключения сервиса.
"""

from robotics.services.errors import (
    DomainFailureError,
    ResourceConflictError,
    ResourceNotFoundError,
    ServiceError,
    ValidationFailedError,
)

__all__ = [
    "ServiceError",
    "ResourceNotFoundError",
    "ResourceConflictError",
    "ValidationFailedError",
    "DomainFailureError",
]
