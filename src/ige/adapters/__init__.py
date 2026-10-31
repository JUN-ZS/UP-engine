"""Optional model-provider adapters. No provider is enabled by default.

Active generation path: xAI Grok Imagine (see xai_imagine.py).
Registration gate: registration.py — must pass before compositor.
"""

from .registration import (
    RegistrationError,
    RegistrationReport,
    assess_registration,
    require_registration_for_composite,
)

__all__ = [
    "RegistrationError",
    "RegistrationReport",
    "assess_registration",
    "require_registration_for_composite",
]
