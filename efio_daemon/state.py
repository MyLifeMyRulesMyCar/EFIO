#!/usr/bin/env python3
# efio_daemon/state.py
# FIXED: Better compatibility wrapper supporting element-level access

from efio_daemon.thread_safe_state import state as _thread_state
import warnings


class ListProxy:
    """
    Proxy for list-like access to di/do arrays.
    
    Allows: state["di"][0] = 1
    Instead of: state.set_di(0, 1)
    """
    def __init__(self, state_obj, key):
        self._state = state_obj
        self._key = key
    
    def __getitem__(self, index):
        if self._key == "di":
            return self._state.get_di(index)
        elif self._key == "do":
            return self._state.get_do(index)
        else:
            raise KeyError(f"Unknown key: {self._key}")
    
    def __setitem__(self, index, value):
        warnings.warn(
            f"Dict-style access state['{self._key}'][{index}] is deprecated. "
            f"Use state.set_{self._key}({index}, {value}) instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        if self._key == "di":
            self._state.set_di(index, value)
        elif self._key == "do":
            self._state.set_do(index, value)
        else:
            raise KeyError(f"Unknown key: {self._key}")
    
    def copy(self):
        """Support .copy() for backward compatibility"""
        if self._key == "di":
            return self._state.get_di()
        elif self._key == "do":
            return self._state.get_do()
        else:
            raise KeyError(f"Unknown key: {self._key}")
    
    def __iter__(self):
        """Support iteration"""
        if self._key == "di":
            return iter(self._state.get_di())
        elif self._key == "do":
            return iter(self._state.get_do())
        else:
            raise KeyError(f"Unknown key: {self._key}")
    
    def __len__(self):
        """Support len()"""
        return 4  # Always 4 channels


class StateCompatWrapper:
    """
    Compatibility wrapper for gradual migration.
    
    Supports both old dict-style and new thread-safe API:
    
    OLD (still works, but deprecated):
        state["di"][0] = 1
        state["do"][2] = 0
    
    NEW (recommended):
        state.set_di(0, 1)
        state.set_do(2, 0)
    """
    
    def __init__(self, thread_safe_state):
        self._state = thread_safe_state
    
    def __getitem__(self, key):
        if key == "di":
            return ListProxy(self._state, "di")
        elif key == "do":
            return ListProxy(self._state, "do")
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
            f"Dict-style access state['{key}'] is deprecated. "
            f"Use the thread-safe API instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        if key == "di":
            if isinstance(value, list):
                self._state.set_di_all(value)
            else:
                raise ValueError("Must set entire di array: state.set_di_all([...])")
        elif key == "do":
            if isinstance(value, list):
                self._state.set_do_all(value)
            else:
                raise ValueError("Must set entire do array: state.set_do_all([...])")
        elif key == "simulation":
            self._state.set_simulation(value)
        elif key == "simulation_oled":
            self._state.set_simulation_oled(value)
        elif key == "modbus":
            if isinstance(value, dict):
                for k, v in value.items():
                    self._state.set_modbus(k, v)
            else:
                raise ValueError("modbus must be a dict")
        else:
            raise KeyError(f"Unknown state key: {key}")
    
    def get(self, key, default=None):
        """Dict-style .get() with default"""
        try:
            return self[key]
        except KeyError:
            return default
    
    def __contains__(self, key):
        """Support 'in' operator"""
        return key in ["di", "do", "simulation", "simulation_oled", "modbus"]
    
    # Forward all other attributes to underlying state
    def __getattr__(self, name):
        return getattr(self._state, name)


# Export wrapped state for backward compatibility
state = StateCompatWrapper(_thread_state)