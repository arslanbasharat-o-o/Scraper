from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]


def test_extractor_template_groups_and_dialog_accessibility():
    soup = BeautifulSoup((ROOT / "templates" / "index.html").read_text(encoding="utf-8"), "html.parser")

    assert soup.find(id="urls").get("aria-describedby") == "urlsHelp"
    assert soup.find(id="advancedControls").has_attr("hidden")

    pricing_group = soup.find(attrs={"aria-labelledby": "pricingGroupLabel"})
    keywords_group = soup.find(attrs={"aria-labelledby": "keywordsGroupLabel"})
    display_group = soup.find(attrs={"aria-labelledby": "displayGroupLabel"})

    assert pricing_group is not None
    assert keywords_group is not None
    assert display_group is not None

    search_label = soup.find("label", attrs={"for": "search"})
    assert search_label is not None

    confirm_dialog = soup.find(id="confirmModalDialog")
    assert confirm_dialog is not None
    assert confirm_dialog.get("tabindex") == "-1"


def test_extractor_script_syncs_filters_results_and_dialog_focus():
    script = (ROOT / "static" / "js" / "main.js").read_text(encoding="utf-8")

    assert "function syncFiltersDisclosure()" in script
    assert "advancedControls.hidden = !filtersOpen" in script
    assert "advancedControls.setAttribute('aria-hidden', String(!filtersOpen))" in script
    assert "const resultsTable = resultsTableWrap?.querySelector('table');" in script
    assert "if (resultsTable) resultsTable.hidden = !has;" in script
    assert "document.addEventListener('focusin'" in script
    assert "focusConfirmDialogTarget" in script
    assert "function summarizeTargetErrors(targetErrors)" in script
    assert "Target fetch error:" in script


def test_failed_automation_runs_are_always_resumable():
    script = (ROOT / "static" / "js" / "automation.js").read_text(encoding="utf-8")

    assert "['paused', 'interrupted', 'failed'].includes(status)" in script


def test_scheduler_does_not_replace_unfinished_runs():
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "if latest_status in {'paused', 'interrupted', 'failed'}:" in source
    assert "Skipping scheduled job" in source


def test_real_time_polling_is_visibility_aware_and_payloads_are_compact():
    automation_script = (ROOT / "static" / "js" / "automation.js").read_text(encoding="utf-8")
    menu_map_script = (ROOT / "static" / "js" / "menu-map.js").read_text(encoding="utf-8")
    menu_map_template = (ROOT / "templates" / "menu_map.html").read_text(encoding="utf-8")

    assert "include_models: '0'" in automation_script
    assert "function schedulePolling(" in menu_map_script
    assert "document.addEventListener('visibilitychange'" in menu_map_script
    assert "window.addEventListener('pagehide', stopPolling)" in menu_map_script
    assert "MENU_POLL_MAX_MS = 30000" in menu_map_script
    assert "window.setInterval(() => pollJob()" not in menu_map_script
    assert menu_map_template.count("sessionStorage.setItem('cy_theme'") == 0


def test_menu_map_automation_names_are_category_scoped_not_date_stamped():
    menu_map_script = (ROOT / "static" / "js" / "menu-map.js").read_text(encoding="utf-8")
    automation_script = (ROOT / "static" / "js" / "automation.js").read_text(encoding="utf-8")
    history_script = (ROOT / "static" / "js" / "history.js").read_text(encoding="utf-8")

    assert "function targetScopeForJob(site, targets)" in menu_map_script
    assert "name: `${cleanJobScopeLabel(site.name)} - ${scope}`" in menu_map_script
    assert "category_query: scope" in menu_map_script
    assert "Menu Map - ${site.name}" not in menu_map_script
    assert "function automationDisplayName(record)" in automation_script
    assert "function automationScopeLabel(record)" in automation_script
    assert "${escapeHtml(displayName)}" in automation_script
    assert "JSON.stringify(isDeleteAll ? { delete_all: true } : { days: this.currentDays })" in history_script
    assert "elements.historyContainer.innerHTML = Array.from({ length: 5 })" in history_script


def test_automation_live_runs_keep_visible_progress_through_finalizing():
    automation_script = (ROOT / "static" / "js" / "automation.js").read_text(encoding="utf-8")
    automation_styles = (ROOT / "static" / "css" / "automation.css").read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "function getRunProgressPercent(run)" in automation_script
    assert "function getRunPhaseName(run)" in automation_script
    assert "function getRunActivityMessage(run)" in automation_script
    assert "automation-run-progress__fill" in automation_script
    assert "Phase 4: Saving Snapshot" in app_source
    assert "'status_message': 'Writing scraped products, comparison metadata, and run history to the database.'" in app_source
    assert ".automation-run-progress__track" in automation_styles
    assert "transition: width .55s cubic-bezier" in automation_styles


def test_automation_distinguishes_schedules_from_run_snapshots():
    template = (ROOT / "templates" / "automation.html").read_text(encoding="utf-8")
    script = (ROOT / "static" / "js" / "automation.js").read_text(encoding="utf-8")

    assert "Saved Schedules" in template
    assert "Run History" in template
    assert "Schedules control future scrapes. Run history preserves each result." in template
    assert "function scheduleStatusChip(job)" in script
    assert "${scheduleStatusChip(job)}" in script
    assert "${statusChip(job.last_status)}" not in script
    assert '<div class="automation-card-kind">Saved schedule</div>' in script
    assert '<div class="automation-card-kind">Run snapshot</div>' in script


def test_product_explorer_uses_stable_toolbar_filters_and_pagination():
    template = (ROOT / "templates" / "automation.html").read_text(encoding="utf-8")
    script = (ROOT / "static" / "js" / "automation.js").read_text(encoding="utf-8")
    styles = (ROOT / "static" / "css" / "automation.css").read_text(encoding="utf-8")

    assert "Product Explorer" in template
    assert "Model scope" in template
    assert "data-product-search" in script
    assert "data-product-mode" in script
    assert "data-product-source" in script
    assert "data-product-min-price" in script
    assert "data-product-max-price" in script
    assert "data-product-sort-select" in script
    assert "data-product-page-size" in script
    assert "data-product-page=\"previous\"" in script
    assert "data-product-page=\"next\"" in script
    assert "function resetAllProductFilters()" in script
    assert "state.selectedChangeView = 'all';" in script
    assert "elements.automationModelFilter.value = '';" in script
    assert "filteredItems.slice(startIndex, endIndex)" in script
    assert "woocommerce-placeholder" in script
    assert "data-product-image" in script
    assert "Supplier provided no product image" in script
    assert "addEventListener('error'" in script
    assert "data-product-filter" not in script
    assert "automation-product-filter-row" not in script
    assert ".automation-product-toolbar__controls" in styles
    assert ".automation-product-pagination" in styles
    assert ".automation-product-no-image[hidden]" in styles


def test_automation_product_filters_keep_unknown_prices_blank():
    script = (ROOT / "static" / "js" / "automation.js").read_text(encoding="utf-8")

    assert "function productPriceNumber(item)" in script
    assert "if (parsed === 0) continue;" in script
    assert "if (parsed !== null && parsed > 0) return parsed;" in script
    assert "escapeHtml(original || '-')" in script
