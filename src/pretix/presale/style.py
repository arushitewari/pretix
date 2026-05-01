#
# Refactored for CSCI 630 Project 3 — Issue #83
# Anti-pattern: Code Duplication — widget CSS version cache-key construction
#               logic copied verbatim across multiple widget classes
# Design Pattern: Template Method — AbstractWidget defines the cache-key
#                 skeleton; subclasses provide only the variant step
#
# File: src/pretix/presale/style.py  (excerpt showing the changed section)
#

# ---------------------------------------------------------------------------
# BEFORE (duplication anti-pattern):
#
# Each widget class independently constructed its cache key:
#
#   class DefaultWidget:
#       def get_css_version(self):
#           version_parts = [settings.PRETIX_VERSION]
#           if self.event.settings.presale_css_file:
#               version_parts.append(self.event.settings.presale_css_file)
#           return hashlib.md5("|".join(version_parts).encode()).hexdigest()[:8]
#
#   class OrganizerWidget:
#       def get_css_version(self):
#           version_parts = [settings.PRETIX_VERSION]          # <-- identical
#           if self.organizer.settings.presale_css_file:       # <-- only this differs
#               version_parts.append(self.organizer.settings.presale_css_file)
#           return hashlib.md5("|".join(version_parts).encode()).hexdigest()[:8]
#
# Adding a new version component (e.g., plugin hash) requires editing every class.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# AFTER: Template Method pattern
#
# AbstractWidget.get_css_version() defines the invariant skeleton.
# Subclasses override only _get_extra_version_parts() to provide
# their specific version components.
# ---------------------------------------------------------------------------

import hashlib
from django.conf import settings


class AbstractWidget:
    """
    Base class for pretix presale widgets.

    Template method: get_css_version()
    ┌─────────────────────────────────────────┐
    │  get_css_version()  ← invariant skeleton │
    │    [settings.PRETIX_VERSION]             │
    │  + _get_extra_version_parts()  ← hook   │
    │    → hashlib.md5 → 8-char hex           │
    └─────────────────────────────────────────┘

    Subclasses must implement _get_extra_version_parts().
    """

    # ------------------------------------------------------------------
    # Template method — sealed; do not override in subclasses.
    # ------------------------------------------------------------------
    def get_css_version(self) -> str:
        """
        Return an 8-character hex cache-busting version string.

        The algorithm is fixed here:
          1. Start with the pretix release version.
          2. Append any context-specific parts from _get_extra_version_parts().
          3. Hash and truncate.

        Previously this entire body was copy-pasted into every widget class.
        """
        version_parts = [settings.PRETIX_VERSION]
        version_parts.extend(self._get_extra_version_parts())
        digest = hashlib.md5("|".join(version_parts).encode()).hexdigest()
        return digest[:8]

    # ------------------------------------------------------------------
    # Hook — subclasses override this ONE method to vary the key.
    # ------------------------------------------------------------------
    def _get_extra_version_parts(self) -> list:
        """
        Return additional strings to include in the CSS version hash.

        Default: empty list (version = PRETIX_VERSION hash only).
        Override in subclasses to add event/organizer-specific components.
        """
        return []


# ---------------------------------------------------------------------------
# Concrete subclasses — each overrides only the variant step.
# ---------------------------------------------------------------------------

class EventWidget(AbstractWidget):
    """Widget scoped to a specific event."""

    def __init__(self, event):
        self.event = event

    def _get_extra_version_parts(self) -> list:
        parts = []
        css_file = self.event.settings.presale_css_file
        if css_file:
            parts.append(css_file)
        return parts


class OrganizerWidget(AbstractWidget):
    """Widget scoped to an organizer (shown across all organizer events)."""

    def __init__(self, organizer):
        self.organizer = organizer

    def _get_extra_version_parts(self) -> list:
        parts = []
        css_file = self.organizer.settings.presale_css_file
        if css_file:
            parts.append(css_file)
        return parts


class GlobalWidget(AbstractWidget):
    """
    Widget with no event/organizer customisation.
    Uses only the base PRETIX_VERSION — no override needed.
    """
    pass


# ---------------------------------------------------------------------------
# Extension story (assignment requirement):
# Adding a new widget type that includes a plugin hash:
#
#   class PluginWidget(AbstractWidget):
#       def __init__(self, event, plugin_version):
#           self.event = event
#           self.plugin_version = plugin_version
#
#       def _get_extra_version_parts(self):
#           return [self.event.settings.presale_css_file or '', self.plugin_version]
#
# Before: developer would copy-paste get_css_version() and edit it.
# After:  developer writes only the 3-line _get_extra_version_parts() override.
# ---------------------------------------------------------------------------
