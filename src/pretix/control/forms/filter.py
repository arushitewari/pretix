#
# Refactored for CSCI 630 Project 3 — Issue #82
# Anti-pattern: Global State Overuse — module-level mutable PAYMENT_PROVIDERS list
#               acting as an implicit shared cache with a manual guard
# Design Pattern: Factory Method — PaymentProviderFactory encapsulates creation
#                 and caching of provider instances
#
# File: src/pretix/control/forms/filter.py  (excerpt showing the changed section)
#

# ---------------------------------------------------------------------------
# BEFORE (global state anti-pattern):
#
#   PAYMENT_PROVIDERS = []          # <-- mutable module-level global
#
#   def get_all_payment_providers():
#       global PAYMENT_PROVIDERS    # <-- explicit global mutation
#       if PAYMENT_PROVIDERS:
#           return PAYMENT_PROVIDERS
#       class FakeSettings: ...
#       class FakeEvent: ...
#       for recv, providers in register_payment_providers.send(...):
#           ...
#       return PAYMENT_PROVIDERS
#
# Problems:
# - Implicit shared mutable state across all callers in a process
# - "global" keyword signals the design is fighting the language
# - No single owner of the creation logic — any caller could mutate the list
# - Difficult to reset in tests (requires patching module globals)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# AFTER: Factory Method pattern
#
# PaymentProviderFactory owns the instance cache privately.
# The public interface is a single method: get_all().
# Module-level global is gone. Tests can instantiate a fresh factory.
# ---------------------------------------------------------------------------

from pretix.base.signals import register_payment_providers


class PaymentProviderFactory:
    """
    Factory for payment provider instances used in filter forms.

    Responsibilities (before: spread across a global list + a function):
    - Creates FakeSettings/FakeEvent stubs needed to instantiate providers
      without a real database event.
    - Caches the resulting list so repeated calls within a request are cheap.
    - Provides a reset() method so tests can clear cached state cleanly.

    Usage:
        providers = payment_provider_factory.get_all()
    """

    def __init__(self):
        self._cache = None

    def get_all(self):
        """Return all registered payment providers, building them on first call."""
        if self._cache is not None:
            return self._cache
        self._cache = self._build()
        return self._cache

    def reset(self):
        """Clear the cache — primarily useful in tests."""
        self._cache = None

    # ------------------------------------------------------------------
    # Private factory method — was previously inlined inside
    # get_all_payment_providers() alongside the global mutation.
    # ------------------------------------------------------------------
    def _build(self):
        from pretix.base.models import Event

        class FakeSettings:
            """Stub settings that accepts writes but reads through to originals."""
            def __init__(self, orig_settings):
                self.orig_settings = orig_settings

            def set(self, *args, **kwargs):
                pass  # silently discard writes

            def __getattr__(self, item):
                return getattr(self.orig_settings, item)

        class FakeEvent:
            """Minimal event stub that satisfies provider constructors."""
            def __init__(self, orig_event):
                self.orig_event = orig_event
                self.settings = FakeSettings(orig_event.settings)

            def __getattr__(self, item):
                return getattr(self.orig_event, item)

        # Use the first available event as a prototype; providers only need
        # shape-compatible settings, not real event data.
        try:
            prototype_event = FakeEvent(Event.objects.first())
        except Exception:
            return []

        providers = []
        for _recv, provider_classes in register_payment_providers.send(sender=prototype_event):
            if not isinstance(provider_classes, (list, tuple)):
                provider_classes = [provider_classes]
            for provider_class in provider_classes:
                try:
                    providers.append(provider_class(prototype_event))
                except Exception:
                    pass  # skip providers that fail to instantiate without real config

        return providers


# Module-level singleton replaces the bare PAYMENT_PROVIDERS global.
# External callers replace:
#   get_all_payment_providers()
# with:
#   payment_provider_factory.get_all()
payment_provider_factory = PaymentProviderFactory()


# ---------------------------------------------------------------------------
# Backwards-compatible shim so existing call sites don't need updating yet.
# Can be removed once all callers are migrated.
# ---------------------------------------------------------------------------
def get_all_payment_providers():
    return payment_provider_factory.get_all()
