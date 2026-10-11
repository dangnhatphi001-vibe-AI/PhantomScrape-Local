import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import pytest

pytestmark = pytest.mark.skipif(os.name == "nt", reason="Bash bootstrap is for macOS/Linux; Windows uses PowerShell")


def fixture_archive(path):
    files = {
        "scripts/install.py": '''import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
assert (root / "LICENSE").read_text() == "Required Notice: fixture author\\n"
assert sys.argv[1:] == ["--targets", "codex"]
assert input("Menu: ") == "8"
print("REMOTE INSTALLER CALLED")
''',
        "LICENSE": "Required Notice: fixture author\n",
    }
    with tarfile.open(path, "w:gz") as archive:
        for filename, contents in files.items():
            data = contents.encode()
            info = tarfile.TarInfo("PhantomScrape-Local-main/" + filename)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))


def test_downloaded_bootstrap_keeps_menu_stdin_arguments_and_cleans_up(tmp_path):
    source = Path(__file__).resolve().parents[1]
    script = tmp_path / "downloaded-install.sh"
    shutil.copy2(source / "install.sh", script)
    fixture_archive(tmp_path / "archive.tar.gz")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text('#!/usr/bin/env python3\nimport os, shutil, sys\nassert "https://codeload.github.com/dangnhatphi001-vibe-AI/PhantomScrape-Local/tar.gz/refs/heads/main" in sys.argv\nshutil.copyfile(os.environ["PHANTOM_TEST_ARCHIVE"], sys.argv[sys.argv.index("-o") + 1])\n')
    curl.chmod(0o755)
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
           "TMPDIR": str(temporary), "PHANTOM_TEST_ARCHIVE": str(tmp_path / "archive.tar.gz")}
    result = subprocess.run(["bash", str(script), "--targets", "codex"], cwd=tmp_path,
                            input="8\n", text=True, capture_output=True, env=env, timeout=10)
    assert result.returncode == 0, result.stderr
    assert "REMOTE INSTALLER CALLED" in result.stdout
    assert list(temporary.iterdir()) == []


def test_failed_download_does_not_run_installer(tmp_path):
    source = Path(__file__).resolve().parents[1]
    script = tmp_path / "downloaded-install.sh"
    shutil.copy2(source / "install.sh", script)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text("#!/usr/bin/env bash\nexit 22\n")
    curl.chmod(0o755)
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "TMPDIR": str(temporary)}
    result = subprocess.run(["bash", str(script)], cwd=tmp_path, capture_output=True, text=True, env=env, timeout=10)
    assert result.returncode == 22
    assert list(temporary.iterdir()) == []
