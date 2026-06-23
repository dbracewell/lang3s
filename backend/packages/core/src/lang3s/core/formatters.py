def format_seconds(total_seconds: float) -> str:
    total_seconds = int(total_seconds)

    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_duration(start_time: float, end_time: float) -> str:
    return format_seconds(end_time - start_time)
