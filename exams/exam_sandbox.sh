#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$(command -v python3 || command -v python)"

usage() {
    cat <<'EOF'
Usage: exam_sandbox.sh --student-path PATH --moulinette-path PATH --env-file FILE [options]

Runs a student's Python submission inside the isolated sandbox CLI.

Required arguments:
  --student-path PATH      Path to the student submission directory.
  --moulinette-path PATH   Path to the moulinette repository root.
  --env-file FILE          Environment file to load before execution.

Optional arguments:
  --student-file FILE      Relative path to the Python file inside student-path.
  --sandbox-config FILE    JSON file with sandbox configuration.

The script uses the sandbox CLI in the repository and validates paths carefully.
EOF
    exit 1
}

student_path=""
moulinette_path=""
env_file=""
student_file=""
sandbox_config=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --student-path)
            student_path="$2"
            shift 2
            ;;
        --moulinette-path)
            moulinette_path="$2"
            shift 2
            ;;
        --env-file)
            env_file="$2"
            shift 2
            ;;
        --student-file)
            student_file="$2"
            shift 2
            ;;
        --sandbox-config)
            sandbox_config="$2"
            shift 2
            ;;
        -*|--*)
            echo "ERROR: Unknown argument: $1" >&2
            usage
            ;;
        *)
            echo "ERROR: Unexpected positional argument: $1" >&2
            usage
            ;;
    esac
done

if [[ -z "$student_path" || -z "$moulinette_path" || -z "$env_file" ]]; then
    echo "ERROR: --student-path, --moulinette-path and --env-file are required." >&2
    usage
fi

student_path="$(realpath "$student_path")"
moulinette_path="$(realpath "$moulinette_path")"
env_file="$(realpath "$env_file")"

if [[ ! -d "$student_path" ]]; then
    echo "ERROR: student path is not a directory: $student_path" >&2
    exit 1
fi

if [[ ! -d "$moulinette_path" ]]; then
    echo "ERROR: moulinette path is not a directory: $moulinette_path" >&2
    exit 1
fi

if [[ ! -f "$env_file" ]]; then
    echo "ERROR: env file does not exist: $env_file" >&2
    exit 1
fi

if [[ -n "$sandbox_config" && ! -f "$sandbox_config" ]]; then
    echo "ERROR: sandbox config does not exist: $sandbox_config" >&2
    exit 1
fi

if [[ -n "$student_file" ]]; then
    student_file_path="$student_path/$student_file"
    if [[ ! -f "$student_file_path" ]]; then
        echo "ERROR: specified student file does not exist: $student_file_path" >&2
        exit 1
    fi
else
    py_files=("$student_path"/*.py)
    if [[ ${#py_files[@]} -eq 1 ]]; then
        student_file_path="${py_files[0]}"
    else
        echo "ERROR: multiple or no Python files found in student path."
        echo "Specify --student-file relative to --student-path." >&2
        exit 1
    fi
fi

if [[ -z "$PYTHON_BIN" ]]; then
    echo "ERROR: Python interpreter not found on PATH." >&2
    exit 1
fi

cd "$REPO_ROOT"

# Load environment variables in a controlled way.
set -a
source "$env_file"
set +a

cmd=("$PYTHON_BIN" -m core.sandbox_cli --file "$student_file_path")
if [[ -n "$sandbox_config" ]]; then
    cmd+=(--sandbox-config "$sandbox_config")
fi

exec "${cmd[@]}"
