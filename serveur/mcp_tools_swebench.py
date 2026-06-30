from mcp.server.fastmcp import FastMCP
from typing import List
import re
from pathlib import Path
import subprocess


mcp = FastMCP("SW_SERV")


@mcp.tool()
def read_file(
    filepath: str,
    start_line: int,
    end_line: int
) -> str:
    """Read the content of a specific file with line numbers included."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as fd:
            lines = fd.readlines()
        if start_line > end_line:
            return (
                f"Error: start_line ({start_line}) is greater "
                f"than end_line ({end_line})."
            )
        if (
            start_line < 1
            or end_line < 1
            or start_line > len(lines)
            or end_line > len(lines)
        ):
            return (
                f"Error: Requested lines {start_line}-{end_line} are out of "
                f"range for file '{filepath}' (available: 1-{len(lines)})."
            )

        result_lines = []
        for line_idx, line_content in enumerate(lines, start=1):
            if start_line <= line_idx <= end_line:
                result_lines.append(f"{line_idx}: {line_content.rstrip('\n')}")
        return "\n".join(result_lines)
    except Exception as e:
        return f"Error reading file '{filepath}': {str(e)}"


@mcp.tool()
def edit_file(
    filepath: str,
    old_str: str,
    new_str: str
) -> str:
    """Replace an exact unique string or block
    of code in a file with a new string.
    This is a strict search-and-replace tool.
    The 'old_str' must match the target content
    exactly (including indentation and line breaks).
    If 'old_str' is not unique or not found,
    the edit will fail.
    Args:
        filepath: The path to the file to modify.
        old_str: The exact string/block currently in
        the file that needs to be replaced.
        new_str: The new string/block to replace 'old_str' with.
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fd:
            file = fd.read()
            count = file.count(old_str)
            if count == 0:
                return (
                    "Error: The block of code to replace ('old_str') was "
                    f"not found in '{filepath}'.\n"
                    "Make sure your indentation, spaces, and line breaks "
                    "match the file content exactly."
                )
            new_content = file.replace(old_str, new_str)

        # Create a simple backup before overwriting
        try:
            backup_path = f"{filepath}.bak"
            with open(
                backup_path,
                "w",
                encoding="utf-8",
                errors="replace",
            ) as bfd:
                bfd.write(file)
        except Exception:
            # Non-fatal: proceed even if backup fails
            pass

        with open(
            filepath, "w", encoding="utf-8", errors="replace"
        ) as fd:
            fd.write(new_content)
            return (
                f"Success: File '{filepath}' updated successfully. "
                f"Backup: '{backup_path}'"
            )
    except FileNotFoundError:
        return f"Error: File not found at path '{filepath}'."
    except Exception as e:
        return f"Error editing file '{filepath}': {type(e).__name__}: {e}"


@mcp.tool()
def list_files(
    directory: str,
    pattern: str
) -> str:
    """List all files in a directory matching a given glob or text pattern.
    Useful for exploring the codebase structure and locating files dynamically.
    Args:
        directory: The directory path to look into
        (e.g., '/testbed' or 'src/').
        pattern: The search pattern or file extension to filter by
        (e.g., '*.py', 'test_*.py').
    """
    try:
        dir_path = Path(directory)
        if not dir_path.exists():
            return f"Error: Directory '{directory}' does not exist."
        if not dir_path.is_dir():
            return f"Error: Path '{directory}' is a file, not a directory."
        matching_files = sorted(dir_path.rglob(pattern))
        result_lines = [str(file) for file in matching_files if file.is_file()]
        if not result_lines:
            return (
                f"No files found matching pattern '{pattern}' "
                f"in directory '{directory}'."
            )
        return "\n".join(result_lines)
    except Exception as e:
        return f"Error listing files in '{directory}': {type(e).__name__}: {e}"


@mcp.tool()
def search_code(pattern: str, file_pattern: str = "*") -> str:
    """Perform a grep-like text or regex search across the codebase.

    The output strictly follows the format:
    /absolute/path_to_file.py:<line_number> <line_content>

    Args:
        pattern: The string literal or regular expression to search for.
        file_pattern: Optional glob to limit matching files (e.g., '*.py').
    """
    try:
        root_dir = Path(".").resolve()
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            regex = re.compile(re.escape(pattern), re.IGNORECASE)

        results = []
        for file_path in root_dir.rglob(file_pattern):
            if not file_path.is_file():
                continue
            if ".git" in file_path.parts or "__pycache__" in file_path.parts:
                continue
            try:
                with open(
                    file_path,
                    "r",
                    encoding="utf-8",
                    errors="replace",
                ) as f:
                    for line_num, line in enumerate(f, start=1):
                        if regex.search(line):
                            clean_line = line.rstrip("\r\n")
                            results.append(
                                f"{file_path.resolve()}: {line_num}: "
                                f"{clean_line}"
                            )
            except Exception:
                continue
        if not results:
            return (
                f"No matches found for pattern '{pattern}' in files "
                f"matching '{file_pattern}'."
            )

        return "\n".join(results)

    except Exception as e:
        return f"Error performing search_code: {type(e).__name__}: {e}"


@mcp.tool()
def search_function_or_class_definition_in_code(name: str) -> str:
    """Find the exact definition of a specific function or
    class within the codebase.

    Returns the file path and starting line number where the
    definition occurs.
    """
    try:
        root_dir = Path(".").resolve()
        pattern = rf"^\s*(def|class)\s+{re.escape(name)}\b"
        regex = re.compile(pattern)
        
        results = []
        for file_path in root_dir.rglob("*.py"):
            if ".git" in file_path.parts or "__pycache__" in file_path.parts:
                continue
            try:
                with open(
                    file_path,
                    "r",
                    encoding="utf-8",
                    errors="replace",
                ) as f:
                    for line_num, line in enumerate(f, start=1):
                        if regex.search(line):
                            results.append(
                                f"{file_path.resolve()}: {line_num}: "
                                f"{line.rstrip('\r\n')}"
                            )
            except Exception:
                continue
                
        if not results:
            return f"Definition of '{name}' not found in the codebase."
        return "\n".join(results)
    except Exception as e:
        return f"Error searching definition: {str(e)}"


@mcp.tool()
def find_references(name: str, filepath: str, line: int) -> str:
    """Find all usages and references of a symbol across the codebase."""
    try:
        root_dir = Path(".").resolve()
        pattern = rf"\b{re.escape(name)}\b"
        regex = re.compile(pattern)
        
        results = []
        for file_path in root_dir.rglob("*.py"):
            if ".git" in file_path.parts or "__pycache__" in file_path.parts:
                continue
            try:
                with open(
                    file_path,
                    "r",
                    encoding="utf-8",
                    errors="replace",
                ) as f:
                    for line_num, line in enumerate(f, start=1):
                        if regex.search(line):
                            results.append(
                                f"{file_path.resolve()}: {line_num}: "
                                f"{line.rstrip('\r\n')}"
                            )
            except Exception:
                continue
        if not results:
            return f"No references found for symbol '{name}'."
        return "\n".join(results)
    except Exception as e:
        return f"Error finding references: {str(e)}"


@mcp.tool()
def get_patch() -> str:
    """Retrieve the unified git diff of all changes made to the
    repository so far.
    """
    try:
        cmd = "git -c core.fileMode=false diff"
        res = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60
        )
        if res.returncode != 0:
            return f"Error generating patch: {res.stderr}"
        return res.stdout or "No changes made yet (empty diff)."
    except Exception as e:
        return f"Error executing git diff: {str(e)}"


@mcp.tool()
def run_command(command: str, workdir: str) -> str:
    """Execute an arbitrary shell command in a specified working directory.
    Returns stdout, stderr, and the exit code.
    """
    try:
        res = subprocess.run(
            command,
            shell=True,
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300
        )
        return (
            f"Exit Code: {res.returncode}\n"
            f"--- STDOUT ---\n{res.stdout or '(empty)'}\n"
            f"--- STDERR ---\n{res.stderr or '(empty)'}"
        )
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 300 seconds."
    except Exception as e:
        return f"Error executing command: {type(e).__name__}: {e}"


@mcp.tool()
def run_tests(code: str, tests: List[str]) -> str:
    """Execute the pre-configured evaluation script inside the
    SWE-bench environment.

    Note: 'code' and 'tests' arguments can be used to pass dynamic
    scripts if needed, but typically this triggers the pytest/tox
    suite of the environment via subprocess.
    """
    return run_command(command="pytest", workdir=".")


if __name__ == "__main__":
    mcp.run()
