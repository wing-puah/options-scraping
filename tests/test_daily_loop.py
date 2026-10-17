import re
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "daily_loop.sh"


def _run(tmp_path, *flags):
    return subprocess.run(
        ["bash", str(SCRIPT), "--dry-run", *flags],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )


def test_dry_run_prints_all_six_steps(tmp_path):
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    for frag in ("fetch_mech_regime.py", "scripts.backtest --config",
                 "scripts.backtest.proxy", "python3 -m scripts.journal\n",
                 "scripts.journal recommend", "backup_research_caches.py push"):
        assert frag in r.stdout + "\n", frag
    assert re.search(r"--start \d{4}-\d{2}-\d{2}", r.stdout)


def test_start_override_and_skips(tmp_path):
    r = _run(tmp_path, "--skip-backtest", "--skip-backup", "--start", "2026-09-23")
    assert r.returncode == 0
    assert "scripts.backtest" not in r.stdout
    assert "backup_research_caches" not in r.stdout
    assert "START=2026-09-23" in r.stdout
