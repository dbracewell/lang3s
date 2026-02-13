def format_duration(start_time: float, end_time: float) -> str:
    total_seconds = int(end_time - start_time)

    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
