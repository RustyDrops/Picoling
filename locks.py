# locks.py — Centralized cross-core resource locks
import _thread

# Serializes all WiFi/Socket communication.
# Prevents Core 0 poller and Core 1 Flex worker from
# using the CYW43 radio simultaneously (causes crashes).
net_lock = _thread.allocate_lock()

# Protects shared RAM data structures:
# journal[], state{}, soul{}, current_task, dirty_flags{}
state_lock = _thread.allocate_lock()
