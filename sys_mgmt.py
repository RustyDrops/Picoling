# sys_mgmt.py — System management for Pico 2W stability
import machine

def lock_system_frequency():
    """Lock CPU to 150MHz. The Pico 2W CYW43 WiFi driver relies on
    stable PIO timing. Dynamic frequency scaling causes bus jitter
    and random shutoff crashes. Fixed 150MHz is the safest."""
    machine.freq(150_000_000)
    print("CPU: Locked to 150MHz")
