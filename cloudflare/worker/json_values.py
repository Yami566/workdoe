from __future__ import annotations

import asyncio
import json
import math
from contextlib import suppress


class JsonDataError(ValueError):
    pass


async def read_json_response_bytes(response, *, max_bytes: int, max_chunks: int) -> bytes:
    return await read_json_stream_bytes(
        response.body, max_bytes=max_bytes, max_chunks=max_chunks,
        label="Provider response", accepted=response.status == 200,
    )


async def read_json_stream_bytes(stream, *, max_bytes: int, max_chunks: int, label: str, accepted: bool = True) -> bytes:
    if stream is None:
        raise JsonDataError(f"{label} has no body.")
    try:
        from pyodide.ffi import JsException
    except ImportError:
        stream_errors = (OSError,)
    else:
        stream_errors = (OSError, JsException)
    reader = None
    data = bytearray()
    finished = False
    try:
        reader = stream.getReader()
        if not accepted:
            raise JsonDataError(f"{label} was not accepted.")
        for _ in range(max_chunks):
            part = await reader.read()
            if part.done:
                finished = True
                return bytes(data)
            chunk = part.value
            remaining = max_bytes - len(data)
            if int(chunk.byteLength) > remaining:
                raise JsonDataError(f"{label} is too large.")
            converted = bytes(chunk.to_py())
            if len(converted) > remaining:
                raise JsonDataError(f"{label} is too large.")
            data.extend(converted)
        raise JsonDataError(f"{label} has too many chunks.")
    except stream_errors as exc:
        raise JsonDataError(f"{label} could not be read.") from exc
    finally:
        if reader is not None:
            if not finished:
                with suppress(Exception):
                    await asyncio.wait_for(reader.cancel(), timeout=1)
            with suppress(Exception):
                reader.releaseLock()


def _reject_constant(_value: str):
    raise JsonDataError("Non-finite JSON numbers are not supported.")


def _require_unicode_text(text: str) -> None:
    if not text.isascii():
        try:
            text.encode("utf-8")
        except UnicodeError as exc:
            raise JsonDataError("JSON strings must contain valid Unicode.") from exc


def _normalize_values(
    value: object, max_depth: int, *, js_null: object = None, allow_deep_values: bool = False
) -> object:
    if value is js_null:
        return None
    pending = [(value, 1)]
    while pending:
        item, depth = pending.pop()
        if isinstance(item, (dict, list)):
            if depth > max_depth:
                raise JsonDataError("JSON input exceeds the supported nesting depth.")
            children = item.items() if isinstance(item, dict) else enumerate(item)
            for key, child in children:
                if isinstance(key, str):
                    _require_unicode_text(key)
                if child is js_null:
                    item[key] = None
                else:
                    pending.append((child, depth + 1))
        elif isinstance(item, str):
            _require_unicode_text(item)
        elif not allow_deep_values and type(item) is float:
            if not math.isfinite(item):
                raise JsonDataError("Non-finite JSON numbers are not supported.")
        elif not allow_deep_values and item is not None and type(item) not in {str, int, bool}:
            # Containers beyond the FFI conversion budget remain proxies.
            raise JsonDataError("JSON input exceeds the supported nesting depth.")
    return value


def parse_json_value(
    raw: str | bytes, *, max_depth: int = 8, allow_deep_values: bool = False
) -> object:
    if type(max_depth) is not int or not 1 <= max_depth <= 32:
        raise ValueError("JSON conversion depth must be between 1 and 32.")
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    except UnicodeError as exc:
        raise JsonDataError("JSON input is not valid UTF-8.") from exc
    if isinstance(raw, str):
        _require_unicode_text(text)
    try:
        from js import JSON as js_json
        from pyodide.ffi import JsException, jsnull
    except ImportError:
        jsnull = None
        try:
            value = json.loads(text, parse_constant=_reject_constant)
        except (ValueError, RecursionError) as exc:
            raise JsonDataError("JSON input is not valid.") from exc
    else:
        try:
            parsed = js_json.parse(text)
            value = parsed.to_py(depth=max_depth) if hasattr(parsed, "to_py") else parsed
        except (JsException, UnicodeError) as exc:
            raise JsonDataError("JSON input is not valid.") from exc
    return _normalize_values(value, max_depth, js_null=jsnull, allow_deep_values=allow_deep_values)


def normalize_json_value(value: object, *, max_depth: int = 8) -> object:
    """Convert a structured native event value before shared Python validation."""
    if type(max_depth) is not int or not 1 <= max_depth <= 32:
        raise ValueError("JSON conversion depth must be between 1 and 32.")
    try:
        from pyodide.ffi import JsException, jsnull
    except ImportError:
        jsnull = None
        conversion_errors = (TypeError, ValueError, RecursionError)
    else:
        conversion_errors = (JsException, TypeError, ValueError, RecursionError)
    try:
        converter = getattr(value, "to_py", None)
        if callable(converter):
            value = converter(depth=max_depth)
    except conversion_errors:
        raise JsonDataError("Native JSON value could not be converted.") from None
    return _normalize_values(value, max_depth, js_null=jsnull)
