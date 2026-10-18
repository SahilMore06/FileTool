"""Core conversion engine, registry, and runner for FileTool."""

def load_all_engines() -> None:
    """Import all engine modules to ensure all format converters are registered."""
    import filetool.core.engines.archives  # noqa: F401
    import filetool.core.engines.images  # noqa: F401
    import filetool.core.engines.media  # noqa: F401
    import filetool.core.engines.office  # noqa: F401
    import filetool.core.engines.pandoc_docs  # noqa: F401
    import filetool.core.engines.pdf  # noqa: F401
    import filetool.core.engines.spreadsheets  # noqa: F401
    import filetool.core.engines.subtitles  # noqa: F401

load_all_engines()

