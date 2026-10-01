"""backfill_supervisor.sh halts after N identical no-progress stops (no network, stub backfill)."""
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts/collector/backfill_supervisor.sh"

STUB = """#!/bin/bash
# stub for backfill_chain: prints the scripted pass from $STUB_DIR/next
f="$STUB_DIR/next"
cat "$f"
"""


@pytest.fixture
def env(tmp_path):
    stub = tmp_path / "stubpy"
    stub.write_text(STUB)
    stub.chmod(0o755)
    e = dict(os.environ)
    e.update(BACKFILL_ROOT=str(tmp_path), BACKFILL_PY=str(stub), BACKFILL_STATE=str(tmp_path / "state"),
             BACKFILL_LOGDIR=str(tmp_path / "logs"), BACKFILL_CAFFEINATE="", BACKFILL_SKIP_PGREP="1",
             STUB_DIR=str(tmp_path), PATH=f"{tmp_path / 'bin'}:{e['PATH']}")
    (tmp_path / "bin").mkdir()
    osa = tmp_path / "bin" / "osascript"
    osa.write_text("#!/bin/bash\nexit 0\n")
    osa.chmod(0o755)
    return tmp_path, e


def run_pass(tmp, e, contract="GLD_20221007_171.00P",
             stat="stopped_consecutive_failures=1", fetched=0, unavailable=0):
    (tmp / "next").write_text(
        f"2026-09-24 INFO [backfill_chain.main]  [3/900] {contract}: no_bars\n"
        f"2026-09-24 INFO [backfill_chain.main]  done: {stat}  fetched={fetched}  "
        f"failed=10  unavailable={unavailable}\n")
    state = tmp / "state"
    (state / "cooldown_until").unlink(missing_ok=True)
    return subprocess.run(["/bin/bash", str(SCRIPT)], env=e, capture_output=True, text=True, cwd=tmp)


def test_halts_after_three_identical_stuck_passes(env):
    tmp, e = env
    for _ in range(2):
        run_pass(tmp, e)
        assert not (tmp / "state/HALT").exists()
    r = run_pass(tmp, e)
    assert r.returncode == 0
    halt = (tmp / "state/HALT").read_text()
    assert "GLD_20221007_171.00P" in halt and "stopped_consecutive_failures" in halt and "3 passes" in halt


def test_no_halt_when_key_changes(env):
    tmp, e = env
    for c in ("GLD_20221007_171.00P", "GLD_20221007_172.00P", "GLD_20221007_171.00P", "GLD_20221007_172.00P"):
        run_pass(tmp, e, contract=c)
    assert not (tmp / "state/HALT").exists()


def test_no_halt_with_progress(env):
    tmp, e = env
    for _ in range(4):
        run_pass(tmp, e, fetched=5)
    assert not (tmp / "state/HALT").exists()


def test_threshold_env_override(env):
    tmp, e = env
    e["STUCK_HALT_PASSES"] = "2"
    run_pass(tmp, e)
    run_pass(tmp, e)
    assert (tmp / "state/HALT").exists()
