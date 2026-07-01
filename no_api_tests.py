import os
import sys
import json
import subprocess
import tempfile

sys.path.insert(0, 'src')
from core.code_extractor import CodeExtractor
from core.providers import PROVIDERS
from core.llm_client import LLMClient
import core.agent_mbpp as mbpp
from core.sandbox_config import SandboxConfig
from core.sandbox import Sandbox
from core.solution_output import SolutionOutput
from core.step_metrics import StepMetrics

failed = 0

def check(name, fn):
    global failed
    print(f"\n=== {name} ===")
    try:
        fn()
        print(f"✅ {name} PASSED")
    except Exception as e:
        print(f"❌ {name} FAILED: {e}")
        failed += 1


def assert_code_extractor():
    text = '```python\ndef add(a, b):\n    return a + b\n```\n'
    res = CodeExtractor().extract(text)
    assert res is not None and 'def add' in res.code


def assert_providers():
    for p in ['cerebras', 'groq', 'mistral', 'openrouter']:
        assert p in PROVIDERS, p


def assert_llm_client():
    llm = LLMClient(api_keys=['test-key'], model='mixtral-8x7b-32768', provider_url='https://api.groq.com/openai/v1')
    assert llm.model == 'mixtral-8x7b-32768'


def assert_api_key_loader():
    if 'TEST_API_KEY' in os.environ:
        del os.environ['TEST_API_KEY']
    keys = mbpp.load_api_keys('TEST_API_KEY')
    assert keys == []


def assert_sandboxconfig_default():
    c = SandboxConfig()
    assert c.cpu_limit is not None
    assert c.memory_limit is not None


def assert_sandboxconfig_from_json():
    data = {'cpu_limit': '2', 'memory_limit': '512m', 'timeout_seconds': 30}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(data, f)
        path = f.name
    try:
        c = SandboxConfig.from_json(path)
        assert c.cpu_limit == '2'
    finally:
        os.unlink(path)


def assert_sandbox_cli_help():
    proc = subprocess.run('PYTHONPATH=src python src/core/sandbox_cli.py --help', shell=True, capture_output=True, text=True)
    assert 'usage' in proc.stdout.lower() or 'usage' in proc.stderr.lower()


def assert_sandbox_json_config():
    data = {'cpu_limit': '1', 'memory_limit': '256m', 'timeout_seconds': 10}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(data, f)
        path = f.name
    try:
        config = SandboxConfig.from_json(path)
        s = Sandbox(image='python:3.11-slim', config=config, mcp_client=None)
        assert s.image == 'python:3.11-slim'
    finally:
        os.unlink(path)


def assert_sandbox_execution():
    s = Sandbox(image='python:3.11-slim', config=SandboxConfig(), mcp_client=None)
    s.start()
    result = s.run('print(1+1)')
    s.cleanup()
    assert '2' in str(result)


def assert_solution_output():
    s = SolutionOutput(task_id='test-1', benchmark='mbpp', success=True, solution='code', system_prompt='prompt', iterations=1, total_requests=1, total_input_tokens=10, total_output_tokens=5, total_time_seconds=1.0, steps=[])
    assert s.benchmark == 'mbpp'


def assert_step_metrics():
    m = StepMetrics(step=1, input_tokens=100, output_tokens=50, request_time_ms=234.5, api_url='https://api.groq.com/openai/v1', model_name='mixtral-8x7b-32768', llm_output='output', sandbox_input='input', sandbox_output='result', retries=0)
    assert m.step == 1


def assert_mbpp_solution_json():
    s = SolutionOutput(benchmark='mbpp', task_id='1', success=True, solution='def add(a,b): return a+b', system_prompt='MBPP prompt', iterations=3, total_requests=5, total_input_tokens=150, total_output_tokens=75, total_time_seconds=12.5, steps=[])
    obj = json.loads(s.model_dump_json())
    assert obj['benchmark'] == 'mbpp'


def assert_swebench_solution_json():
    s = SolutionOutput(benchmark='swebench', task_id='test/test-1', success=True, solution='diff', system_prompt='Swebench prompt', iterations=5, total_requests=8, total_input_tokens=200, total_output_tokens=100, total_time_seconds=25.0, steps=[])
    obj = json.loads(s.model_dump_json())
    assert obj['benchmark'] == 'swebench'


def assert_mcp_server(path):
    p = subprocess.Popen([sys.executable, path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        req = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}) + '\n'
        out, err = p.communicate(req, timeout=3)
        assert p.returncode == 0 or 'tool' in out.lower() or 'tool' in err.lower()
    finally:
        p.kill()

check('Import core modules', lambda: [__import__(m) for m in ['core.sandbox', 'core.sandbox_config', 'core.prompts', 'core.llm_client']])
check('Import serveur MCP modules', lambda: [__import__(m) for m in ['serveur.mcp_tools_mbpp', 'serveur.mcp_tools_swebench']])
check('Code Extractor', assert_code_extractor)
check('Providers', assert_providers)
check('LLM Client instantiation', assert_llm_client)
check('API key loader returns empty', assert_api_key_loader)
check('SandboxConfig default', assert_sandboxconfig_default)
check('SandboxConfig from JSON', assert_sandboxconfig_from_json)
check('Sandbox CLI help', assert_sandbox_cli_help)
check('Sandbox JSON config with Sandbox', assert_sandbox_json_config)
check('Sandbox start, execute, cleanup', assert_sandbox_execution)
check('SolutionOutput schema', assert_solution_output)
check('StepMetrics schema', assert_step_metrics)
check('MBPP Solution JSON', assert_mbpp_solution_json)
check('Swebench Solution JSON', assert_swebench_solution_json)
check('MCP MBPP server startup', lambda: assert_mcp_server('serveur/mcp_tools_mbpp.py'))
check('MCP Swebench server startup', lambda: assert_mcp_server('serveur/mcp_tools_swebench.py'))

if failed:
    print(f"\n⚠️ {failed} no-API tests failed")
    sys.exit(1)
print('\n🎉 Tous les tests sans API key ont réussi.')
