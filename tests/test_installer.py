import importlib.util
import json
from pathlib import Path

import pytest
import tomlkit

spec = importlib.util.spec_from_file_location("phantom_installer", Path(__file__).resolve().parents[1] / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def test_codex_merge_backup_policies_and_reinstall(tmp_path):
    home = tmp_path / "home"
    config = home / ".codex/config.toml"
    config.parent.mkdir(parents=True)
    before = '# Personal settings\nmodel = "personal-model"\n[mcp_servers.other]\ncommand = "other-tool"\n[mcp_servers.phantom-local]\ndisabled_tools = ["scrape_urls"]\n'
    config.write_text(before)
    runtime = tmp_path / "runtime with spaces"
    python = runtime / ".venv/bin/python"
    [(path, backup)] = installer.configure("codex", python, runtime, home, False)
    assert path == config and backup.read_text() == before
    result = tomlkit.parse(config.read_text())
    assert result["model"] == "personal-model"
    assert result["mcp_servers"]["other"]["command"] == "other-tool"
    assert result["mcp_servers"]["phantom-local"]["disabled_tools"] == ["scrape_urls"]
    assert "# Personal settings" in config.read_text()
    assert result["mcp_servers"]["phantom-local"]["command"] == str(python)
    assert installer.configure("codex", python, runtime, home, False)[0][1] is None
    assert installer.configure("chatgpt", python, runtime, home, False)[0][1] is None


@pytest.mark.parametrize("target,filename,key", [
    ("claude", ".claude.json", "mcpServers"),
    ("cursor", ".cursor/mcp.json", "mcpServers"),
    ("vscode", ".config/Code/User/mcp.json", "servers"),
])
def test_json_configs_preserve_other_settings(tmp_path, target, filename, key):
    if target == "vscode" and not installer.sys.platform.startswith("linux"):
        pytest.skip("Linux default profile path")
    config = tmp_path / filename
    config.parent.mkdir(parents=True, exist_ok=True)
    before = json.dumps({"keep": {"setting": True}, key: {"other": {"command": "other-tool"}}})
    config.write_text(before)
    config.chmod(0o600)
    [(path, backup)] = installer.configure(target, Path("/runtime/python"), Path("/runtime"), tmp_path, False)
    result = json.loads(config.read_text())
    assert result["keep"] == {"setting": True}
    assert result[key]["other"]["command"] == "other-tool"
    assert result[key]["phantom-local"]["command"] == "/runtime/python"
    assert backup.read_text() == before
    assert path.stat().st_mode & 0o777 == 0o600


def test_opencode_both_json_and_jsonc(tmp_path):
    directory = tmp_path / ".config/opencode"
    directory.mkdir(parents=True)
    json_path = directory / "opencode.json"
    jsonc_path = directory / "opencode.jsonc"
    json_path.write_text('{"model": "keep-this", "mcp": {"other": {"type": "remote", "url": "https://example.com/mcp"}}}')
    jsonc_path.write_text('// comments and trailing comma\n{"permission": "ask", "mcp": {"phantom-local": {"enabled": false}},}')
    changes = installer.configure("opencode", Path("/runtime/python"), Path("/runtime"), tmp_path, False)
    assert len(changes) == 2
    result = json.loads(json_path.read_text())
    assert result["model"] == "keep-this"
    assert result["mcp"]["other"]["type"] == "remote"
    for path in [json_path, jsonc_path]:
        assert json.loads(path.read_text())["mcp"]["phantom-local"] == {
            "type": "local", "command": ["/runtime/python", "/runtime/scripts/run_mcp.py"],
            "enabled": True, "timeout": 20000,
        }
    assert json.loads(jsonc_path.read_text())["permission"] == "ask"


def test_invalid_existing_configuration_is_not_overwritten(tmp_path):
    directory = tmp_path / ".config/opencode"
    directory.mkdir(parents=True)
    first = directory / "opencode.json"
    second = directory / "opencode.jsonc"
    first.write_text('{"model": "keep"}')
    second.write_text("not valid json")
    with pytest.raises(ValueError):
        installer.configure("opencode", Path("/runtime/python"), Path("/runtime"), tmp_path, False)
    assert first.read_text() == '{"model": "keep"}'
    assert second.read_text() == "not valid json"
    assert not list(directory.glob("*.phantom-backup-*"))


def test_menu_multi_select_and_web_not_claimed_installed(monkeypatch):
    answers = iter(["9", "nonsense", "1,3,4,1"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert installer.choose_targets() == ["codex", "claude", "opencode"]


def test_runtime_copy_includes_original_license(tmp_path, monkeypatch):
    source = tmp_path / "source"
    (source / "phantom_local").mkdir(parents=True)
    (source / "phantom_local/__init__.py").write_text("")
    (source / "scripts").mkdir()
    (source / "scripts/run_mcp.py").write_text("# entrypoint\n")
    (source / "requirements-local.txt").write_text("# fixture\n")
    notice = b"Required Notice: test author\n\nLicense fixture\n"
    (source / "LICENSE").write_bytes(notice)
    destination = tmp_path / "installed"
    python = installer.runtime_python(destination)
    python.parent.mkdir(parents=True)
    python.write_text("# mocked runtime\n")
    monkeypatch.setattr(installer, "SOURCE", source)
    monkeypatch.setattr(installer, "run", lambda *args, **kwargs: None)
    assert installer.setup_runtime(destination, browser=False) == python
    assert (destination / "LICENSE").read_bytes() == notice
