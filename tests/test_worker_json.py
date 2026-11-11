from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock

PATH = Path(__file__).resolve().parents[1] / "cloudflare" / "worker" / "json_values.py"


def load_decoder():
    spec = importlib.util.spec_from_file_location("worker_json_test", PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BoundedJsonTests(unittest.TestCase):
    def test_supported_nested_data_and_bracket_text_round_trip(self):
        module = load_decoder()
        value = {"scope": {"answers": ["one", "two"]}, "text": 'Literal [brackets] and "quotes"'}
        self.assertEqual(module.parse_json_value(json.dumps(value)), value)
        self.assertEqual(module.parse_json_value(b'{"value":null}'), {"value": None})

    def test_depth_boundary_and_nonfinite_input_fail_closed(self):
        module = load_decoder()
        value = {"leaf": "valid"}
        for _ in range(7):
            value = {"child": value}
        self.assertEqual(module.parse_json_value(json.dumps(value)), value)
        cases = (
            json.dumps({"child": value}), "[" * 3000 + "0" + "]" * 3000,
            '{"value":NaN}', '{"value":Infinity}', '{"value":1e999}', b"\xff",
        )
        for index, raw in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(module.JsonDataError):
                module.parse_json_value(raw)
        for depth in (-1, 0, 33, True):
            with self.subTest(depth=depth), self.assertRaises(ValueError):
                module.parse_json_value("{}", max_depth=depth)

    def test_valid_unicode_and_literal_escape_text_are_preserved(self):
        module = load_decoder()
        value = {"\U0001d11e": "Caf\u00e9 \U0001d11e", "literal": r"\ud800"}
        for ensure_ascii in (True, False):
            with self.subTest(ensure_ascii=ensure_ascii):
                raw = json.dumps(value, ensure_ascii=ensure_ascii).encode("utf-8")
                self.assertEqual(module.parse_json_value(raw), value)
        self.assertEqual(module.normalize_json_value(value), value)

    def test_unpaired_surrogates_are_rejected_in_json_keys_values_and_queue_objects(self):
        module = load_decoder()
        for raw in (
            br'"\ud800"', br'{"\udfff":null}', br'{"scope":{"notes":["value\ud800"]}}',
            br'{"text":"\ud800 \udfff"}', '"\ud800"',
        ):
            with self.subTest(raw=repr(raw)), self.assertRaisesRegex(module.JsonDataError, "valid Unicode"):
                module.parse_json_value(raw)
        for value in ({"\udfff": None}, {"scope": ["value\ud800"]}):
            with self.subTest(value=value), self.assertRaisesRegex(module.JsonDataError, "valid Unicode"):
                module.normalize_json_value(value)

    def test_native_conversion_is_bounded_and_never_coerces_opaque_values(self):
        module = load_decoder()
        depths = []

        class Opaque:
            def __str__(self):
                raise AssertionError("Do not coerce untrusted proxy fields.")

        class NativeValue:
            def to_py(self, *, depth):
                depths.append(depth)
                return {"metadata": Opaque()}

        class NativeError(Exception):
            pass

        js = ModuleType("js")
        js.JSON = SimpleNamespace(parse=lambda raw: NativeValue())
        ffi = ModuleType("pyodide.ffi")
        ffi.JsException = NativeError
        ffi.jsnull = object()
        with mock.patch.dict(sys.modules, {"js": js, "pyodide.ffi": ffi}):
            with self.assertRaises(module.JsonDataError):
                module.parse_json_value("{}")
            shallow = module.parse_json_value("{}", max_depth=1, allow_deep_values=True)
            self.assertIsInstance(shallow["metadata"], Opaque)
        self.assertEqual(depths, [8, 1])

    def test_native_nulls_normalize_at_root_and_nested_without_string_coercion(self):
        module = load_decoder()
        sentinel = object()
        opaque = object()

        class NativeValue:
            def to_py(self, *, depth):
                if depth == 1:
                    return {"optional": sentinel, "nested": opaque}
                return {"optional": sentinel, "nested": [sentinel, {"value": sentinel}]}

        js = ModuleType("js")
        js.JSON = SimpleNamespace(parse=lambda raw: sentinel if raw == "null" else NativeValue())
        ffi = ModuleType("pyodide.ffi")
        ffi.JsException = type("NativeError", (Exception,), {})
        ffi.jsnull = sentinel
        with mock.patch.dict(sys.modules, {"js": js, "pyodide.ffi": ffi}):
            self.assertIsNone(module.parse_json_value("null"))
            expected = {"optional": None, "nested": [None, {"value": None}]}
            self.assertEqual(module.parse_json_value("{}"), expected)
            shallow = module.parse_json_value("{}", max_depth=1, allow_deep_values=True)
            self.assertIsNone(shallow["optional"])
            self.assertIs(shallow["nested"], opaque)


if __name__ == "__main__":
    unittest.main()
