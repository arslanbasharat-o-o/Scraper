import importlib
import sys

import pytest


def _fresh_app(tmp_path, monkeypatch):
    site_dbs = tmp_path / "site_dbs"
    monkeypatch.setenv("DATABASES_DIR", str(site_dbs))
    monkeypatch.delenv("DATABASE_PATH", raising=False)

    for module_name in ("app", "database"):
        sys.modules.pop(module_name, None)

    app_module = importlib.import_module("app")
    app_module.app.config["TESTING"] = True
    app_module.ensure_automation_scheduler_started = lambda: None
    return app_module


def test_scrape_requires_at_least_one_url(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)

    with app_module.app.test_client() as client:
        response = client.post("/api/scrape", json={})

    payload = response.get_json()

    assert response.status_code == 400
    assert payload["error"] == "At least one URL is required."
    assert payload["history_saved"] is False
    assert payload["count"] == 0
    assert app_module.db_manager.get_history_list(limit=10) == []


def test_scrape_uses_http_first_when_browser_not_requested(tmp_path, monkeypatch):
    """
    Safari-TLS HTTP is the PRIMARY scraping transport.
    When use_browser=False is passed, execute_scrape_workflow must report
    using_browser=False regardless of other settings.

    This test was previously named test_scrape_always_uses_botasaurus_mode and
    incorrectly asserted using_browser=True even when use_browser=False.
    That encoded an obsolete browser-first requirement. The authoritative
    requirement is: HTTP scraping first, browser only as a fallback when HTTP
    cannot retrieve usable supplier data.
    """
    app_module = _fresh_app(tmp_path, monkeypatch)

    monkeypatch.setattr(app_module, "build_session", lambda **_kwargs: (object(), False))
    monkeypatch.setattr(
        app_module,
        "scrape_url",
        lambda *_args, **_kwargs: [app_module.Item(
            url="https://example.com/product",
            site="example.com",
            title="Test Product",
            price_value=1.0,
            price_currency="USD",
            price_text="$1.00",
            discounted_value=1.0,
            discounted_formatted="$1.00",
            original_formatted="$1.00",
            source="test",
            image_url="",
        )],
    )

    result = app_module.execute_scrape_workflow(
        ["https://example.com/product"],
        use_browser=False,
        use_parallel=False,
    )

    # HTTP-first: when browser is not requested, using_browser must be False.
    assert result["using_browser"] is False
    assert result["count"] == 1


def test_scrape_reports_browser_used_when_browser_requested(tmp_path, monkeypatch):
    """When use_browser=True is explicitly requested, using_browser must be True."""
    app_module = _fresh_app(tmp_path, monkeypatch)

    monkeypatch.setattr(app_module, "build_session", lambda **_kwargs: (object(), False))
    monkeypatch.setattr(
        app_module,
        "scrape_url",
        lambda *_args, **_kwargs: [app_module.Item(
            url="https://www.mobilesentrix.com/product",
            site="mobilesentrix.com",
            title="HTTP Fallback Product",
            price_value=5.0,
            price_currency="USD",
            price_text="$5.00",
            discounted_value=5.0,
            discounted_formatted="$5.00",
            original_formatted="$5.00",
            source="test",
            image_url="",
        )],
    )

    result = app_module.execute_scrape_workflow(
        ["https://www.mobilesentrix.com/product"],
        use_browser=True,
        use_parallel=False,
    )

    # When browser mode is explicitly requested, it is reflected in the result.
    assert result["using_browser"] is True
    assert result["count"] == 1


def test_extractor_locks_botasaurus_rendering_on(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)

    with app_module.app.test_client() as client:
        response = client.get("/")

    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="useBrowserApi" class="toggle-cb" checked disabled' in html


def test_error_placeholder_items_do_not_count_as_products(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)

    def fake_build_session(**_kwargs):
        return object(), False

    def fake_scrape_url(_session, url, _rules, _crawl_pagination, _max_pages, _delay_ms, _logger):
        return [app_module.Item(
            url=url,
            site="example.com",
            title="",
            price_value=None,
            price_currency=None,
            price_text="fetch_failed: blocked",
            discounted_value=None,
            discounted_formatted="",
            original_formatted="",
            source="error",
            image_url="",
        )]

    monkeypatch.setattr(app_module, "build_session", fake_build_session)
    monkeypatch.setattr(app_module, "scrape_url", fake_scrape_url)

    result = app_module.execute_scrape_workflow(
        ["https://www.mobilesentrix.com/example"],
        use_browser=False,
        use_parallel=False,
    )

    assert result["count"] == 0
    assert result["history_saved"] is False
    assert result["target_errors"]


def test_xcell_listing_does_not_auto_enable_slow_detail_scan(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRAPER_LOCAL_BROWSER_FALLBACK", "1")
    app_module = _fresh_app(tmp_path, monkeypatch)
    calls = {"enrich": 0, "enrich_details": None}

    def fake_build_session(**_kwargs):
        class Session:
            xcell_last_error = ""
            xcell_blocked = False

        return Session(), False

    def fake_scrape_url(_session, _url, _rules, _crawl_pagination, _max_pages, _delay_ms, _logger):
        return [app_module.xcell_scraper_engine.Item(
            title="Outer OLED Assembly for Samsung ZFold 7 5G",
            url="https://xcellparts.com/product/outter-oled-assembly-without-frame-for-samsung-zfold-7-5g/",
            original=12.0,
            discounted=12.0,
            original_formatted="$12.00",
            discounted_formatted="$12.00",
            stock_status="In Stock",
        )]

    def fake_enrich(*_args, **_kwargs):
        calls["enrich"] += 1
        calls["enrich_details"] = _kwargs.get("enrich_details")
        return _args[0], 0

    monkeypatch.setattr(app_module.xcell_scraper_engine, "build_session", fake_build_session)
    monkeypatch.setattr(app_module.xcell_scraper_engine, "scrape_url", fake_scrape_url)
    monkeypatch.setattr(app_module, "enrich_scraped_items", fake_enrich)

    result = app_module.execute_scrape_workflow(
        ["https://xcellparts.com/product-category/samsung/galaxy-z-series/galaxy-z-fold-7-5g/"],
        use_browser=True,
        use_parallel=False,
    )

    assert result["count"] == 1
    assert result["auto_enrich_details"] is False
    assert result["enrich_details"] is True
    assert calls["enrich"] == 1
    assert calls["enrich_details"] is True


def test_phase_two_pause_aborts_detail_enrichment(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    items = [
        app_module.Item(
            url="https://example.com/product-a",
            site="example.com",
            title="Product A",
            price_value=1.0,
            price_currency="USD",
            price_text="$1.00",
            discounted_value=1.0,
            discounted_formatted="$1.00",
            original_formatted="$1.00",
            source="test",
            image_url="",
        )
    ]

    monkeypatch.setattr(app_module, "build_session", lambda **_kwargs: (object(), False))
    monkeypatch.setattr(app_module, "enrich_standard_item_details", lambda _session, item, *_args, **_kwargs: item)

    def pause_on_phase_two(progress):
        if progress.get("phase") == 2 and progress.get("phase2_completed"):
            raise app_module.AutomationRunPaused("Paused during detail enrichment.")

    try:
        app_module.enrich_scraped_items(
            items,
            rules={},
            retries=1,
            verify_ssl=True,
            use_curl=True,
            enrich_details=True,
            progress_callback=pause_on_phase_two,
        )
    except app_module.AutomationRunPaused as exc:
        assert "Paused during detail enrichment" in str(exc)
    else:
        raise AssertionError("Phase 2 enrichment swallowed AutomationRunPaused")


def test_parallel_phase_one_pause_is_not_swallowed_as_target_error(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)

    monkeypatch.setattr(app_module, "build_session", lambda **_kwargs: (object(), False))
    monkeypatch.setattr(
        app_module,
        "scrape_url",
        lambda _sess, url, *_args, **_kwargs: [app_module.Item(
            url=f"{url}/product",
            site="example.com",
            title="Paused Product",
            price_value=1.0,
            price_currency="USD",
            price_text="$1.00",
            discounted_value=1.0,
            discounted_formatted="$1.00",
            original_formatted="$1.00",
            source="test",
            image_url="",
        )],
    )

    def pause_on_progress(_progress):
        raise app_module.AutomationRunPaused("Paused during category crawl.")

    with pytest.raises(app_module.AutomationRunPaused):
        app_module.execute_scrape_workflow(
            ["https://example.com/category-a", "https://example.com/category-b"],
            use_parallel=True,
            enrich_details=False,
            progress_callback=pause_on_progress,
        )


def test_detail_stop_check_aborts_enrichment_before_next_request(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    items = [
        app_module.Item(
            url=f"https://example.com/product-{idx}",
            site="example.com",
            title=f"Product {idx}",
            price_value=1.0,
            price_currency="USD",
            price_text="$1.00",
            discounted_value=1.0,
            discounted_formatted="$1.00",
            original_formatted="$1.00",
            source="test",
            image_url="",
        )
        for idx in range(2)
    ]

    monkeypatch.setattr(app_module, "build_session", lambda **_kwargs: (object(), False))
    monkeypatch.setattr(app_module, "enrich_standard_item_details", lambda _session, item, *_args, **_kwargs: item)

    def stop_immediately():
        raise app_module.AutomationRunPaused("Paused before detail request.")

    with pytest.raises(app_module.AutomationRunPaused):
        app_module.enrich_scraped_items(
            items,
            rules={},
            retries=1,
            verify_ssl=True,
            use_curl=True,
            enrich_details=True,
            stop_check=stop_immediately,
        )


def test_supplier_worker_profiles_restore_fast_http_concurrency(tmp_path, monkeypatch):
    monkeypatch.delenv("SCRAPER_XCELL_DETAIL_WORKERS", raising=False)
    monkeypatch.delenv("XCELL_MAX_WORKERS", raising=False)
    monkeypatch.delenv("SCRAPER_XCELL_MAX_WORKERS", raising=False)
    app_module = _fresh_app(tmp_path, monkeypatch)

    assert app_module.resolve_scraper_worker_limit("xcell", "detail") == 64
    assert app_module.resolve_scraper_worker_limit("phonelcdparts", "detail") == 40
    assert app_module.resolve_scraper_worker_limit("parts4cells", "detail") == 32
    assert app_module.resolve_scraper_worker_limit("gadgetfix", "detail") == 24
    assert app_module.resolve_scraper_worker_limit("standard", "detail") == 8
    assert app_module.resolve_scraper_worker_limit("mobilesentrix_canada", "detail") == 4
    assert app_module.resolve_scraper_worker_limit("standard", "phase1") == 24

    monkeypatch.setenv("SCRAPER_XCELL_DETAIL_WORKERS", "999")
    assert app_module.resolve_scraper_worker_limit("xcell", "detail") == app_module.SCRAPER_WORKER_HARD_CAP


def test_memory_profiles_scale_worker_limits_for_local_and_server(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)

    monkeypatch.setenv("SCRAPER_WORKER_PROFILE", "local_10gb")
    assert app_module.resolve_scraper_worker_hard_cap() == 64
    assert app_module.resolve_scraper_worker_limit("phonelcdparts", "detail") == 32

    monkeypatch.setenv("SCRAPER_WORKER_PROFILE", "server_40gb")
    assert app_module.resolve_scraper_worker_hard_cap() == 160
    assert app_module.resolve_scraper_worker_limit("phonelcdparts", "detail") == 80


def test_phase_two_reuses_phase_one_supplier_cookies(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    observed_cookies = []

    class Cookies:
        def __init__(self):
            self.values = {}

        def update(self, values):
            self.values.update(values)

    class Session:
        def __init__(self):
            self.cookies = Cookies()

        def close(self):
            return None

    def fake_enrich(session, item, *_args, **_kwargs):
        observed_cookies.append(dict(session.cookies.values))
        return item

    monkeypatch.setattr(app_module, "build_session", lambda **_kwargs: (Session(), False))
    monkeypatch.setattr(app_module, "enrich_standard_item_details", fake_enrich)
    item = app_module.Item(
        url="https://example.com/product",
        site="example.com",
        title="Cookie Product",
        price_value=1.0,
        price_currency="USD",
        price_text="$1.00",
        discounted_value=1.0,
        discounted_formatted="$1.00",
        original_formatted="$1.00",
        source="test",
        image_url="",
    )

    app_module.enrich_scraped_items(
        [item],
        rules={},
        retries=1,
        verify_ssl=True,
        use_curl=True,
        session_cookies_by_engine={"standard": {"supplier_session": "ready"}},
    )

    assert observed_cookies == [{"supplier_session": "ready"}]


def test_mobilesentrix_sku_missing_after_http_is_retried_in_browser(tmp_path, monkeypatch):
    """MobileSentrix keeps HTTP/Safari primary but retries a blocked detail page in a browser."""
    monkeypatch.setenv("SCRAPER_LOCAL_BROWSER_FALLBACK", "1")
    app_module = _fresh_app(tmp_path, monkeypatch)
    calls = []

    class Session:
        mobilesentrix_last_status = None

        def close(self):
            return None

    def fake_build_session(**_kwargs):
        return Session(), False

    def fake_enrich(session, item, *_args, **_kwargs):
        from scrapers.browser_fetcher import should_use_browser_fetch

        calls.append(should_use_browser_fetch())
        if not should_use_browser_fetch():
            session.mobilesentrix_last_status = 403
            raise RuntimeError("blocked by anti-bot challenge (403)")
        item.sku = "MS-BROWSER-SKU"
        return item

    monkeypatch.setattr(app_module, "build_session", fake_build_session)
    monkeypatch.setattr(app_module, "enrich_standard_item_details", fake_enrich)
    item = app_module.Item(
        url="https://www.mobilesentrix.com/product/iphone-screen",
        site="www.mobilesentrix.com",
        title="iPhone Screen",
        price_value=10.0,
        price_currency="USD",
        price_text="$10.00",
        discounted_value=10.0,
        discounted_formatted="$10.00",
        original_formatted="$10.00",
        source="listing",
        image_url="",
    )

    enriched, _ = app_module.enrich_scraped_items(
        [item],
        rules={},
        retries=1,
        verify_ssl=True,
        use_curl=True,
        enrich_details=True,
    )

    assert calls == [False, True]
    assert enriched[0].sku == "MS-BROWSER-SKU"


def test_txparts_missing_sku_detail_is_not_skipped(tmp_path, monkeypatch):
    """All suppliers, including TXParts, must enter phase-two SKU enrichment."""
    app_module = _fresh_app(tmp_path, monkeypatch)

    class Session:
        def close(self):
            return None

    def fake_enrich(_session, item, *_args, **_kwargs):
        item.sku = "TX-PHASE2-SKU"
        return item

    monkeypatch.setattr(app_module.txparts_scraper_engine, "build_session", lambda **_kwargs: (Session(), False))
    monkeypatch.setattr(app_module.txparts_scraper_engine, "enrich_item_details", fake_enrich)
    item = app_module.Item(
        url="https://txparts.com/product/iphone-screen",
        site="txparts.com",
        title="TXParts Screen",
        price_value=10.0,
        price_currency="USD",
        price_text="$10.00",
        discounted_value=10.0,
        discounted_formatted="$10.00",
        original_formatted="$10.00",
        source="listing",
        image_url="",
    )

    enriched, _ = app_module.enrich_scraped_items(
        [item],
        rules={},
        retries=1,
        verify_ssl=True,
        use_curl=True,
        enrich_details=True,
        use_browser=False,
    )

    assert enriched[0].sku == "TX-PHASE2-SKU"


def test_resume_checkpoint_items_skip_completed_targets_and_still_enrich(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    scraped_urls = []
    enriched_urls = []

    class Session:
        def close(self):
            return None

    def fake_scrape(_session, url, *_args, **_kwargs):
        scraped_urls.append(url)
        return [app_module.Item(
            url=f"{url}/product-b",
            site="example.com",
            title="Product B",
            price_value=2.0,
            price_currency="USD",
            price_text="$2.00",
            discounted_value=2.0,
            discounted_formatted="$2.00",
            original_formatted="$2.00",
            source="test",
            image_url="",
        )]

    def fake_enrich(_session, item, *_args, **_kwargs):
        enriched_urls.append(item.url)
        item.sku = f"SKU-{len(enriched_urls)}"
        return item

    monkeypatch.setattr(app_module, "build_session", lambda **_kwargs: (Session(), False))
    monkeypatch.setattr(app_module, "scrape_url", fake_scrape)
    monkeypatch.setattr(app_module, "enrich_standard_item_details", fake_enrich)

    completed_url = "https://example.com/category-a"
    pending_url = "https://example.com/category-b"
    checkpoint_item = {
        "url": f"{completed_url}/product-a",
        "site": "example.com",
        "title": "Product A",
        "price_value": 1.0,
        "price_currency": "USD",
        "price_text": "$1.00",
        "discounted_value": 1.0,
        "discounted_formatted": "$1.00",
        "original_formatted": "$1.00",
        "source": "checkpoint",
        "image_url": "",
    }

    result = app_module.execute_scrape_workflow(
        [completed_url, pending_url],
        use_parallel=False,
        enrich_details=True,
        initial_items=[checkpoint_item],
        skip_target_urls=[completed_url],
    )

    assert scraped_urls == [pending_url]
    assert set(enriched_urls) == {checkpoint_item["url"], f"{pending_url}/product-b"}
    assert result["count"] == 2
    assert all(item["sku"] for item in result["items"])


def test_progress_writes_are_throttled_but_phase_boundaries_are_forced(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    state = {}

    assert app_module.automation_progress_write_due(state, now=1.0, phase=2, completed=0, total=100)
    assert not app_module.automation_progress_write_due(state, now=1.1, phase=2, completed=1, total=100)
    assert app_module.automation_progress_write_due(state, now=1.3, phase=2, completed=2, total=100)
    assert app_module.automation_progress_write_due(state, now=1.31, phase=2, completed=100, total=100)
    assert app_module.automation_progress_write_due(state, now=1.32, phase=3, completed=100, total=100)


def test_resume_worker_lock_blocks_duplicate_resume(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    monkeypatch.setattr(app_module, "APP_ROOT", tmp_path)

    app_module._write_resume_worker_lock(52, 12345)
    monkeypatch.setattr(app_module, "_resume_worker_pid_is_alive", lambda pid: int(pid) == 12345)

    assert app_module._resume_worker_is_locked(52) is True

    monkeypatch.setattr(app_module, "_resume_worker_pid_is_alive", lambda _pid: False)
    assert app_module._resume_worker_is_locked(52) is False
    assert not app_module._resume_worker_lock_path(52).exists()


def test_resume_reconciles_interrupted_run_when_worker_is_alive(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    job = app_module.db_manager.save_automation_job(
        {
            "name": "Live worker",
            "scraper_key": "xcell",
            "category_query": "live",
            "root_url": "https://xcellparts.com/",
            "interval_minutes": 1440,
            "enabled": True,
        },
        targets=[{"label": "One", "url": "https://xcellparts.com/one", "active": True}],
    )
    run = app_module.db_manager.create_automation_run(
        job["id"], trigger_type="manual", target_urls=["https://xcellparts.com/one"]
    )
    app_module.db_manager.recover_running_automation_runs()
    monkeypatch.setattr(app_module, "_resume_worker_is_locked", lambda _run_id: True)

    launched, message = app_module._launch_existing_automation_run(run["id"])
    restored = app_module.db_manager.get_automation_run(run["id"])
    assert launched is False
    assert message == "This automation run is already running."
    assert restored["status"] == "running"


def test_resume_clears_paused_worker_before_claiming_run(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    job = app_module.db_manager.save_automation_job(
        {
            "name": "Paused worker",
            "scraper_key": "xcell",
            "category_query": "paused",
            "root_url": "https://xcellparts.com/",
            "interval_minutes": 1440,
            "enabled": True,
        },
        targets=[{"label": "One", "url": "https://xcellparts.com/one", "active": True}],
    )
    run = app_module.db_manager.create_automation_run(
        job["id"], trigger_type="manual", target_urls=["https://xcellparts.com/one"]
    )
    app_module.db_manager.pause_automation_run(run["id"], reason="Paused for test.")
    stop_calls = []
    lock_states = iter([True, False])
    monkeypatch.setattr(app_module, "_resume_worker_is_locked", lambda _run_id: next(lock_states))
    monkeypatch.setattr(app_module, "_stop_resume_worker", lambda run_id, **_kwargs: stop_calls.append(run_id) or True)
    monkeypatch.setattr(app_module, "_spawn_automation_run_worker", lambda *_args, **_kwargs: (True, ""))

    launched, message = app_module._launch_existing_automation_run(run["id"])

    assert launched is True
    assert message == ""
    assert stop_calls == [run["id"]]


def test_exited_resume_worker_cleans_lock_atomically(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    monkeypatch.setattr(app_module, "APP_ROOT", tmp_path)

    class ExitedProcess:
        pid = 6789

        @staticmethod
        def poll():
            return 0

    app_module._write_resume_worker_lock(53, ExitedProcess.pid)
    app_module.AUTOMATION_RESUME_PROCESSES[53] = ExitedProcess()

    assert app_module._resume_worker_is_locked(53) is False
    assert 53 not in app_module.AUTOMATION_RESUME_PROCESSES
    assert not app_module._resume_worker_lock_path(53).exists()


def test_pause_stops_inflight_resume_worker_tree_promptly(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)

    class RunningProcess:
        pid = 8123

        def __init__(self):
            self.killed = False

        def poll(self):
            return 0 if self.killed else None

        def wait(self, timeout=None):
            if not self.killed:
                raise app_module.subprocess.TimeoutExpired("worker", timeout)
            return 0

        def kill(self):
            self.killed = True

        def terminate(self):
            self.killed = True

    worker = RunningProcess()

    def fake_run(command, **_kwargs):
        assert command[:2] == ["taskkill", "/PID"]
        worker.killed = True
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(app_module.subprocess, "run", fake_run)
    if hasattr(app_module.os, "killpg"):
        monkeypatch.setattr(app_module.os, "getpgid", lambda pid: pid)
        monkeypatch.setattr(app_module.os, "killpg", lambda pgid, sig: setattr(worker, "killed", True))
    if hasattr(app_module.os, "kill"):
        monkeypatch.setattr(app_module.os, "kill", lambda pid, sig: setattr(worker, "killed", True))
    app_module.AUTOMATION_RESUME_PROCESSES[61] = worker

    assert app_module._stop_resume_worker(61) is True
    assert worker.killed is True


def test_sparse_target_guard_blocks_bad_history_save(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRAPER_ANOMALY_GUARD", "1")
    monkeypatch.setenv("SCRAPER_ANOMALY_MIN_PREVIOUS", "10")
    monkeypatch.setenv("SCRAPER_ANOMALY_MAX_SPARSE_ITEMS", "2")
    monkeypatch.setenv("SCRAPER_CHATGPT_AUTO_REPORT", "0")
    app_module = _fresh_app(tmp_path, monkeypatch)
    monkeypatch.setattr(app_module, "APP_ROOT", tmp_path)

    target_url = "https://www.mobilesentrix.com/replacement-parts/apple/iphone-15"
    previous_history = {
        "id": "previous-history",
        "timestamp": "2026-07-16T00:00:00+05:00",
        "items": [
            {
                "title": f"Previous Product {idx}",
                "url": f"https://www.mobilesentrix.com/product-{idx}",
                "site": "mobilesentrix.com",
                "price_value": 1.0,
                "price_text": "$1.00",
                "discounted_value": 1.0,
                "discounted_formatted": "$1.00",
                "original_formatted": "$1.00",
                "extra": {"target_url": target_url, "target_label": "iPhone 15"},
            }
            for idx in range(12)
        ],
    }

    def fake_build_session(**_kwargs):
        return object(), False

    def fake_scrape_url(_session, _url, _rules, _crawl_pagination, _max_pages, _delay_ms, _logger):
        return [app_module.Item(
            url="https://www.mobilesentrix.com/only-one-product",
            site="mobilesentrix.com",
            title="Only One Product",
            price_value=1.0,
            price_currency="USD",
            price_text="$1.00",
            discounted_value=1.0,
            discounted_formatted="$1.00",
            original_formatted="$1.00",
            source="test",
            image_url="",
        )]

    monkeypatch.setattr(app_module, "build_session", fake_build_session)
    monkeypatch.setattr(app_module, "scrape_url", fake_scrape_url)

    result = app_module.execute_scrape_workflow(
        [target_url],
        use_browser=False,
        use_parallel=False,
        previous_history_override=previous_history,
    )

    assert result["history_saved"] is False
    assert result["guard_anomalies"]
    assert result["guard_anomalies"][0]["previous_count"] == 12
    assert result["guard_anomalies"][0]["current_count"] == 1
    assert result["guard_incident"]["chatgpt_report"]["sent"] is False
    assert "Scraper data-quality guard stopped" in result["error"]
    assert app_module.db_manager.get_history_list(limit=10) == []
    assert (tmp_path / "output" / "scraper_incidents").exists()


def test_running_automation_run_exposes_live_product_preview(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    job = app_module.db_manager.save_automation_job({
        "name": "GadgetFix Live",
        "scraper_key": "gadgetfix",
        "category_query": "iphone",
        "root_url": "https://gadgetfix.com/",
        "interval_minutes": 1440,
        "enabled": True,
        "auto_discover": False,
        "crawl_pagination": True,
        "max_pages": 10,
        "delay_ms": 50,
        "retries": 1,
        "verify_ssl": True,
        "use_parallel": True,
        "enrich_details": False,
        "drop_pct": 10,
        "rules": {},
    }, targets=[{
        "label": "iPhone",
        "url": "https://gadgetfix.com/category/iphone-1559.html",
        "active": True,
    }])
    run = app_module.db_manager.create_automation_run(
        job["id"],
        trigger_type="manual",
        target_urls=["https://gadgetfix.com/category/iphone-1559.html"],
    )
    app_module.db_manager.update_automation_run_progress(
        run["id"],
        items_count=1,
        summary={
            "target_count": 1,
            "completed_targets": 1,
            "current_items": 1,
            "preview_items": [{
                "title": "GadgetFix Screen",
                "url": "https://gadgetfix.com/gadgetfix-screen-100.html",
                "site": "gadgetfix.com",
                "original_formatted": "$9.99",
                "discounted_formatted": "$9.99",
                "image_url": "",
                "extra": {},
            }],
        },
    )

    with app_module.app.test_client() as client:
        response = client.get(f"/api/automation/runs/{run['id']}")

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["current_history"]["is_live_preview"] is True
    assert payload["current_history"]["items_count"] == 1
    assert payload["current_history"]["items"][0]["title"] == "GadgetFix Screen"


def test_automation_polling_is_compact_and_run_action_resumes_checkpoint(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    job = app_module.db_manager.save_automation_job({
        "name": "XCell Resume Test",
        "scraper_key": "xcell",
        "category_query": "resume",
        "root_url": "https://xcellparts.com/",
        "interval_minutes": 1440,
        "enabled": True,
        "max_pages": 10,
        "delay_ms": 50,
    }, targets=[
        {"label": "One", "url": "https://xcellparts.com/one", "active": True},
        {"label": "Two", "url": "https://xcellparts.com/two", "active": True},
    ])
    run = app_module.db_manager.create_automation_run(
        job["id"],
        trigger_type="manual",
        target_urls=["https://xcellparts.com/one", "https://xcellparts.com/two"],
    )
    app_module.db_manager.update_automation_run_progress(
        run["id"],
        items_count=1,
        summary={
            "target_count": 2,
            "total_targets": 2,
            "completed_targets": 1,
            "current_items": 1,
            "preview_items": [{"title": "Checkpoint item"}],
        },
    )
    app_module.db_manager.pause_automation_run(run["id"], reason="Paused for test.")
    monkeypatch.setattr(
        app_module,
        "_launch_existing_automation_run",
        lambda run_id: (run_id == run["id"], ""),
    )

    with app_module.app.test_client() as client:
        jobs_payload = client.get("/api/automation/jobs").get_json()
        runs_payload = client.get("/api/automation/runs?scraper_key=xcell").get_json()
        resume_response = client.post(f"/api/automation/jobs/{job['id']}/run", json={})
        app_module.db_manager.complete_automation_run(
            run["id"],
            status="failed",
            current_history_id="xcell:saved-partial-history",
            target_urls=["https://xcellparts.com/one", "https://xcellparts.com/two"],
            items_count=1,
            summary={
                "target_count": 2,
                "total_targets": 2,
                "completed_targets": 1,
                "current_items": 1,
                "preview_items": [{"title": "Checkpoint item"}],
            },
            error_text="Browser worker stopped.",
        )
        failed_resume_response = client.post(f"/api/automation/jobs/{job['id']}/run", json={})

    compact_job = jobs_payload["jobs"][0]
    compact_run = runs_payload["runs"][0]
    resume_payload = resume_response.get_json()

    assert compact_job["targets"] == []
    assert "target_urls" not in compact_run
    assert "preview_items" not in compact_run["summary"]
    assert compact_run["summary"]["preview_item_count"] == 1
    assert resume_response.status_code == 200
    assert resume_payload["resumed"] is True
    assert resume_payload["run_id"] == run["id"]
    assert failed_resume_response.status_code == 200
    assert failed_resume_response.get_json()["resumed"] is True


def test_run_now_rejects_job_with_active_run(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    job = app_module.db_manager.save_automation_job({
        "name": "XCell Active Test",
        "scraper_key": "xcell",
        "category_query": "active",
        "root_url": "https://xcellparts.com/",
        "interval_minutes": 1440,
        "enabled": True,
        "max_pages": 10,
        "delay_ms": 50,
    }, targets=[
        {"label": "One", "url": "https://xcellparts.com/one", "active": True},
    ])
    run = app_module.db_manager.create_automation_run(
        job["id"],
        trigger_type="manual",
        target_urls=["https://xcellparts.com/one"],
    )

    with app_module.app.test_client() as client:
        response = client.post(f"/api/automation/jobs/{job['id']}/run", json={})

    payload = response.get_json()
    assert response.status_code == 409
    assert payload["run_id"] == run["id"]
    assert payload["status"] == "running"
    assert "already running" in payload["error"]


def test_local_browser_rendering_is_hidden_by_default(monkeypatch):
    from scrapers import browser_fetcher

    monkeypatch.delenv("SCRAPER_LOCAL_BROWSER_HEADLESS", raising=False)
    monkeypatch.delenv("LOCAL_BROWSER_HEADLESS", raising=False)

    assert browser_fetcher._local_browser_headless() is True


def test_browser_fetch_uses_rendered_html_after_ready_timeout(monkeypatch):
    import types

    from scrapers import browser_fetcher

    class FakeDriver:
        page_html = "<html><body><div class='product-card'>Rendered product</div></body></html>"
        current_url = "https://txpartscanada.ca/shop/iphone-16-pro-max"

        def get(self, _url, timeout=60):
            raise RuntimeError("Document did not become ready within 60 seconds")

        def sleep(self, _seconds):
            return None

        def run_js(self, _script):
            return False

    def fake_browser(**_kwargs):
        def decorate(fn):
            def wrapper(data):
                return fn(FakeDriver(), data)
            return wrapper
        return decorate

    monkeypatch.setitem(
        sys.modules,
        "scrapers.botasaurus_wrapper",
        types.SimpleNamespace(Driver=FakeDriver, browser=fake_browser),
    )
    monkeypatch.setenv("SCRAPER_LOCAL_BROWSER_CHALLENGE_WAIT_SECONDS", "0")

    result = browser_fetcher.fetch_html(
        "https://txpartscanada.ca/shop/iphone-16-pro-max",
        timeout=1,
        wait_seconds=0,
    )

    assert result.final_url == "https://txpartscanada.ca/shop/iphone-16-pro-max"
    assert "Rendered product" in result.html
