"""Intervalos de programas observados; nunca somados ao tempo de estudo."""

from datetime import datetime, timezone


class UsageAggregator:
    def __init__(self):
        self.program = None
        self.started = None

    def change(self, program, at=None):
        at = at or datetime.now(timezone.utc)
        previous = self.close(at)
        self.program, self.started = program, at
        return previous

    def close(self, at=None):
        at = at or datetime.now(timezone.utc)
        if self.program is None:
            return []
        result = [{"programa": self.program, "started_at": self.started.isoformat(),
                   "ended_at": at.isoformat(),
                   "seconds": max(0, (at - self.started).total_seconds())}]
        self.program, self.started = None, None
        return result
