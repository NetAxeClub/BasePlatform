import math
import time

from django.core.cache import cache
from rest_framework.throttling import BaseThrottle


class AgentBaseRateThrottle(BaseThrottle):
    rate_attr = ""
    cache_suffix = ""
    window_seconds = 60

    def allow_request(self, request, view):
        limit = getattr(view, self.rate_attr, None)
        if not limit:
            return True

        self.key = self.get_cache_key(request, view)
        if not self.key:
            return True

        now = time.time()
        history = cache.get(self.key, [])
        history = [entry for entry in history if entry > now - self.window_seconds]
        if len(history) >= limit:
            self.history = history
            self.now = now
            return False

        history.insert(0, now)
        cache.set(self.key, history, timeout=self.window_seconds)
        self.history = history
        self.now = now
        return True

    def wait(self):
        if not getattr(self, "history", None):
            return self.window_seconds
        remaining = self.window_seconds - (self.now - self.history[-1])
        return max(1, math.ceil(remaining))

    def get_cache_key(self, request, view):
        identity = self._resolve_identity(request)
        if not identity:
            return None
        scope = getattr(view, "throttle_cache_scope", view.__class__.__name__)
        return f"agent-throttle:{scope}:{self.cache_suffix}:{identity}"

    @staticmethod
    def _resolve_identity(request):
        django_request = getattr(request, "_request", request)
        iam = getattr(django_request, "iam", None)
        if iam is not None and getattr(iam, "is_authenticated", False):
            return f"iam:{getattr(iam, 'username', '') or getattr(iam, 'id', '') or 'anonymous'}"

        user = getattr(django_request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            return f"user:{getattr(user, 'username', '') or getattr(user, 'id', '') or 'anonymous'}"

        remote_addr = django_request.META.get("REMOTE_ADDR")
        if remote_addr:
            return f"ip:{remote_addr}"
        return None


class AgentBurstRateThrottle(AgentBaseRateThrottle):
    rate_attr = "throttle_burst_limit"
    cache_suffix = "burst"
    window_seconds = 10


class AgentSustainedRateThrottle(AgentBaseRateThrottle):
    rate_attr = "throttle_sustained_limit"
    cache_suffix = "sustained"
    window_seconds = 60
