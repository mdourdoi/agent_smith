"""Pulls runnable Python out of a model reply.

Different models answer in different shapes, so we try a few: a ```python
block first, then XML / JSON / ReAct tool calls, which we rewrite into an
equivalent Python call. The sandbox then only ever sees Python.
"""
import re
import json
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    code: str
    original_format: str
    warning: str | None


class CodeExtractor:
    def extract(self, reply: str) -> ExtractionResult | None:
        return (self._python(reply)
                or self._xml(reply)
                or self._hermes(reply)
                or self._react(reply))

    def _python(self, text: str) -> ExtractionResult | None:
        match = re.search(r"```python\s*\n(.*?)(?:```|<end_code>)",
                          text, re.DOTALL)
        if match:
            return ExtractionResult(match.group(1).strip(), "python", None)
        match = re.search(r"```python\s*\n(.*)", text, re.DOTALL)
        if match:
            return ExtractionResult(
                match.group(1).strip(), "python",
                "the code block was not closed; recovered it anyway")
        return None

    def _xml(self, text: str) -> ExtractionResult | None:
        match = re.search(r"<invoke\s+name=[\"'](\w+)[\"'](.*?)</invoke>",
                          text, re.DOTALL)
        if not match:
            return None
        params = {
            p.group(1): p.group(2).strip()
            for p in re.finditer(
                r"<parameter\s+name=[\"'](\w+)[\"']>(.*?)</parameter>",
                match.group(2), re.DOTALL)
        }
        return ExtractionResult(self._to_call(match.group(1), params),
                                "xml", None)

    def _hermes(self, text: str) -> ExtractionResult | None:
        match = re.search(r"<tool_call>(.*?)</tool_call>", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return None
        if not data.get("name"):
            return None
        return ExtractionResult(
            self._to_call(data["name"], data.get("arguments", {})),
            "hermes", None)

    def _react(self, text: str) -> ExtractionResult | None:
        match = re.search(r"Action:\s*(\w+)", text)
        if not match:
            return None
        args = {}
        input_match = re.search(r"Action Input:\s*(\{.*?\})", text, re.DOTALL)
        if input_match:
            try:
                args = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                pass
        return ExtractionResult(self._to_call(match.group(1), args),
                                "react", None)

    def _to_call(self, tool_name: str, arguments: dict) -> str:
        kwargs = ", ".join(f"{k}={repr(v)}" for k, v in arguments.items())
        return f"result = {tool_name}({kwargs})\nprint(result)"
