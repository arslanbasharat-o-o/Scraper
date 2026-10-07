from types import SimpleNamespace

import pytest

from scrapers import fetch_pipeline
from scrapers.browser_fetcher import browser_fetch_mode


class FakeResponse:
    def __init__(self, status_code, text, url):
        self.status_code = status_code
        self.text = text
        self.url = url
        self.headers = {}


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, *_args, **_kwargs):
        self.calls += 1
        return self.responses[min(self.calls - 1, len(self.responses) - 1)]


def test_pipeline_returns_http_success_without_expensive_fallback(monkeypatch):
    session = FakeSession([FakeResponse(200, "<html>catalog</html>", "https://supplier.test/catalog")])
    monkeypatch.setattr(fetch_pipeline, "scrapling_enabled", lambda: False)
    monkeypatch.setattr(fetch_pipeline, "botasaurus_fetch_html", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("browser should not run")))

    result = fetch_pipeline.fetch_with_pipeline(session, "https://supplier.test/catalog", http_attempts=2)

    assert result is not None
    assert result.transport == "http"
    assert result.http_attempts == 1
    assert session.calls == 1


def test_pipeline_falls_through_scrapling_before_botasaurus(monkeypatch):
    session = FakeSession([FakeResponse(403, "Access denied", "https://supplier.test/product")])
    transports = []

    monkeypatch.setenv("SCRAPER_LOCAL_BROWSER_FALLBACK", "1")
    monkeypatch.setattr(fetch_pipeline, "scrapling_enabled", lambda: True)
    monkeypatch.setattr(fetch_pipeline, "_scrapling_http", lambda *_args, **_kwargs: (403, "https://supplier.test/product", "Access denied"))
    monkeypatch.setattr(fetch_pipeline, "_scrapling_stealth", lambda *_args, **_kwargs: transports.append("scrapling-stealth") or (200, "https://supplier.test/product", "<html>rendered</html>"))
    monkeypatch.setattr(fetch_pipeline, "botasaurus_fetch_html", lambda *_args, **_kwargs: transports.append("botasaurus") or SimpleNamespace(final_url=_args[0], html="<html>fallback</html>"))

    result = fetch_pipeline.fetch_with_pipeline(session, "https://supplier.test/product", http_attempts=1)

    assert result is not None
    assert result.transport == "scrapling-stealth"
    assert transports == ["scrapling-stealth"]


def test_scrapling_cloudflare_solver_is_enabled_by_default_and_can_be_disabled(monkeypatch):
    monkeypatch.delenv("SCRAPER_SCRAPLING_SOLVE_CLOUDFLARE", raising=False)
    assert fetch_pipeline.scrapling_cloudflare_solver_enabled() is True
    monkeypatch.setenv("SCRAPER_SCRAPLING_SOLVE_CLOUDFLARE", "0")
    assert fetch_pipeline.scrapling_cloudflare_solver_enabled() is False


def test_browser_fallback_is_enabled_by_default_and_can_be_disabled(monkeypatch):
    monkeypatch.delenv("SCRAPER_LOCAL_BROWSER_FALLBACK", raising=False)
    monkeypatch.setattr(fetch_pipeline, "should_use_browser_fetch", lambda: False)
    monkeypatch.setattr(fetch_pipeline, "browser_fetch_requested", lambda: False)
    assert fetch_pipeline.browser_fallback_enabled() is True
    monkeypatch.setenv("SCRAPER_LOCAL_BROWSER_FALLBACK", "0")
    assert fetch_pipeline.browser_fallback_enabled() is False


def test_stealth_fallback_gets_cloudflare_timeout_budget(monkeypatch):
    session = FakeSession([FakeResponse(403, "Access denied", "https://supplier.test/product")])
    seen = []
    monkeypatch.setenv("SCRAPER_LOCAL_BROWSER_FALLBACK", "1")
    monkeypatch.setenv("SCRAPER_SCRAPLING_STEALTH_TIMEOUT", "60")
    monkeypatch.setattr(fetch_pipeline, "scrapling_enabled", lambda: True)
    monkeypatch.setattr(fetch_pipeline, "_scrapling_http", lambda *_args, **_kwargs: (403, "https://supplier.test/product", "denied"))
    monkeypatch.setattr(fetch_pipeline, "_scrapling_stealth", lambda _url, timeout, *_args, **_kwargs: seen.append(timeout) or (200, "https://supplier.test/product", "<html>recovered</html>"))

    result = fetch_pipeline.fetch_with_pipeline(session, "https://supplier.test/product", http_attempts=1, browser_timeout=18)

    assert result is not None
    assert result.transport == "scrapling-stealth"
    assert seen == [60]


def test_explicit_browser_mode_skips_http_and_uses_one_browser_fetch(monkeypatch):
    session = FakeSession([FakeResponse(200, "should not be used", "https://supplier.test/product")])
    calls = []

    def browser_fetch(url, **_kwargs):
        calls.append(url)
        return SimpleNamespace(final_url=url, html="<html>browser</html>")

    with browser_fetch_mode(True):
        result = fetch_pipeline.fetch_with_pipeline(
            session,
            "https://supplier.test/product",
            browser_fetch_fn=browser_fetch,
        )

    assert result is not None
    assert result.transport == "botasaurus"
    assert calls == ["https://supplier.test/product"]
    assert session.calls == 0


def test_http_first_mode_still_allows_configured_browser_fallback(monkeypatch):
    session = FakeSession([FakeResponse(403, "Access denied", "https://supplier.test/product")])
    monkeypatch.setenv("SCRAPER_LOCAL_BROWSER_FALLBACK", "1")
    monkeypatch.setattr(fetch_pipeline, "scrapling_enabled", lambda: False)
    monkeypatch.setattr(fetch_pipeline, "botasaurus_fetch_html", lambda url, **_: SimpleNamespace(final_url=url, html="<html>recovered</html>"))

    with browser_fetch_mode(False):
        result = fetch_pipeline.fetch_with_pipeline(session, "https://supplier.test/product")

    assert result.transport == "botasaurus"
    assert session.calls == 1
    assert session.fetch_browser_attempted is True


def test_browser_disable_flag_stops_after_scrapling_http(monkeypatch):
    session = FakeSession([FakeResponse(403, "Access denied", "https://supplier.test/product")])
    monkeypatch.setenv("SCRAPER_LOCAL_BROWSER_FALLBACK", "0")
    monkeypatch.setenv("SCRAPER_USE_BROWSER", "0")
    monkeypatch.setattr(fetch_pipeline, "scrapling_enabled", lambda: True)
    calls = []
    monkeypatch.setattr(fetch_pipeline, "_scrapling_http", lambda *_args: calls.append("http") or (403, "https://supplier.test/product", "denied"))
    monkeypatch.setattr(fetch_pipeline, "_scrapling_stealth", lambda *_args, **_kwargs: pytest.fail("browser disabled"))

    with browser_fetch_mode(False):
        result = fetch_pipeline.fetch_with_pipeline(session, "https://supplier.test/product")

    assert result is None
    assert calls == ["http"]
    assert session.fetch_browser_attempted is False


def test_pipeline_rejects_error_status_from_stealth_and_runs_final_browser_once(monkeypatch):
    session = FakeSession([FakeResponse(403, "denied", "https://supplier.test/product")])
    monkeypatch.setenv("SCRAPER_LOCAL_BROWSER_FALLBACK", "1")
    monkeypatch.setattr(fetch_pipeline, "scrapling_enabled", lambda: True)
    calls = []
    monkeypatch.setattr(fetch_pipeline, "_scrapling_http", lambda *_args: calls.append("scrapling-http") or (403, "https://supplier.test/product", "denied"))
    monkeypatch.setattr(fetch_pipeline, "_scrapling_stealth", lambda *_args, **_kwargs: calls.append("stealth") or (500, "https://supplier.test/product", "<html>server error</html>"))
    monkeypatch.setattr(fetch_pipeline, "botasaurus_fetch_html", lambda url, **_: calls.append("botasaurus") or SimpleNamespace(final_url=url, html="<html>catalog</html>"))

    result = fetch_pipeline.fetch_with_pipeline(session, "https://supplier.test/product")
    assert result.transport == "botasaurus"
    assert calls == ["scrapling-http", "stealth", "botasaurus"]


@pytest.mark.parametrize("status", [404, 410])
def test_terminal_http_status_preserved_without_fallback(monkeypatch, status):
    session = FakeSession([FakeResponse(status, "gone", "https://supplier.test/product")])
    monkeypatch.setattr(fetch_pipeline, "_scrapling_http", lambda *_args: pytest.fail("terminal response must not retry"))
    result = fetch_pipeline.fetch_with_pipeline(session, "https://supplier.test/product")
    fetch_pipeline.copy_fetch_metadata(session, "phonelcdparts")
    assert result is None
    assert session.phonelcdparts_last_status == status
    assert session.calls == 1


def test_success_status_with_cf_challenge_header_not_accepted(monkeypatch):
    response = FakeResponse(200, "<html>wait</html>", "https://supplier.test/product")
    response.headers = {"Cf-Mitigated": "challenge"}
    monkeypatch.setattr(fetch_pipeline, "scrapling_enabled", lambda: False)
    result = fetch_pipeline.fetch_with_pipeline(FakeSession([response]), response.url, allow_browsers=False)
    assert result is None


def test_stop_callback_aborts_before_fallback(monkeypatch):
    session = FakeSession([FakeResponse(403, "denied", "https://supplier.test/product")])
    def stop():
        if session.calls:
            raise RuntimeError("paused at request boundary")
    session.scraper_stop_check = stop
    monkeypatch.setattr(fetch_pipeline, "_scrapling_http", lambda *_args: pytest.fail("cancelled"))
    with pytest.raises(RuntimeError, match="paused at request boundary"):
        fetch_pipeline.fetch_with_pipeline(session, "https://supplier.test/product")


def test_browser_slot_timeout_does_not_release_an_unacquired_slot(monkeypatch):
    from scrapers import browser_fetcher
    class FullSemaphore:
        def acquire(self, *, timeout):
            assert timeout == 3
            return False
        def release(self):
            pytest.fail("unacquired slot released")
    monkeypatch.setattr(browser_fetcher, "_get_local_browser_semaphore", lambda: FullSemaphore())
    monkeypatch.setenv("SCRAPER_LOCAL_BROWSER_SLOT_TIMEOUT", "3")
    with pytest.raises(TimeoutError, match="waiting for a local browser slot"):
        with browser_fetcher._local_browser_slot(timeout=60):
            pytest.fail("full browser slot acquired")


def test_scrapling_uses_one_warm_thread_per_slot(monkeypatch):
    import threading
    from contextlib import contextmanager
    from concurrent.futures import ThreadPoolExecutor
    @contextmanager
    def single_slot(**_kwargs):
        with lock:
            yield 0
    lock = threading.Lock()
    calls = []
    monkeypatch.setattr(fetch_pipeline, "_local_browser_slot", single_slot)
    monkeypatch.setattr(fetch_pipeline, "_stealth_fetch_on_worker", lambda *_: calls.append(threading.get_ident()) or (200, "url", "html", {}))
    monkeypatch.setattr(fetch_pipeline, "_STEALTH_WORKERS", {})
    with ThreadPoolExecutor(max_workers=4) as callers:
        results = list(callers.map(lambda _: fetch_pipeline._scrapling_stealth("url", 5, None), range(8)))
    assert len(results) == 8
    assert len(set(calls)) == 1
    assert len(fetch_pipeline._STEALTH_WORKERS) == 1
    for worker in fetch_pipeline._STEALTH_WORKERS.values():
        worker.shutdown()


def test_broken_warm_scrapling_session_is_closed_and_replaced(monkeypatch):
    import sys
    import threading
    from scrapers import botasaurus_wrapper
    instances = []
    fetch_options = []
    class StealthySession:
        def __init__(self, **_kwargs):
            self.closed = False
            instances.append(self)
        def __enter__(self):
            return self
        def fetch(self, url, **_kwargs):
            fetch_options.append(_kwargs)
            if self is instances[0]:
                raise RuntimeError("browser disconnected")
            return SimpleNamespace(body=b"<html>catalog</html>", status=200, url=url, headers={})
        def close(self):
            self.closed = True
    monkeypatch.setattr(fetch_pipeline, "_STEALTH_SESSIONS", threading.local())
    monkeypatch.setitem(sys.modules, "scrapling.fetchers", SimpleNamespace(StealthySession=StealthySession))
    monkeypatch.setattr(botasaurus_wrapper, "resolve_chrome_executable", lambda: None)
    with pytest.raises(RuntimeError, match="browser disconnected"):
        fetch_pipeline._stealth_fetch_on_worker("url", 5, None, None)
    assert instances[0].closed is True
    assert fetch_pipeline._STEALTH_SESSIONS.current is None
    result = fetch_pipeline._stealth_fetch_on_worker("url", 5, None, None)
    assert result[0] == 200
    assert len(instances) == 2
    assert all(options["solve_cloudflare"] is True for options in fetch_options)


def test_standard_engine_cancellation_is_not_recorded_as_supplier_block():
    from scrapers import scraper_engine
    session = FakeSession([FakeResponse(200, "<html>catalog</html>", "https://supplier.test/product")])
    def stop():
        raise RuntimeError("scrape paused")
    session.scraper_stop_check = stop
    with pytest.raises(RuntimeError, match="scrape paused"):
        scraper_engine.get_html(session, "https://supplier.test/product")
    assert session.mobilesentrix_blocked is False
    assert session.mobilesentrix_last_error == ""
    assert session.calls == 0
