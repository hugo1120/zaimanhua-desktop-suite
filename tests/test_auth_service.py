from zaimanhua.backend.app_services.auth_service import AuthService


class FakeApi:
    def __init__(self):
        self.token = ""
        self.calls = []

    def login(self, username, password):
        self.calls.append((username, password))
        self.token = "token-123"
        return True


class FakeSettingsService:
    def __init__(self, initial=None):
        self.data = dict(initial or {})

    def read_raw_config(self):
        return dict(self.data)

    def write_raw_config(self, data):
        self.data = dict(data)


def test_login_persists_plaintext_password_when_remember_enabled():
    api = FakeApi()
    settings_service = FakeSettingsService()
    service = AuthService(api=api, settings_service=settings_service)

    session = service.login("hugo", "secret", remember_password=True)

    assert api.calls == [("hugo", "secret")]
    assert session.username == "hugo"
    assert session.logged_in is True
    assert session.remember_password is True
    assert session.remembered_password == "secret"
    assert settings_service.data["username"] == "hugo"
    assert settings_service.data["token"] == "token-123"
    assert settings_service.data["remembered_password"] == "secret"


def test_login_clears_plaintext_password_when_remember_disabled():
    api = FakeApi()
    settings_service = FakeSettingsService(
        {
            "username": "legacy",
            "token": "old-token",
            "remembered_password": "old-secret",
        }
    )
    service = AuthService(api=api, settings_service=settings_service)

    session = service.login("hugo", "secret", remember_password=False)

    assert session.username == "hugo"
    assert session.logged_in is True
    assert session.remember_password is False
    assert session.remembered_password == ""
    assert settings_service.data["username"] == "hugo"
    assert settings_service.data["token"] == "token-123"
    assert "remembered_password" not in settings_service.data


def test_get_session_returns_remembered_password_state():
    api = FakeApi()
    settings_service = FakeSettingsService(
        {
            "username": "hugo",
            "token": "token-123",
            "remembered_password": "secret",
        }
    )
    service = AuthService(api=api, settings_service=settings_service)

    session = service.get_session()

    assert session.username == "hugo"
    assert session.logged_in is True
    assert session.remember_password is True
    assert session.remembered_password == "secret"
