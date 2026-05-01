from pretix.base.models import Event as RealEvent


class SettingsAdapter:
    """
    Wraps a real settings object for use in contexts where writes should
    be silently ignored, such as when instantiating payment providers
    outside of a normal request.
    """

    def __init__(self, real_settings):
        object.__setattr__(self, '_real', real_settings)

    def set(self, *args, **kwargs):
        pass

    def get(self, key, *args, **kwargs):
        return self._real.get(key, *args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._real, item)

    def __setattr__(self, key, value):
        pass


class EventAdapter:
    """
    Wraps a real Event object to satisfy the BasePaymentProvider interface
    without requiring a full database-backed request context.
    """

    def __init__(self, real_event: RealEvent):
        object.__setattr__(self, '_real', real_event)
        object.__setattr__(self, 'settings', SettingsAdapter(real_event.settings))

    def __getattr__(self, item):
        if item == 'settings':
            return object.__getattribute__(self, 'settings')
        return getattr(object.__getattribute__(self, '_real'), item)

    def __setattr__(self, key, value):
        pass


def build_event_adapter() -> EventAdapter:
    """
    Returns an EventAdapter wrapping the first available event,
    or None if no events exist.
    """
    real_event = RealEvent.objects.first()
    if real_event is None:
        return None
    return EventAdapter(real_event)
