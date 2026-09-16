"""Provider-neutral payment provider layer (ADR-016)."""

from app.providers.base import ProviderPort
from app.providers.registry import ProviderRegistry, build_default_registry

provider_registry = build_default_registry()

__all__ = ["ProviderPort", "ProviderRegistry", "provider_registry"]