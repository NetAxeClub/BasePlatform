from __future__ import annotations

from typing import Optional

from apps.config_center.config_parse.structured.profiles import DEFAULT_PROFILES


class StructuredConfigProfileRegistry:
    def __init__(self):
        self._profiles = list(DEFAULT_PROFILES)

    def get(self, vendor: str):
        normalized_vendor = (vendor or '').strip()
        for profile in self._profiles:
            if profile.matches(normalized_vendor):
                return profile
        return None


profile_registry = StructuredConfigProfileRegistry()


def get_structured_profile(vendor: str) -> Optional[object]:
    return profile_registry.get(vendor)
