import json
import shutil
from pathlib import Path

from zaimanhua.backend.app_services.settings_service import SettingsService


def _make_temp_dir(name: str) -> Path:
    temp_dir = Path(__file__).resolve().parents[1] / ".test_tmp" / name
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def test_settings_service_uses_env_config_path_by_default(monkeypatch):
    temp_dir = _make_temp_dir("settings_service_env")
    config_path = temp_dir / "portable" / "config.json"
    monkeypatch.setenv("ZAIMANHUA_CONFIG_PATH", str(config_path))

    service = SettingsService()

    assert service.config_path == str(config_path)
    shutil.rmtree(temp_dir)


def test_get_theme_mode_defaults_to_dark_when_missing_or_invalid():
    temp_dir = _make_temp_dir("settings_service_theme_read")
    config_path = temp_dir / "config.json"
    config_path.write_text(json.dumps({"theme_mode": "unknown"}), encoding="utf-8")
    service = SettingsService(config_path=str(config_path))

    assert service.get_theme_mode() == "dark"
    shutil.rmtree(temp_dir)


def test_set_theme_mode_normalizes_and_persists_value():
    temp_dir = _make_temp_dir("settings_service_theme_write")
    config_path = temp_dir / "config.json"
    service = SettingsService(config_path=str(config_path))

    assert service.set_theme_mode(" LIGHT ") == "light"

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["theme_mode"] == "light"
    shutil.rmtree(temp_dir)
