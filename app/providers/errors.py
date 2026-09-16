"""Provider-port exceptions.

All of these carry a *safe* message: never a provider secret, token, signing
key, or raw payload.
"""


class ProviderIntegrationError(Exception):
    """A provider call failed in a safe, documented way."""

    def __init__(self, code: str, message_safe: str):
        super().__init__(message_safe)
        self.code = code
        self.message_safe = message_safe


class ProviderTimeoutError(ProviderIntegrationError):
    """The provider did not respond within its timeout budget."""


class CapabilityNotSupportedError(Exception):
    """The provider does not advertise the requested capability."""

    def __init__(self, capability: str, provider_code: str):
        super().__init__(
            f"Provider {provider_code} does not support capability {capability}"
        )
        self.capability = capability
        self.provider_code = provider_code


class UnknownProviderError(Exception):
    """No adapter is registered for a provider code and environment."""

    def __init__(self, provider_code: str, environment: str):
        super().__init__(
            f"No provider adapter is registered for {provider_code} / {environment}"
        )
        self.provider_code = provider_code
        self.environment = environment