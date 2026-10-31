"""Conservative pre-dispatch reservations; estimates are not billing guarantees."""
import json
from copy import deepcopy
import math
import threading
import time


class BudgetExceeded(RuntimeError):
    pass


class Deadline:
    """Shared elapsed-time gate; subprocesses receive the remaining duration.

    This cannot preempt arbitrary Python callbacks or the trusted local REPL.
    Untrusted host execution still requires a separate process/OS boundary.
    """
    def __init__(self, seconds):
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('Deadline must be finite and positive')
        self.seconds = seconds
        self.started = time.monotonic()
        self.stop_reason = None
        self.lock = threading.RLock()

    def _stop(self, reason):
        self.stop_reason = reason
        raise BudgetExceeded(reason)

    def remaining(self, cap=None, *, minimum=0.001):
        with self.lock:
            if self.stop_reason:
                raise BudgetExceeded(self.stop_reason)
            duration = self.seconds - (time.monotonic() - self.started)
            if duration < minimum:
                self._stop('Wall time exhausted')
            return min(duration, cap) if cap is not None else duration


class CallBudget(Deadline):
    def __init__(self, limits, rates):
        if not isinstance(limits, dict):
            raise ValueError("Budget limits must be an object")
        self.limits = dict(limits)
        for key in ("max_calls", "max_output_tokens", "max_input_bytes"):
            if type(limits.get(key)) is not int or limits[key] < 1:
                raise ValueError(f"{key} must be a positive integer")
        for key in ("max_wall_seconds", "max_cost_usd"):
            if type(limits.get(key)) not in (int, float) or not math.isfinite(limits[key]) or limits[key] < 0:
                raise ValueError(f"{key} must be finite and nonnegative")
        if (limits["max_wall_seconds"] <= 0 or any(type(limits.get(k)) is not int for k in ("max_concurrency", "max_depth", "max_repairs")) or
                limits.get("max_concurrency") != 1 or limits.get("max_depth") != 1 or not 0 <= limits.get("max_repairs") <= 10):
            raise ValueError("Adapter requires positive wall time, concurrency/depth=1 and repairs from 0 to 10")
        self.rates = deepcopy(rates)
        if not isinstance(rates, dict) or not rates:
            raise ValueError("Explicit model pricing estimates are required")
        for pricing in rates.values():
            if not isinstance(pricing, dict):
                raise ValueError("Each model needs a pricing object")
            for field in ("input_per_million", "output_per_million"):
                value = pricing.get(field)
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                    raise ValueError("Pricing rates must be finite and nonnegative")
        super().__init__(limits['max_wall_seconds'])
        self.calls = self.output_reserved = self.input_bytes = 0
        self.cost_reserved = 0.0

    def reserve(self, model, messages, output_cap):
        with self.lock:
            return self._reserve(model, messages, output_cap)

    def _stop(self, reason):
        self.stop_reason = reason
        raise BudgetExceeded(reason)

    def _reserve(self, model, messages, output_cap):
        if self.stop_reason:
            raise BudgetExceeded(self.stop_reason)
        if type(output_cap) is not int or output_cap <= 0:
            raise ValueError("Output cap must be a positive integer")
        if model not in self.rates:
            self._stop("Unconfigured model")
        if time.monotonic() - self.started >= self.limits["max_wall_seconds"]:
            self._stop("Wall time exhausted")
        size = len(json.dumps(messages, ensure_ascii=False).encode())
        rates = self.rates[model]
        # Byte count plus framing allowance is a deliberately conservative estimate
        # for text-only requests; opaque provider reasoning/hidden tokens are excluded.
        estimate = ((size + 1024) * rates["input_per_million"] + output_cap * rates["output_per_million"]) / 1_000_000
        if (self.calls + 1 > self.limits["max_calls"] or
                self.output_reserved + output_cap > self.limits["max_output_tokens"] or
                self.input_bytes + size > self.limits["max_input_bytes"] or
                self.cost_reserved + estimate > self.limits["max_cost_usd"] + 1e-12):
            self._stop("Call, token, input or estimated cost budget exhausted")
        self.calls += 1
        self.output_reserved += output_cap
        self.input_bytes += size
        self.cost_reserved += estimate
        return estimate
