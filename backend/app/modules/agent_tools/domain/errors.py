"""Errors raised inside tool handlers. Messages are safe to show to the LLM and the user."""


class ToolInputError(Exception):
    """The arguments were well-formed but refer to something that does not exist (e.g. unknown department)."""
