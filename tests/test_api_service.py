from zaimanhua.services.api import ZaimanhuaAPI


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code
        self.encoding = "utf-8"


def test_search_web_scrape_extracts_author_from_html(monkeypatch):
    html = """
    <html>
      <body>
        <ul>
          <li>
            <a href="/details/60131"><img src="https://example.com/cover.jpg" /></a>
            <p class="title"><a href="/details/60131" title="平屋小品">平屋小品</a></p>
            <p class="auth">真造圭伍</p>
            <p class="newPage">最新：第82话</p>
          </li>
        </ul>
      </body>
    </html>
    """

    api = ZaimanhuaAPI()
    monkeypatch.setattr(api.session, "get", lambda *args, **kwargs: DummyResponse(html))

    results = api.search_web_scrape("平屋小品")

    assert results == [
        {
            "title": "平屋小品",
            "id": "60131",
            "author": "真造圭伍",
            "source": "web",
        }
    ]
