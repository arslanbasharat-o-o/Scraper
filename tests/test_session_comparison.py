import importlib
import sys
import json
import time


def _fresh_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASES_DIR", str(tmp_path / "site_dbs"))
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    for module_name in ("app", "database"):
        sys.modules.pop(module_name, None)
    app_module = importlib.import_module("app")
    app_module.app.config["TESTING"] = True
    app_module.ensure_automation_scheduler_started = lambda: None
    return app_module


def _item(url, title, **values):
    return {
        "url": url,
        "title": title,
        "site": "xcellparts.com",
        "sku": values.get("sku", ""),
        "stock_status": values.get("stock_status", ""),
        "price_value": values.get("price_value"),
        "original_formatted": values.get("original_formatted", ""),
        "description": values.get("description", ""),
        "source": values.get("source", "xcell"),
        "extra": values.get("extra", {}),
    }


def test_comparison_excludes_categories_and_consolidates_duplicate_products(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    product_url = "https://xcellparts.com/product/example-screen/"
    previous = {
        "id": "previous",
        "timestamp": "2026-07-01T00:00:00+00:00",
        "items": [
            _item(
                "https://xcellparts.com/product-category/apple/iphone/",
                "IPHONE 42 Products",
            ),
            _item(product_url, 'Screen for iPhone 15 Pro 6.1"', sku="SCREEN-15"),
        ],
    }
    current = [
        _item(product_url, "Screen for iPhone 15 Pro 6.1\u2033", stock_status="In Stock"),
        _item(product_url, "Screen for iPhone 15 Pro 6.1\u2033", sku="SCREEN-15", stock_status="In Stock"),
    ]

    comparison = app_module.build_session_comparison(previous, current)

    assert comparison["summary"]["previous_rows"] == 2
    assert comparison["summary"]["previous_items"] == 1
    assert comparison["summary"]["excluded_previous_non_products"] == 1
    assert comparison["summary"]["current_rows"] == 2
    assert comparison["summary"]["current_items"] == 1
    assert comparison["summary"]["duplicate_current_rows"] == 1
    assert comparison["summary"]["changed"] == 0
    assert comparison["removed"] == []


def test_comparison_ignores_missing_metadata_but_keeps_real_changes(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    url = "https://xcellparts.com/product/charging-board/"
    previous = {
        "id": "previous",
        "timestamp": "2026-07-01T00:00:00+00:00",
        "items": [
            _item(
                url,
                "Charging Board for PS5",
                sku="PS5-BOARD",
                price_value=10.0,
            ),
        ],
    }
    current = [
        _item(
            url,
            "Charging Board for PS5 Slim",
            sku="",
            stock_status="In Stock",
            price_value=12.0,
        ),
    ]

    comparison = app_module.build_session_comparison(previous, current)

    assert comparison["summary"]["changed"] == 1
    assert comparison["summary"]["title_changes"] == 1
    assert comparison["summary"]["price_changes"] == 1
    assert comparison["summary"]["sku_changes"] == 0
    assert comparison["summary"]["stock_changes"] == 0
    assert set(comparison["changed"][0]["changes"]) == {"title", "price"}


def test_comparison_normalizes_url_and_presentation_only_title_differences(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    previous = {
        "id": "previous",
        "timestamp": "2026-07-01T00:00:00+00:00",
        "items": [
            _item(
                "HTTPS://XCELLPARTS.COM/product/test-cable/?utm_source=old",
                "Cable \u201c8.0\u201d \u2013 Black",
                sku="Cable-01",
                stock_status="2 in stock",
            ),
        ],
    }
    current = [
        _item(
            "https://xcellparts.com/product/test-cable",
            'cable "8.0" - black',
            sku="cable-01",
            stock_status="In Stock",
        ),
    ]

    comparison = app_module.build_session_comparison(previous, current)

    assert comparison["summary"]["changed"] == 0
    assert comparison["summary"]["added"] == 0
    assert comparison["summary"]["removed"] == 0


def test_comparison_matches_only_unambiguous_titles_for_changed_urls(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    previous = {
        "id": "previous",
        "timestamp": "2026-07-01T00:00:00+00:00",
        "items": [
            _item("https://xcellparts.com/product/old-slug/", "Unique Adapter"),
        ],
    }
    current = [
        _item("https://xcellparts.com/product/new-slug/", "unique adapter"),
    ]

    comparison = app_module.build_session_comparison(previous, current)

    assert comparison["summary"]["changed"] == 1
    assert comparison["summary"]["url_changes"] == 1
    assert set(comparison["changed"][0]["changes"]) == {"url"}


def test_comparison_matches_stable_sku_when_url_and_title_change(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    previous = {
        "id": "previous",
        "timestamp": "2026-07-01T00:00:00+00:00",
        "items": [
            _item("https://xcellparts.com/product/old-s26-plus-screen/", "S26 Plus Screen", sku="LCD-S26P"),
        ],
    }
    current = [
        _item("https://xcellparts.com/product/galaxy-s26-plus-lcd/", "Galaxy S26 Plus LCD Assembly", sku="lcd s26p"),
    ]

    comparison = app_module.build_session_comparison(previous, current)

    assert comparison["summary"]["added"] == 0
    assert comparison["summary"]["removed"] == 0
    assert comparison["summary"]["changed"] == 1
    assert comparison["changed"][0]["match_reason"] == "sku"
    assert {"url", "title"} <= set(comparison["changed"][0]["changes"])


def test_comparison_records_category_move_without_remove_or_add(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    old_target = "https://xcellparts.com/product-category/samsung/s26-plus/"
    new_target = "https://xcellparts.com/product-category/samsung/galaxy-s26-plus/"
    previous = {
        "id": "previous",
        "timestamp": "2026-07-01T00:00:00+00:00",
        "items": [
            _item(
                "https://xcellparts.com/product/s26-plus-service-pack/",
                "S26 Plus Service Pack",
                sku="SP-S26P",
                extra={"target_url": old_target},
            ),
        ],
    }
    current = [
        _item(
            "https://xcellparts.com/product/s26-plus-service-pack/",
            "S26 Plus Service Pack",
            sku="SP-S26P",
            extra={"target_url": new_target},
        ),
    ]

    comparison = app_module.build_session_comparison(previous, current, current_target_urls=[new_target])

    assert comparison["summary"]["added"] == 0
    assert comparison["summary"]["removed"] == 0
    assert comparison["summary"]["category_changes"] == 1
    assert comparison["changed"][0]["status"] == "Category Changed"


def test_comparison_does_not_confirm_removed_from_single_missing_scrape(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    target = "https://xcellparts.com/product-category/samsung/s26-plus/"
    previous = {
        "id": "previous",
        "timestamp": "2026-07-01T00:00:00+00:00",
        "items": [
            _item(
                "https://xcellparts.com/product/s26-plus-service-pack/",
                "S26 Plus Service Pack",
                sku="SP-S26P",
                extra={"target_url": target},
            ),
        ],
    }

    comparison = app_module.build_session_comparison(previous, [], current_target_urls=[target])

    assert comparison["summary"]["removed"] == 0
    assert comparison["summary"]["removed_confirmed"] == 0
    assert comparison["summary"]["verification_required"] == 1
    assert comparison["summary"]["temporarily_missing"] == 1
    assert comparison["verification_required"][0]["status"] == "Temporarily Missing"


def test_comparison_marks_missing_from_failed_target_as_scrape_failure(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    target = "https://xcellparts.com/product-category/samsung/s26-plus/"
    previous = {
        "id": "previous",
        "timestamp": "2026-07-01T00:00:00+00:00",
        "items": [
            _item(
                "https://xcellparts.com/product/s26-plus-service-pack/",
                "S26 Plus Service Pack",
                sku="SP-S26P",
                extra={"target_url": target},
            ),
        ],
    }

    comparison = app_module.build_session_comparison(
        previous,
        [],
        current_target_urls=[target],
        target_errors=[{"url": target, "error": "403 Forbidden"}],
    )

    assert comparison["summary"]["removed"] == 0
    assert comparison["summary"]["scrape_failures"] == 1
    assert comparison["verification_required"][0]["status"] == "Scrape Failure"


def test_comparison_does_not_remove_products_from_unscanned_targets(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    omitted_target = "https://xcellparts.com/product-category/accessories/wireless/"
    current_target = "https://xcellparts.com/product-category/accessories/cables/"
    previous = {
        "id": "previous",
        "timestamp": "2026-07-01T00:00:00+00:00",
        "items": [
            _item(
                "https://xcellparts.com/product/wireless-charger/",
                "Wireless Charger",
                sku="WIRELESS-1",
                extra={"target_url": omitted_target},
            ),
        ],
    }

    comparison = app_module.build_session_comparison(
        previous,
        [],
        current_target_urls=[current_target],
    )

    assert comparison["summary"]["removed"] == 0
    assert comparison["summary"]["out_of_scope_previous_products"] == 1
    assert comparison["removed"] == []


def test_unknown_zero_placeholder_price_is_not_presented_as_real_price(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)

    snapshot = app_module.normalize_item_snapshot(
        _item(
            "https://xcellparts.com/product/unknown-price/",
            "Unknown Price Product",
            price_value=None,
            original_formatted="$0.00",
        )
    )

    assert snapshot["comparison_price"] is None
    assert snapshot["price_formatted"] == ""
    assert snapshot["adjusted_price_formatted"] == ""


def test_scrape_completeness_validation_rejects_large_total_drop(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    target = "https://xcellparts.com/product-category/samsung/s26-plus/"
    previous = {
        "id": "previous",
        "timestamp": "2026-07-01T00:00:00+00:00",
        "items": [
            _item(
                f"https://xcellparts.com/product/s26-plus-screen-{idx}/",
                f"S26 Plus Screen {idx}",
                sku=f"S26P-{idx}",
                extra={"target_url": target},
            )
            for idx in range(200)
        ],
    }
    current = [
        _item(
            f"https://xcellparts.com/product/s26-plus-screen-{idx}/",
            f"S26 Plus Screen {idx}",
            sku=f"S26P-{idx}",
            extra={"target_url": target},
        )
        for idx in range(80)
    ]

    validation = app_module.validate_scrape_completeness([target], current, previous, [])

    assert validation["approved"] is False
    assert validation["status"] == "Rejected by Validation"
    assert validation["metrics"]["total_drop_items"] == 120


def test_scrape_completeness_validation_rejects_failed_target_with_baseline(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    target = "https://xcellparts.com/product-category/samsung/s26-plus/"
    previous = {
        "id": "previous",
        "timestamp": "2026-07-01T00:00:00+00:00",
        "items": [
            _item(
                f"https://xcellparts.com/product/s26-plus-screen-{idx}/",
                f"S26 Plus Screen {idx}",
                sku=f"S26P-{idx}",
                extra={"target_url": target},
            )
            for idx in range(12)
        ],
    }

    validation = app_module.validate_scrape_completeness(
        [target],
        previous["items"],
        previous,
        [{"url": target, "error": "No products parsed on page 3"}],
    )

    assert validation["approved"] is False
    assert "scrape errors" in validation["reasons"][-1]


def test_history_pruning_keeps_newest_two_valid_runs_for_same_url_set(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    target = "https://xcellparts.com/product-category/samsung/s26-plus/"
    items = [
        _item(
            "https://xcellparts.com/product/s26-plus-screen/",
            "S26 Plus Screen",
            sku="S26P-1",
            extra={"target_url": target},
        )
    ]

    for history_id in ("1001", "1002", "1003", "1004"):
        assert app_module.db_manager.save_fetch_history(history_id, [target], items, {})
        time.sleep(0.01)

    xcell_manager = app_module.db_manager._get_manager("xcell")
    conn = xcell_manager.get_connection()
    rules = {"_baseline_rejected": True}
    conn.execute("UPDATE fetch_history SET rules = ? WHERE id = ?", (json.dumps(rules), "1003"))
    conn.commit()

    deleted = app_module.db_manager.prune_histories_for_urls([target], keep=2)

    assert set(deleted) == {"xcell:1003", "xcell:1001"}
    assert app_module.db_manager.get_history_detail("xcell:1004") is not None
    assert app_module.db_manager.get_history_detail("xcell:1002") is not None
    assert app_module.db_manager.get_history_detail("xcell:1003") is None
    assert app_module.db_manager.get_history_detail("xcell:1001") is None


def test_history_baseline_skip_and_prune_work_for_every_supplier(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    base_history_id = 2000000000000

    for index, (scraper_key, config) in enumerate(app_module.SCRAPER_CONFIG.items(), start=1):
        domain = config["domains"][0]
        target = f"https://{domain}/product-category/preprod-audit-{scraper_key}/"
        product = f"https://{domain}/product/preprod-audit-product-{scraper_key}/"
        item = _item(
            product,
            f"Preprod Audit Product {scraper_key}",
            sku=f"AUDIT-{scraper_key}",
            extra={"target_url": target},
        )
        old_id = str(base_history_id + index * 10 + 1)
        rejected_id = str(base_history_id + index * 10 + 2)
        newest_id = str(base_history_id + index * 10 + 3)

        assert app_module.db_manager.save_fetch_history(old_id, [target], [item], {})
        assert app_module.db_manager.save_fetch_history(rejected_id, [target], [item], {"_baseline_rejected": True})
        assert app_module.db_manager.save_fetch_history(newest_id, [target], [item], {})

        latest = app_module.db_manager.get_latest_history_for_urls([target])
        assert latest["id"] == f"{scraper_key}:{newest_id}"

        deleted = app_module.db_manager.prune_histories_for_urls([target], keep=1)
        assert set(deleted) == {f"{scraper_key}:{rejected_id}", f"{scraper_key}:{old_id}"}
        assert app_module.db_manager.get_history_detail(f"{scraper_key}:{newest_id}") is not None
        assert app_module.db_manager.get_history_detail(f"{scraper_key}:{rejected_id}") is None
        assert app_module.db_manager.get_history_detail(f"{scraper_key}:{old_id}") is None
