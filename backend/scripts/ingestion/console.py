"""Tiny logging helper shared across the ingestion pipeline."""


def log(message: str) -> None:
    """Print a pipeline progress line, flushed so worker output stays ordered."""
    print(message, flush=True)
