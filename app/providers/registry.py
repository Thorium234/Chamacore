"""Provider registry and factory (ADR-016).

Resolves an adapter by ``provider_code`` and ``environment``. The domain
never imports a concrete adapter directly; it asks the registry for the port.
"""

from app.models.enums import PaymentEnvironment, PaymentProviderCode
from app.providers.base import ProviderPort
from app.providers.errors import UnknownProviderError


class ProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[tuple[PaymentProviderCode, PaymentEnvironment], ProviderPort] = {}

    def register(self, adapter: ProviderPort) -> None:
        key = (adapter.provider_code, adapter.environment)
        self._adapters[key] = adapter

    def get(self, provider_code: PaymentProviderCode, environment: PaymentEnvironment) -> ProviderPort:
        adapter = self._adapters.get((provider_code, environment))
        if adapter is None:
            raise UnknownProviderError(provider_code.value, environment.value)
        return adapter

    def supports(self, provider_code: PaymentProviderCode, environment: PaymentEnvironment) -> bool:
        return (provider_code, environment) in self._adapters

    def specs(self) -> list[ProviderPort]:
        return list(self._adapters.values())


def build_default_registry() -> ProviderRegistry:
    """Wire every supported provider adapter (imported lazily to avoid cycles)."""
    from app.providers.daraja.adapter import create_daraja_adapters
    from app.providers.jenga.adapter import create_jenga_adapters

    registry = ProviderRegistry()
    for adapter in create_jenga_adapters() + create_daraja_adapters():
        registry.register(adapter)
    return registry