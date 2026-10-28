"""Role-based authorization helpers."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from flask import abort
from flask_login import current_user, login_required

P = ParamSpec("P")
R = TypeVar("R")

ROLES = ("Admin", "Editor", "Viewer", "Service")
ROLE_PERMISSIONS = {
    "Admin": frozenset({"add", "delete", "edit", "view", "admin"}),
    "Editor": frozenset({"add", "delete", "edit", "view"}),
    "Viewer": frozenset({"view"}),
    "Service": frozenset({"view"}),
}


def has_permission(permission: str) -> bool:
    """Return whether the current authenticated user has a permission."""

    return bool(
        current_user.is_authenticated
        and permission in ROLE_PERMISSIONS.get(current_user.role, frozenset())
    )


def permission_required(permission: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Protect a view with login and role permission checks."""

    def decorator(view: Callable[P, R]) -> Callable[P, R]:
        @wraps(view)
        @login_required
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            if not has_permission(permission):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


admin_required = permission_required("admin")
