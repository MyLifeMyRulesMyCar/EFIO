# UPDATED: Use thread-safe implementation with a compatibility wrapper

from efio_daemon.thread_safe_state import state as _thread_state
import warnings


class StateCompatWrapper:
    """
    Compatibility wrapper for gradual migration.

    Dict-like access is deprecated but still supported to avoid
    breaking existing code during migration. Prefer using the
    thread-safe API on the `state` object (e.g. `state.get_di()`).
    """

    def __init__(self, thread_safe_state):
        self._state = thread_safe_state

    def __getitem__(self, key):
        if key == "di":
            return self._state.get_di()
        elif key == "do":
            return self._state.get_do()
        elif key == "simulation":
            return self._state.get_simulation()
        elif key == "simulation_oled":
            return self._state.get_simulation_oled()
        elif key == "modbus":
            return self._state.get_modbus()
        else:
            raise KeyError(f"Unknown state key: {key}")

    def __setitem__(self, key, value):
        warnings.warn(
            f"Dict-style access state['{key}'] is deprecated. Use the thread-safe API instead.",
            DeprecationWarning,
            stacklevel=2
        )

        if key == "di":
            self._state.set_di_all(value)
        elif key == "do":
            self._state.set_do_all(value)
        elif key == "simulation":
            self._state.set_simulation(value)
        elif key == "simulation_oled":
            self._state.set_simulation_oled(value)
        elif key == "modbus":
            for k, v in value.items():
                self._state.set_modbus(k, v)
        else:
            raise KeyError(f"Unknown state key: {key}")

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __getattr__(self, name):
        return getattr(self._state, name)


# Export wrapped state for backward compatibility
state = StateCompatWrapper(_thread_state)
