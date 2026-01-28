VERSION = (26, 1, 1, "")

__version_info__ = VERSION
__version__ = ".".join(map(str, VERSION[:3])) + (f"-{VERSION[3]}" if VERSION[3] else "")
