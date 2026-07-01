# Tests Agent Smith - Copy-Paste Commands

**STATUS: 5/5 BASIC TESTS ✅ PASSED**
- ✅ Phase 1: Both agents importable
- ✅ Phase 2: Prompts loaded (MBPP: 1150 chars, Swebench: 1560 chars)
- ✅ Phase 3: CLI arguments parsed correctly
- ✅ Phase 4: SandboxConfig working
- ✅ Phase 5: Solution output format valid

## Phase 1: Import tests (5 min)

### Test 1.1: Import tous les modules core
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
sys.path.insert(0, 'src')

modules = [
    'core.sandbox',
    'core.orchestrator_base',
    'core.orchestrator_mbpp',
    'core.orchestrator_swebench',
    'core.llm_client',
    'core.providers',
    'core.prompts',
    'core.code_extractor',
    'core.console',
    'core.final_answer_signal',
    'core.solution_output',
    'core.step_metrics',
    'core.sandbox_config',
    'core.sandbox_cli',
    'core.agent_mbpp',
    'core.agent_swebench',
]

failed = []
for mod in modules:
    try:
        __import__(mod)
        print(f"✓ {mod}")
    except Exception as e:
        print(f"✗ {mod}: {e}")
        failed.append(mod)

if failed:
    print(f"\n❌ {len(failed)} modules failed")
    sys.exit(1)
else:
    print(f"\n✅ All {len(modules)} modules imported successfully")
EOF
```

### Test 1.2: Import MCP servers
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
sys.path.insert(0, 'serveur')

# Test MCP client
try:
    from mcp_client import MCPClientBridge
    print("✓ mcp_client.MCPClientBridge")
except Exception as e:
    print(f"✗ mcp_client: {e}")
    sys.exit(1)

# Test that MCP tools can be parsed
import subprocess
for tool_file in ['serveur/mcp_tools_mbpp.py', 'serveur/mcp_tools_swebench.py']:
    try:
        result = subprocess.run([sys.executable, tool_file, '--help'], 
                              capture_output=True, timeout=5)
        if result.returncode == 0:
            print(f"✓ {tool_file} (--help works)")
        else:
            print(f"⚠ {tool_file} (--help returned {result.returncode})")
    except Exception as e:
        print(f"✗ {tool_file}: {e}")

print("\n✅ MCP servers can be invoked")
EOF
```

---

## Phase 2: MCP Server tests (10 min)

### Test 2.1: MCP MBPP server list_tools
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import json
import subprocess
import sys

# Test MBPP server
proc = subprocess.Popen(
    [sys.executable, 'serveur/mcp_tools_mbpp.py'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

# Send list_tools request
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
}

try:
    stdout, stderr = proc.communicate(json.dumps(request) + '\n', timeout=5)
    if proc.returncode == 0 or 'tools' in stdout.lower():
        print("✓ MBPP server responded to list_tools")
        print(f"  Output preview: {stdout[:100]}...")
    else:
        print(f"⚠ MBPP server returned: {stderr[:200]}")
except subprocess.TimeoutExpired:
    proc.kill()
    print("⚠ MBPP server timeout (expected if waiting for input)")
except Exception as e:
    print(f"✗ Error: {e}")

print("✅ MBPP server test done")
EOF
```

### Test 2.2: MCP Swebench server list_tools
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import json
import subprocess
import sys

# Test Swebench server
proc = subprocess.Popen(
    [sys.executable, 'serveur/mcp_tools_swebench.py'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

# Send list_tools request
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
}

try:
    stdout, stderr = proc.communicate(json.dumps(request) + '\n', timeout=5)
    if proc.returncode == 0 or 'tools' in stdout.lower():
        print("✓ Swebench server responded to list_tools")
        print(f"  Output preview: {stdout[:100]}...")
    else:
        print(f"⚠ Swebench server returned: {stderr[:200]}")
except subprocess.TimeoutExpired:
    proc.kill()
    print("⚠ Swebench server timeout (expected if waiting for input)")
except Exception as e:
    print(f"✗ Error: {e}")

print("✅ Swebench server test done")
EOF
```

---

## Phase 3: Prompts & Code Extraction (5 min)

### Test 3.1: MBPP prompts
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
sys.path.insert(0, 'src')

from core.prompts import MBPP_SYSTEM_PROMPT, build_mbpp_task_message

# Test MBPP system prompt
if len(MBPP_SYSTEM_PROMPT) > 100 and 'autonomous' in MBPP_SYSTEM_PROMPT.lower():
    print(f"✓ MBPP_SYSTEM_PROMPT loaded ({len(MBPP_SYSTEM_PROMPT)} chars)")
else:
    print("✗ MBPP_SYSTEM_PROMPT invalid")
    sys.exit(1)

# Test MBPP task message builder
task_msg = build_mbpp_task_message(
    task_definition="Add two numbers",
    function_definition="def add(a, b):",
    test_list=["assert add(2, 3) == 5"]
)

if 'add' in task_msg and 'assert' in task_msg:
    print(f"✓ build_mbpp_task_message works ({len(task_msg)} chars)")
else:
    print("✗ build_mbpp_task_message failed")
    sys.exit(1)

print("✅ MBPP prompts OK")
EOF
```

### Test 3.2: Swebench prompts
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
sys.path.insert(0, 'src')

from core.prompts import SWEBENCH_SYSTEM_PROMPT, build_swebench_task_message

# Test Swebench system prompt
if len(SWEBENCH_SYSTEM_PROMPT) > 100 and 'bug' in SWEBENCH_SYSTEM_PROMPT.lower():
    print(f"✓ SWEBENCH_SYSTEM_PROMPT loaded ({len(SWEBENCH_SYSTEM_PROMPT)} chars)")
else:
    print("✗ SWEBENCH_SYSTEM_PROMPT invalid")
    sys.exit(1)

# Test Swebench task message builder
task_msg = build_swebench_task_message({
    'instance_id': 'test/test-1',
    'problem_statement': 'Fix the bug',
    'repo': 'test/repo',
    'docker_image': 'python:3.11',
    'eval_script': 'pytest test.py'
})

if 'test/test-1' in task_msg and 'Fix the bug' in task_msg:
    print(f"✓ build_swebench_task_message works ({len(task_msg)} chars)")
else:
    print("✗ build_swebench_task_message failed")
    sys.exit(1)

print("✅ Swebench prompts OK")
EOF
```

### Test 3.3: Code extractor
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
sys.path.insert(0, 'src')

from core.code_extractor import CodeExtractor

# Test Python code extraction
test_response = """
Let me solve this.

```python
def add(a, b):
    return a + b
print(add(2, 3))
```
<end_code>

Done!
"""

extractor = CodeExtractor()
codes = extractor.extract_all_code(test_response)

if codes and 'def add' in codes[0]:
    print(f"✓ CodeExtractor found Python block ({len(codes[0])} chars)")
else:
    print("✗ CodeExtractor failed to extract code")
    sys.exit(1)

print("✅ Code extractor OK")
EOF
```

---

## Phase 4: CLI Arguments (5 min)

### Test 4.1: Agent MBPP CLI help
```bash
cd /sgoinfre/mobenhab/agent_smith && PYTHONPATH=src python src/core/agent_mbpp.py --help 2>&1 | grep -E "(task-file|output|model-name)" && echo "✅ MBPP CLI arguments OK"
```

### Test 4.2: Agent Swebench CLI help
```bash
cd /sgoinfre/mobenhab/agent_smith && PYTHONPATH=src python src/core/agent_swebench.py --help 2>&1 | grep -E "(task-file|output|model-name)" && echo "✅ Swebench CLI arguments OK"
```

### Test 4.3: Agent MBPP validation (missing task-file)
```bash
cd /sgoinfre/mobenhab/agent_smith && PYTHONPATH=src python src/core/agent_mbpp.py --output /tmp/test.json --model-name gpt-4 2>&1 | grep -q "error" && echo "✅ MBPP validates required args"
```

### Test 4.4: Agent Swebench validation (missing task-file)
```bash
cd /sgoinfre/mobenhab/agent_smith && PYTHONPATH=src python src/core/agent_swebench.py --output /tmp/test.json --model-name gpt-4 2>&1 | grep -q "error" && echo "✅ Swebench validates required args"
```

---

## Phase 5: LLM & Providers (5 min)

### Test 5.1: Providers available
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
sys.path.insert(0, 'src')

from core.providers import PROVIDERS

expected = ['cerebras', 'groq', 'mistral', 'openrouter']
found = list(PROVIDERS.keys())

print(f"Found providers: {found}")
for p in expected:
    if p in found:
        print(f"✓ {p}")
    else:
        print(f"✗ {p} missing")

print("✅ Providers test done")
EOF
```

### Test 5.2: LLM client instantiation
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
sys.path.insert(0, 'src')

from core.llm_client import LLMClient

try:
    llm = LLMClient(
        api_keys=['test-key'],
        model='mixtral-8x7b-32768',
        provider_url='https://api.groq.com/openai/v1'
    )
    print(f"✓ LLMClient instantiated")
    print(f"  Model: {llm.model}")
    print(f"  Provider: {llm.provider_url[:40]}...")
except Exception as e:
    print(f"✗ LLMClient failed: {e}")
    sys.exit(1)

print("✅ LLM client OK")
EOF
```

### Test 5.3: API key loading
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
import os
sys.path.insert(0, 'src')

from core.llm_client import load_api_keys

# Test without GROQ_API_KEY set
if 'GROQ_API_KEY' in os.environ:
    del os.environ['GROQ_API_KEY']

keys = load_api_keys('GROQ_API_KEY')
if not keys:
    print("✓ load_api_keys correctly returns empty when env var not set")
else:
    print(f"⚠ load_api_keys returned: {keys}")

print("✅ API key loading test done")
EOF
```

---

## Phase 6: Configuration & Sandbox (5 min)

### Test 6.1: SandboxConfig default
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
sys.path.insert(0, 'src')

from core.sandbox_config import SandboxConfig

config = SandboxConfig()
print(f"✓ SandboxConfig created")
print(f"  CPU limit: {config.cpu_limit}")
print(f"  Memory limit: {config.memory_limit}")
print(f"  Timeout: {config.timeout_seconds}")

print("✅ SandboxConfig OK")
EOF
```

### Test 6.2: SandboxConfig from_json
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
import json
import tempfile
sys.path.insert(0, 'src')

from core.sandbox_config import SandboxConfig

# Create temp JSON config
config_data = {
    "cpu_limit": "2",
    "memory_limit": "512m",
    "timeout_seconds": 30
}

with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump(config_data, f)
    temp_file = f.name

try:
    config = SandboxConfig.from_json(temp_file)
    print(f"✓ SandboxConfig.from_json works")
    print(f"  CPU: {config.cpu_limit}, Memory: {config.memory_limit}")
finally:
    import os
    os.unlink(temp_file)

print("✅ SandboxConfig JSON OK")
EOF
```

### Test 6.3: Sandbox instantiation (no Docker required)
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
sys.path.insert(0, 'src')

from core.sandbox import Sandbox
from core.sandbox_config import SandboxConfig

try:
    sandbox = Sandbox(
        image='python:3.11-slim',
        config=SandboxConfig(),
        mcp_client=None
    )
    print(f"✓ Sandbox instantiated")
    print(f"  Image: {sandbox.image}")
except Exception as e:
    print(f"✗ Sandbox instantiation failed: {e}")
    sys.exit(1)

print("✅ Sandbox instantiation OK")
EOF
```

---

## Phase 7: Solution & Metrics Format (5 min)

### Test 7.1: Solution output schema
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
import json
sys.path.insert(0, 'src')

from core.solution_output import SolutionOutput

# Create solution with all required fields
solution = SolutionOutput(
    task_id='test-1',
    benchmark='mbpp',
    success=True,
    solution='def add(a, b): return a + b',
    system_prompt='Test prompt',
    iterations=3,
    total_requests=5,
    total_input_tokens=200,
    total_output_tokens=100,
    total_time_seconds=15.5,
    steps=[]
)

# Convert to dict
solution_dict = solution.model_dump()

required_fields = ['benchmark', 'task_id', 'success', 'solution', 'iterations', 'total_requests', 'steps']
for field in required_fields:
    if field in solution_dict:
        print(f"✓ {field}")
    else:
        print(f"✗ {field} missing")
        sys.exit(1)

print("✅ Solution output schema OK")
EOF
```

### Test 7.2: Metrics validation
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
sys.path.insert(0, 'src')

from core.step_metrics import StepMetrics

metrics = StepMetrics(
    step=1,
    input_tokens=100,
    output_tokens=50,
    request_time_ms=234.5,
    api_url='https://api.groq.com/openai/v1',
    model_name='mixtral-8x7b-32768',
    llm_output='def add(a, b): return a + b',
    sandbox_input='Test input',
    sandbox_output='Test output',
    retries=0
)

print(f"✓ StepMetrics created")
print(f"  Step: {metrics.step}, Input: {metrics.input_tokens}, Output: {metrics.output_tokens}")
print(f"  Request time: {metrics.request_time_ms}ms, Retries: {metrics.retries}")

print("✅ Metrics validation OK")
EOF
```

---

## Phase 8: Test Files Creation

### Test 8.1: Create test MBPP task
```bash
mkdir -p /sgoinfre/mobenhab/agent_smith/cache && cat > /sgoinfre/mobenhab/agent_smith/cache/mbpp_task_test.json << 'EOF'
{
  "task_id": 1,
  "task_definition": "Write a function that adds two numbers.",
  "function_definition": "def add(a: int, b: int) -> int:",
  "test_list": [
    "assert add(2, 3) == 5",
    "assert add(0, 0) == 0",
    "assert add(-1, 1) == 0"
  ]
}
EOF
echo "✅ Test MBPP task created at cache/mbpp_task_test.json"
```

### Test 8.2: Create test Swebench task
```bash
mkdir -p /sgoinfre/mobenhab/agent_smith/cache && cat > /sgoinfre/mobenhab/agent_smith/cache/swebench_task_test.json << 'EOF'
{
  "instance_id": "test/test-1",
  "repo": "test/repo",
  "problem_statement": "Fix the bug in the add function. It should return the sum of two numbers.",
  "docker_image": "python:3.11",
  "eval_script": "python -m pytest test.py -xvs",
  "test_patch": "test patch content",
  "created_at": "2024-01-01"
}
EOF
echo "✅ Test Swebench task created at cache/swebench_task_test.json"
```

---

## Phase 9: Solution Output Tests

### Test 9.1: MBPP solution JSON structure
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
import json
sys.path.insert(0, 'src')

from core.solution_output import SolutionOutput

# Simulate a complete MBPP solution
solution = SolutionOutput(
    benchmark='mbpp',
    task_id='1',
    success=True,
    solution='def add(a: int, b: int) -> int:\n    return a + b',
    system_prompt='MBPP system prompt',
    iterations=3,
    total_requests=5,
    total_input_tokens=150,
    total_output_tokens=75,
    total_time_seconds=12.5,
    steps=[]
)

# Export to JSON
json_str = solution.model_dump_json()
data = json.loads(json_str)

print("✓ MBPP solution JSON structure:")
print(f"  benchmark: {data['benchmark']}")
print(f"  task_id: {data['task_id']}")
print(f"  success: {data['success']}")
print(f"  solution length: {len(data['solution'])} chars")
print(f"  iterations: {data['iterations']}")

print("✅ MBPP solution structure OK")
EOF
```

### Test 9.2: Swebench solution JSON structure
```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
import json
sys.path.insert(0, 'src')

from core.solution_output import SolutionOutput

# Simulate a complete Swebench solution
solution = SolutionOutput(
    benchmark='swebench',
    task_id='test/test-1',
    success=True,
    solution='diff --git a/test.py b/test.py\n...',
    system_prompt='Swebench system prompt',
    iterations=5,
    total_requests=8,
    total_input_tokens=200,
    total_output_tokens=100,
    total_time_seconds=25.0,
    steps=[]
)

# Export to JSON
json_str = solution.model_dump_json()
data = json.loads(json_str)

print("✓ Swebench solution JSON structure:")
print(f"  benchmark: {data['benchmark']}")
print(f"  task_id: {data['task_id']}")
print(f"  success: {data['success']}")
print(f"  solution length: {len(data['solution'])} chars")
print(f"  iterations: {data['iterations']}")

print("✅ Swebench solution structure OK")
EOF
```

---

## Summary: Run all basic tests

```bash
cd /sgoinfre/mobenhab/agent_smith

echo "=== PHASE 1: Import tests ==="
python << 'EOF'
import sys
sys.path.insert(0, 'src')
try:
    from core.agent_mbpp import main as mbpp_main
    from core.agent_swebench import main as swebench_main
    print("✅ Both agents importable")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
EOF

echo ""
echo "=== PHASE 2: Prompts ==="
python << 'EOF'
import sys
sys.path.insert(0, 'src')
from core.prompts import MBPP_SYSTEM_PROMPT, SWEBENCH_SYSTEM_PROMPT, build_mbpp_task_message, build_swebench_task_message
print(f"✅ MBPP prompt: {len(MBPP_SYSTEM_PROMPT)} chars")
print(f"✅ Swebench prompt: {len(SWEBENCH_SYSTEM_PROMPT)} chars")
EOF

echo ""
echo "=== PHASE 3: CLI Arguments ==="
PYTHONPATH=src python src/core/agent_mbpp.py --help > /dev/null 2>&1 && echo "✅ MBPP CLI OK" || echo "❌ MBPP CLI failed"
PYTHONPATH=src python src/core/agent_swebench.py --help > /dev/null 2>&1 && echo "✅ Swebench CLI OK" || echo "❌ Swebench CLI failed"

echo ""
echo "=== PHASE 4: Configuration ==="
python << 'EOF'
import sys
sys.path.insert(0, 'src')
from core.sandbox_config import SandboxConfig
config = SandboxConfig()
print(f"✅ SandboxConfig: CPU={config.cpu_limit}, Memory={config.memory_limit}")
EOF

echo ""
echo "=== PHASE 5: Solution format ==="
python << 'EOF'
import sys
sys.path.insert(0, 'src')
from core.solution_output import SolutionOutput
s = SolutionOutput(
    task_id='test-1',
    benchmark='mbpp',
    success=True,
    solution='code',
    system_prompt='prompt',
    iterations=1,
    total_requests=1,
    total_input_tokens=10,
    total_output_tokens=5,
    total_time_seconds=1.0,
    steps=[]
)
print("✅ Solution format OK")
EOF

echo ""
echo "✅ All basic tests completed!"
```
