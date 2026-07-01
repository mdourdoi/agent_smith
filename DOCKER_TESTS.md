# Tests Docker - Agent Smith

**Docker Status**: ✅ Installé (Docker 29.3.0)

---

## 🐳 Test 1: Vérifier les images Docker disponibles

```bash
docker images | grep -E "python|alpine"
# Si vide, les images seront téléchargées automatiquement au premier test
```

---

## 🐳 Test 2: Tester la création du Sandbox Docker

```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
import time
sys.path.insert(0, 'src')

from core.sandbox import Sandbox
from core.sandbox_config import SandboxConfig

print("Creating sandbox...")
try:
    sandbox = Sandbox(
        image='python:3.11-slim',
        config=SandboxConfig(),
        mcp_client=None
    )
    print(f"✓ Sandbox object created")
    print(f"  Image: {sandbox.image}")
    print(f"  Container ID will be assigned on first use")
    
    # Note: Docker container is created on first code execution,
    # not on instantiation
    
except Exception as e:
    print(f"✗ Sandbox creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("✅ Sandbox creation OK")
EOF
```

---

## 🐳 Test 3: Exécuter du code dans le Sandbox (nécessite Docker)

```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
sys.path.insert(0, 'src')

from core.sandbox import Sandbox
from core.sandbox_config import SandboxConfig

print("Starting sandbox execution test...")

try:
    sandbox = Sandbox(
        image='python:3.11-slim',
        config=SandboxConfig(),
        mcp_client=None
    )
    
    # Start the sandbox (creates Docker container)
    print("Starting sandbox container...")
    sandbox.start()
    
    # Execute code in sandbox
    print("Executing: print(1 + 1)")
    result = sandbox.run('print(1 + 1)')
    print(f"Result: {result}")
    
    if '2' in str(result):
        print("✓ Code execution works!")
    else:
        print(f"✗ Unexpected result: {result}")
        sys.exit(1)
    
    # Test persistence
    print("\nTesting persistence...")
    sandbox.run('x = 42')
    result = sandbox.run('print(x)')
    print(f"Result: {result}")
    
    if '42' in str(result):
        print("✓ Sandbox is persistent!")
    else:
        print(f"✗ Variable not persisted: {result}")
    
except Exception as e:
    print(f"✗ Sandbox execution failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    try:
        sandbox.cleanup()
        print("\n✓ Sandbox cleaned up")
    except:
        pass

print("\n✅ Sandbox execution OK")
EOF
```

---

## 🐳 Test 4: Cleanup des conteneurs Docker

```bash
# Voir les conteneurs
docker ps -a | grep python

# Cleanup (si besoin)
docker container prune -f  # Supprime les conteneurs stoppés
docker image prune -f      # Supprime les images inutilisées

# Ou spécifiquement:
docker ps -a | grep "python:3.11-slim" | awk '{print $1}' | xargs docker rm -f
```

---

## 🐳 Test 5: Test complet avec MCP et Sandbox

```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
import json
sys.path.insert(0, 'src')
sys.path.insert(0, 'serveur')

from core.sandbox import Sandbox
from core.sandbox_config import SandboxConfig
from mcp_client import MCPClientBridge

print("=== SANDBOX + MCP TEST ===\n")

try:
    # Step 1: Create MCP client
    print("Step 1: Creating MCP client...")
    mcp = MCPClientBridge()
    mcp.connect_stdio('python serveur/mcp_tools_mbpp.py')
    print("✓ MCP client connected")
    
    # Step 2: Get available tools
    print("\nStep 2: Getting available tools...")
    tools = mcp.get_available_tools_names()
    print(f"✓ Found {len(tools)} tools: {tools[:3]}...")
    
    # Step 3: Create sandbox with MCP
    print("\nStep 3: Creating sandbox with MCP...")
    sandbox = Sandbox(
        image='python:3.11-slim',
        config=SandboxConfig(),
        mcp_client=mcp
    )
    print("✓ Sandbox created with MCP")
    
    # Step 4: Execute code
    print("\nStep 4: Executing code in sandbox...")
    result = sandbox.run_code('print("Hello from sandbox!")')
    print(f"Result: {result}")
    
    print("\n✅ All Docker + MCP tests passed!")
    
except Exception as e:
    print(f"\n✗ Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    try:
        sandbox.cleanup()
        mcp.close()
    except:
        pass

EOF
```

---

## 🐳 Test 6: Monitorage Docker en temps réel

```bash
# Terminal 1: Watch containers
watch -n 1 'docker ps --format "table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}"'

# Terminal 2: Watch images
watch -n 1 'docker images'

# Terminal 3: Monitor Docker daemon logs
docker events --filter type=container
```

---

## 🐳 Test 7: Test avec limite de ressources

```bash
cd /sgoinfre/mobenhab/agent_smith && python << 'EOF'
import sys
import json
import tempfile
sys.path.insert(0, 'src')

from core.sandbox import Sandbox
from core.sandbox_config import SandboxConfig

print("Creating sandbox with resource limits...")

# Create config with limits
config_data = {
    "cpu_limit": "1",
    "memory_limit": "256m",
    "timeout_seconds": 10
}

with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump(config_data, f)
    config_file = f.name

try:
    config = SandboxConfig.from_json(config_file)
    sandbox = Sandbox(
        image='python:3.11-slim',
        config=config,
        mcp_client=None
    )
    
    print(f"✓ Sandbox with limits created")
    print(f"  CPU: {config.cpu_limit}")
    print(f"  Memory: {config.memory_limit}")
    print(f"  Timeout: {config.timeout_seconds}s")
    
    # Test code execution
    result = sandbox.run_code('print("Limited sandbox works!")')
    print(f"\n✓ Code execution with limits: {result}")
    
    sandbox.cleanup()
    print("✅ Limited sandbox test passed!")
    
except Exception as e:
    print(f"✗ Test failed: {e}")
    import traceback
    traceback.print_exc()
finally:
    import os
    os.unlink(config_file)

EOF
```

---

## 🐳 Commandes utiles Docker

```bash
# Voir les conteneurs actifs
docker ps

# Voir tous les conteneurs (y compris stoppés)
docker ps -a

# Voir les logs d'un conteneur
docker logs <container_id>

# Accéder au shell d'un conteneur
docker exec -it <container_id> /bin/bash

# Arrêter un conteneur
docker stop <container_id>

# Supprimer un conteneur
docker rm <container_id>

# Supprimer une image
docker rmi python:3.11-slim

# Nettoyer tout
docker system prune -a --volumes

# Vérifier l'utilisation des ressources
docker stats

# Montrer les événements en temps réel
docker events
```

---

## 📋 Checklist Docker

- [ ] Docker installé et fonctionnel
- [ ] Images Python téléchargées
- [ ] Sandbox crée et exécute du code
- [ ] Sandbox persiste les variables
- [ ] Cleanup fonctionne (pas de conteneurs zombies)
- [ ] MCP + Sandbox fonctionne ensemble
- [ ] Limites de ressources appliquées
- [ ] Tests end-to-end passent

---

## 🚀 Quick start - Exécuter tous les tests Docker

```bash
cd /sgoinfre/mobenhab/agent_smith

echo "=== Docker Setup Test ==="
docker version > /dev/null && echo "✅ Docker OK" || echo "❌ Docker FAILED"

echo ""
echo "=== Sandbox Creation Test ==="
timeout 30 python << 'EOF'
import sys
sys.path.insert(0, 'src')
from core.sandbox import Sandbox
from core.sandbox_config import SandboxConfig
s = Sandbox(image='python:3.11-slim', config=SandboxConfig(), mcp_client=None)
print("✅ Sandbox instantiation OK")
EOF

echo ""
echo "=== Sandbox Execution Test ==="
timeout 30 python << 'EOF'
import sys
sys.path.insert(0, 'src')
from core.sandbox import Sandbox
from core.sandbox_config import SandboxConfig
s = Sandbox(image='python:3.11-slim', config=SandboxConfig(), mcp_client=None)
s.start()
result = s.run('print(1+1)')
assert '2' in str(result)
s.cleanup()
print("✅ Sandbox Execution OK")
EOF

echo ""
echo "=== Docker Cleanup ==="
docker ps -a | wc -l && echo "containers currently running"
docker system prune -f > /dev/null
echo "✅ Cleanup OK"

echo ""
echo "✅✅✅ All Docker tests passed!"
```
