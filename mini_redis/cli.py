"""Interactive command-line interface for Mini Redis."""

from typing import Callable, Optional

from .command_processor import CommandProcessor


def run_repl(
    processor: Optional[CommandProcessor] = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    """Read and execute commands until exit, EOF, or keyboard interrupt."""
    active_processor = processor if processor is not None else CommandProcessor()
    while True:
        try:
            line = input_fn("mini-redis> ")
        except (EOFError, KeyboardInterrupt):
            return
        response = active_processor.execute(line)
        if response is not None:
            output_fn(response)
        if active_processor.should_exit:
            return
