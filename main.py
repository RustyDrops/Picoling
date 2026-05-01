# main.py — Picoling: Boot sequence and master event loop
import micropython
import machine
import gc
import time
import uasyncio as asyncio

# Optimize MicroPython for production
micropython.opt_level(2)


def main():
    """Boot sequence for Picoling."""
    print("\n=== Picoling ===")
    print("Initializing...")

    # 1. Lock CPU frequency for WiFi stability
    from sys_mgmt import lock_system_frequency
    lock_system_frequency()

    # 2. Start watchdog timer (8.3 second timeout)
    wdt = machine.WDT(timeout=8300)
    wdt.feed()

    # 3. Initialize memory (load state from flash to RAM)
    from memory import init_memory
    init_memory()
    wdt.feed()
    gc.collect()

    print(f"RAM: {gc.mem_free() // 1024}KB free")

    # 4. Connect WiFi + NTP + DNS cache
    async def _boot_wifi():
        from wifi_mgmt import connect_wifi_and_sync_time
        await connect_wifi_and_sync_time(wdt)

    asyncio.run(_boot_wifi())
    wdt.feed()
    gc.collect()

    print(f"RAM after WiFi: {gc.mem_free() // 1024}KB free")

    # 5. Send boot notification
    from telegram_bot import send_telegram_msg
    ram_kb = gc.mem_free() // 1024
    
    if not memory.is_onboarding_complete():
        # Hardware Flex
        try:
            import machine
            sensor = machine.ADC(4)
            voltage = sensor.read_u16() * 3.3 / 65535
            temp_c = 27 - (voltage - 0.706) / 0.001721
            temp_str = f"running at a cool {temp_c:.1f}°C"
        except:
            temp_str = "feeling fine"
            
        send_telegram_msg(f"System boot complete. Sensors online. Ah, {ram_kb}KB of RAM... it's cozy in here. CPU is {temp_str}. Hello... is anyone there?")
    else:
        identity = memory.get_identity()
        send_telegram_msg(f"{identity['emoji']} {identity['name']}: ONLINE | {ram_kb}KB RAM | ~help")
        
    wdt.feed()

    # 6. Start Core 1 background worker
    from horizon import start_background_worker
    start_background_worker()
    wdt.feed()

    print(f"RAM after Horizon: {gc.mem_free() // 1024}KB free")

    # 7. Create required directories
    import uos
    for d in ("skills", "data", "data/human_queue"):
        try:
            uos.mkdir(d)
        except OSError:
            pass

    # 8. Start main async event loop (Core 0)
    print("Starting event loop...")
    asyncio.run(_event_loop(wdt))


async def _event_loop(wdt):
    """Main async event loop on Core 0."""
    from poller import poll_loop

    while True:
        try:
            await poll_loop(wdt)
        except Exception as e:
            print(f"[MAIN] Fatal: {e}")
            # Flush state before reset
            try:
                from memory import flush_to_flash
                flush_to_flash()
            except:
                pass
            # Brief delay then hard reset
            from telegram_bot import send_telegram_msg
            send_telegram_msg(f"CRASH: {str(e)[:100]}. Rebooting...")
            time.sleep(5)
            machine.reset()


# Auto-run on boot
try:
    main()
except Exception as e:
    print(f"BOOT FAILURE: {e}")
    time.sleep(10)
    machine.reset()
