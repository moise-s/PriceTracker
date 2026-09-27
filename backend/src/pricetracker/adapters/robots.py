"""robots.txt parsing and matching per RFC 9309.

Supports user-agent groups, ``Allow``/``Disallow`` with ``*`` and ``$`` wildcards,
and longest-match precedence (``Allow`` wins ties). Python's ``urllib.robotparser``
does not implement wildcards, which several supermarket sites rely on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit


@dataclass(frozen=True)
class Rule:
    allow: bool
    pattern: str
    regex: re.Pattern[str]

    @property
    def length(self) -> int:
        return len(self.pattern)


@dataclass
class RobotsPolicy:
    groups: dict[str, list[Rule]] = field(default_factory=dict)
    allow_all: bool = False
    disallow_all: bool = False
    source_status: int | None = None

    def rules_for(self, agent: str) -> list[Rule]:
        agent = agent.lower()
        best_name = ""
        for name in self.groups:
            if name != "*" and name in agent and len(name) > len(best_name):
                best_name = name
        if best_name:
            return self.groups[best_name]
        return self.groups.get("*", [])

    def is_allowed(self, url: str, agent: str) -> bool:
        if self.allow_all:
            return True
        if self.disallow_all:
            return False
        parts = urlsplit(url)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        path = _normalize_path(path)
        if path == "/robots.txt":
            return True
        matches = [rule for rule in self.rules_for(agent) if rule.regex.match(path)]
        if not matches:
            return True
        best = max(matches, key=lambda r: (r.length, r.allow))
        return best.allow

    def matching_rule(self, url: str, agent: str) -> str | None:
        parts = urlsplit(url)
        path = _normalize_path((parts.path or "/") + (("?" + parts.query) if parts.query else ""))
        matches = [rule for rule in self.rules_for(agent) if rule.regex.match(path)]
        if not matches:
            return None
        best = max(matches, key=lambda r: (r.length, r.allow))
        return ("Allow: " if best.allow else "Disallow: ") + best.pattern


def _normalize_path(path: str) -> str:
    # Percent-decode unreserved characters for comparison, keep the rest as-is.
    return unquote(path)


def _compile(pattern: str) -> re.Pattern[str]:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in _normalize_path(body))
    return re.compile(regex + ("$" if anchored else ""))


def parse_robots(text: str, status: int = 200) -> RobotsPolicy:
    """Parse robots.txt. 4xx -> allow all; 5xx/unreachable -> disallow all (RFC 9309 §2.3.1)."""
    if 400 <= status < 500:
        return RobotsPolicy(allow_all=True, source_status=status)
    if status >= 500 or status == 0:
        return RobotsPolicy(disallow_all=True, source_status=status)
    groups: dict[str, list[Rule]] = {}
    current_agents: list[str] = []
    last_was_agent = False
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if not last_was_agent:
                current_agents = []
            agent = value.lower()
            current_agents.append(agent)
            groups.setdefault(agent, [])
            last_was_agent = True
            continue
        last_was_agent = False
        if key in ("allow", "disallow") and current_agents:
            if not value:
                continue  # "Disallow:" with empty value allows everything
            rule = Rule(allow=key == "allow", pattern=value, regex=_compile(value))
            for agent in current_agents:
                groups[agent].append(rule)
    return RobotsPolicy(groups=groups, source_status=status)
