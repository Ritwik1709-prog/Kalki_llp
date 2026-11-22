"""Offline deployment checks; never contacts Olostep or Gemini."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import yaml
ROOT = Path(__file__).resolve().parents[1]

def main():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text())
    service = blueprint["services"][0]
    assert service["plan"] == "free" and service["rootDir"] == "backend"
    assert service["healthCheckPath"] == "/health"
    vercel = json.loads((ROOT / "frontend/vercel.json").read_text())
    assert {"source":"/(.*)", "destination":"/index.html"} in vercel["rewrites"]
    print("PASS deployment manifests", flush=True)
    subprocess.run([sys.executable, "-m", "pytest", "backend/tests/test_deployment.py", "-q"], cwd=ROOT, check=True)
    for path in (ROOT / "frontend").rglob("*"):
        if not path.is_file() or any(part in {"node_modules", "dist", ".git"} for part in path.parts):
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        names = set(re.findall(r"\bVITE_[A-Z0-9_]+", content))
        assert names <= {"VITE_API_URL"}, f"Disallowed public variable in {path.relative_to(ROOT)}"
        assert not re.search(r"(?:AIza[0-9A-Za-z_-]{30,}|sk-[0-9A-Za-z]{20,}|postgres(?:ql)?://[^\s]+:[^\s]+@)", content), f"Potential secret in {path.relative_to(ROOT)}"
    print("PASS frontend public-variable allowlist and credential scan", flush=True)
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    assert npm, "npm is required"
    subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True)
    print("PASS all deployment readiness checks")

if __name__ == "__main__":
    main()
