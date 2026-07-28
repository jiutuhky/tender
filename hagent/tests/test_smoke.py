import subprocess
import sys

import hagent


def test_version_exposed():
    assert hagent.__version__ == "0.0.1"


def test_cli_runs():
    result = subprocess.run(
        [sys.executable, "-m", "hagent"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "hagent 0.0.1" in result.stdout
