"""IGE package scaffold — Method Registry loader (PR #12 contract seed).

This package is NOT production-wired into UP-engine yet.
No ComfyUI nodes, no GPU inference, no PR merges.

Import explicitly, e.g.::

    from ige.method_registry import load_registry, resolve
"""

__version__ = "0.1.0-draft"

__all__ = [
    "MethodRegistry",
    "MethodRegistryError",
    "MethodNotFoundError",
    "RegistryValidationError",
    "load_registry",
    "resolve",
    "validate_registry_data",
]


def __getattr__(name: str):
    if name in __all__:
        from . import method_registry as _mr

        return getattr(_mr, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
