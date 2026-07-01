import re
import json
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    code: str
    original_format: str  # "python", "xml", "hermes", "react"
    warning: str | None


class CodeExtractor:
    def extract(self, llm_response: str) -> ExtractionResult | None:
        return (
            self._try_python(llm_response)
            or self._try_xml(llm_response)
            or self._try_hermes(llm_response)
            or self._try_react(llm_response)
        )

    def _try_python(self, text: str) -> ExtractionResult | None:
        match = re.search(
            r"```python\s*\n(.*?)(?:```|<end_code>)",
            text,
            re.DOTALL)
        if match:
            return ExtractionResult(match.group(1).strip(), "python", None)

        # Malformed: missing closing tag, recover anyway.
        match = re.search(r"```python\s*\n(.*)", text, re.DOTALL)
        if match:
            return ExtractionResult(
                match.group(1).strip(),
                "python",
                "Unclosed code block - closing ``` was missing, "
                "recovered anyway.")
        return None

    def _try_xml(self, text: str) -> ExtractionResult | None:
        match = re.search(
            r"<invoke\s+name=[\"'](\w+)[\"'](.*?)</invoke>",
            text,
            re.DOTALL)
        if not match:
            return None
        tool_name = match.group(1)
        params = {
            p.group(1): p.group(2).strip()
            for p in re.finditer(
                r"<parameter\s+name=[\"'](\w+)[\"']>(.*?)</parameter>",
                match.group(2), re.DOTALL
            )
        }
        return ExtractionResult(
            self._to_python(
                tool_name,
                params),
            "xml",
            None)

    def _try_hermes(self, text: str) -> ExtractionResult | None:
        match = re.search(r"<tool_call>(.*?)</tool_call>", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return None
        tool_name = data.get("name", "")
        if not tool_name:
            return None
        return ExtractionResult(
            self._to_python(
                tool_name,
                data.get(
                    "arguments",
                    {})),
            "hermes",
            None)

    def _try_react(self, text: str) -> ExtractionResult | None:
        match = re.search(r"Action:\s*(\w+)", text)
        if not match:
            return None
        tool_name = match.group(1)
        args = {}
        input_match = re.search(r"Action Input:\s*(\{.*?\})", text, re.DOTALL)
        if input_match:
            try:
                args = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                pass
        return ExtractionResult(
            self._to_python(
                tool_name,
                args),
            "react",
            None)

    def _to_python(self, tool_name: str, arguments: dict) -> str:
        kwargs = ", ".join(f"{k}={repr(v)}" for k, v in arguments.items())
        return f"result = {tool_name}({kwargs})\nprint(result)"
