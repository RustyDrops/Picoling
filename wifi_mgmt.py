# wifi_mgmt.py — WiFi connection, NTP sync, DNS cache
import network
import ntptime
import uasyncio as asyncio
import socket
from secrets import WIFI_SSID, WIFI_PASS

# DNS monkey-patch removed (built-in modules are read-only on Pico 2W)



def prime_dns_cache():
    pass


def invalidate_dns_cache():
    pass


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
