# skills/sys_info.py — System health report
import gc
import machine
import uos


def tool_system_report():
    """Generate a comprehensive system health report."""
    # RAM
    gc.collect()
    ram_free = gc.mem_free()
    ram_alloc = gc.mem_alloc()
    ram_total = ram_free + ram_alloc
    ram_pct = (ram_free / ram_total * 100) if ram_total > 0 else 0

    # CPU Temperature
    try:
        sensor = machine.ADC(4)
        reading = sensor.read_u16()
        voltage = reading * 3.3 / 65535
        temp_c = 27 - (voltage - 0.706) / 0.001721
        temp_str = f"{temp_c:.1f}C"
    except:
        temp_str = "N/A"

    # CPU frequency
    freq_mhz = machine.freq() // 1_000_000

    # Flash usage (approximate)
    try:
        fs_stat = uos.statvfs("/")
        block_size = fs_stat[0]
        total_blocks = fs_stat[2]
        free_blocks = fs_stat[3]
        flash_total = (block_size * total_blocks) // 1024
        flash_free = (block_size * free_blocks) // 1024
        flash_used = flash_total - flash_free
        flash_str = f"{flash_used}KB / {flash_total}KB"
    except:
        flash_str = "N/A"

    # Uptime (rough, from time module)
    import time
    t = time.localtime()
    time_str = f"{t[3]:02d}:{t[4]:02d}:{t[5]:02d}"

    # Skills count
    try:
        skills = [f for f in uos.listdir("skills") if f.endswith(".py")]
        skills_count = len(skills)
    except:
        skills_count = 0

    report = (
        f"=== System Report ===\n"
        f"RAM: {ram_free // 1024}KB free / {ram_total // 1024}KB ({ram_pct:.0f}% free)\n"
        f"Flash: {flash_str}\n"
        f"CPU: {freq_mhz}MHz | Temp: {temp_str}\n"
        f"Time: {time_str}\n"
        f"Skills: {skills_count} installed"
    )
    return report
