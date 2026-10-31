"""Optional model-provider adapters.

Primary candidate generation: HERE Grok Imagine (`here_imagine.py`).
Secondary candidate generation: remote xAI Images API (`xai_imagine.py`).
Registration gate: `registration.py` — must pass before compositor.
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
