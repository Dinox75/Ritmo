"""Analisa mudanças observadas, sem classificar a pessoa ou seu foco."""

from collections import deque
from datetime import datetime, timedelta, timezone


class WindowSwitchAnalyzer:
    def __init__(self, observation_seconds=60, alert_switches=4):
        self.window = timedelta(seconds=observation_seconds)
        self.alert_switches = alert_switches
        self.changes = deque()
        self.last_key = None
        self.alerting = False

    def observe(self, key, at=None):
        at = at or datetime.now(timezone.utc)
        if key == self.last_key:
            return None
        self.last_key = key
        self.changes.append(at)
        while self.changes and at - self.changes[0] > self.window:
            self.changes.popleft()
        switches = max(0, len(self.changes) - 1)
        if switches < self.alert_switches:
            self.alerting = False
            return None
        if self.alerting:
            return None
        self.alerting = True
        return {"switches": switches, "observation_seconds": int(self.window.total_seconds())}
