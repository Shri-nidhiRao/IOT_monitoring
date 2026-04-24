def format_seconds_ms(val_str):
    if not val_str or val_str == '--': return '--'
    try:
        f = float(val_str)
        return f"{int(f):02d}:{int(round((f % 1) * 1000)):03d}"
    except ValueError:
        pass
    val_str = str(val_str).strip()
    parts = val_str.split(':')
    if len(parts) == 3:
        try:
            return f"{int(parts[2]):02d}:000"
        except: pass
    if len(parts) == 2:
        try:
            return f"{int(parts[0]):02d}:{int(parts[1]):03d}"
        except: pass
    return val_str

print(f"format_seconds_ms('00:00:5') -> {format_seconds_ms('00:00:5')}")
print(f"format_seconds_ms('6.0') -> {format_seconds_ms('6.0')}")
print(f"format_seconds_ms('11:30') -> {format_seconds_ms('11:30')}")
