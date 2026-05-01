# wifi_mgmt.py — WiFi connection, NTP sync, DNS cache
import network
import ntptime
import uasyncio as asyncio
import socket
from secrets import WIFI_SSID, WIFI_PASS

# DNS monkey-patch: cache Gemini API IP to save ~200ms per call
_original_getaddrinfo = socket.getaddrinfo
_cached_ip = None

def _cached_getaddrinfo(host, port, family=0, socktype=0, proto=0, flags=0):
    global _cached_ip
    if host == "generativelanguage.googleapis.com" and _cached_ip:
        return [(2, 1, 0, '', (_cached_ip, port))]
    return _original_getaddrinfo(host, port, family, socktype, proto, flags)

socket.getaddrinfo = _cached_getaddrinfo


def prime_dns_cache():
    """Resolve Gemini API IP once and cache it."""
    global _cached_ip
    try:
        info = _original_getaddrinfo("generativelanguage.googleapis.com", 443)
        _cached_ip = info[0][-1][0]
        print(f"DNS: Cached {_cached_ip}")
    except Exception as e:
        print(f"DNS: Resolution failed: {e}")


def invalidate_dns_cache():
    """Force a fresh DNS lookup on next request."""
    global _cached_ip
    _cached_ip = None


async def connect_wifi_and_sync_time(wdt):
    """Connect to WiFi, sync NTP, and prime DNS cache."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)

    retries = 0
    while not wlan.isconnected():
        wdt.feed()
        retries += 1
        if retries > 30:
            print("WiFi: Connection failed after 30s")
            import machine
            machine.reset()
        await asyncio.sleep(1)

    print(f"WiFi: Connected — {wlan.ifconfig()[0]}")

    # Sync RTC with NTP
    try:
        ntptime.settime()
        print("NTP: Time synced")
    except Exception as e:
        print(f"NTP: Sync failed: {e}")

    # Prime the DNS cache
    prime_dns_cache()
