from db import get_setting_raw, set_setting_raw

OUTPUT_FORMATS = ["markdown", "html", "text", "json"]


def get_setting(key: str, default=None):
    val = get_setting_raw(key)
    return val if val is not None else default


def set_setting(key: str, value: str):
    set_setting_raw(key, value)


def get_default_output_format() -> str:
    return get_setting("default_output_format", "markdown")


def set_default_output_format(fmt: str):
    if fmt in OUTPUT_FORMATS:
        set_setting("default_output_format", fmt)
