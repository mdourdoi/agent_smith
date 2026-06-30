class Console:
    # ANSI codes
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def _c(self, text: str, color: str) -> str:
        return f"{color}{text}{self.RESET}"

    def task_start(self, task_id: str, benchmark: str, model: str) -> None:
        if not self.verbose:
            return
        bar = "═" * 60
        print(self._c(bar, self.BLUE))
        print(self._c(f"  Agent Smith — {benchmark.upper()} task {task_id}",
                      self.BOLD + self.BLUE))
        print(self._c(f"  model: {model}", self.DIM))
        print(self._c(bar, self.BLUE))

    def iteration(self, n: int, max_n: int) -> None:
        if not self.verbose:
            return
        print()
        print(self._c(f"┌─ Iteration {n}/{max_n}", self.BOLD + self.CYAN))

    def thought(self, text: str) -> None:
        if not self.verbose or not text.strip():
            return
        # Show only the prose before the first code block, trimmed.
        prose = text.split("```")[0].strip()
        if not prose:
            return
        for line in prose.splitlines():
            print(self._c("│ ", self.CYAN) + self._c(line, self.DIM))

    def code(self, code: str) -> None:
        if not self.verbose or not code.strip():
            return
        print(self._c("│ ", self.CYAN) + self._c("code:", self.YELLOW))
        for line in code.splitlines():
            print(self._c("│   ", self.CYAN) + line)

    def observation(self, text: str) -> None:
        if not self.verbose:
            return
        print(self._c("│ ", self.CYAN) + self._c("observation:", self.GREEN))
        for line in text.splitlines():
            print(self._c("│   ", self.CYAN) + self._c(line, self.DIM))

    def tokens(self, total_in: int, total_out: int) -> None:
        if not self.verbose:
            return
        print(self._c("│ ", self.CYAN)
              + self._c(f"tokens so far — in: {total_in}, out: {total_out}",
                        self.DIM))

    def solved(self, success: bool, iterations: int) -> None:
        if not self.verbose:
            return
        print()
        if success:
            msg = f"✓ Solved in {iterations} iterations"
            print(self._c(msg, self.BOLD + self.GREEN))
        else:
            msg = f"✗ Not solved ({iterations} iterations used)"
            print(self._c(msg, self.BOLD + self.RED))

    def error(self, message: str) -> None:
        if not self.verbose:
            return
        print(self._c(f"  ! {message}", self.RED))
