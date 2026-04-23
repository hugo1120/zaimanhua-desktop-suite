import json
from pathlib import Path

from zaimanhua.backend.api.dependencies import BackendContainer
from zaimanhua.backend.api.routes.settings import update_settings
from zaimanhua.backend.schemas.settings import SettingsUpdateRequest


def test_update_settings_updates_download_manager_queue_file(tmp_path):
    config_path = tmp_path / "config.json"
    initial_dir = tmp_path / "downloads-a"
    config_path.write_text(
        json.dumps({"download_dir": str(initial_dir)}, ensure_ascii=False),
        encoding="utf-8",
    )
    container = BackendContainer(config_path=str(config_path), api_client=object())
    try:
        other_root = tmp_path / "other-root"
        new_dir = other_root / "downloads-b"
        request = SettingsUpdateRequest(
            max_books=1,
            max_images=5,
            download_dir=str(new_dir),
        )

        response = update_settings(request=request, container=container, user=object())

        assert response.download_dir == str(new_dir)
        assert container.download_service._manager.download_dir == str(new_dir)
        assert Path(container.download_service._manager._queue_file).parent == new_dir.parent
    finally:
        container.close()
