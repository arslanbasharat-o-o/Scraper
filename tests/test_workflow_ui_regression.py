from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]


def test_shared_footer_holds_version_and_maintainer_details():
    template_names = ("history.html", "automation.html", "menu_map.html", "logs.html")
    footer = (ROOT / "templates" / "_footer.html").read_text(encoding="utf-8")

    assert "{{ app_version }}" in footer
    assert "Arslanbasharat414@gmail.com" in footer
    for name in template_names:
        source = (ROOT / "templates" / name).read_text(encoding="utf-8")
        assert '{% include "_footer.html" %}' in source
        assert "version-badge" not in source
        assert "v8.2.0" not in source


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
    assert "data-lazy-children" in menu_map_script
    assert "lazyTreeChildren" in menu_map_script
    assert menu_map_template.count("sessionStorage.setItem('cy_theme'") == 0


def test_menu_map_completed_runs_do_not_keep_the_page_busy_or_expand_all_logs():
    menu_map_script = (ROOT / "static" / "js" / "menu-map.js").read_text(encoding="utf-8")
    menu_map_styles = (ROOT / "static" / "css" / "menu-map.css").read_text(encoding="utf-8")
    menu_map_template = (ROOT / "templates" / "menu_map.html").read_text(encoding="utf-8")

    assert "job-event--completed" in menu_map_script
    assert "MAX_JOB_OUTPUT_CHARS = 1600" in menu_map_script
    assert "activeJobId = '';" in menu_map_script
    assert "jobPanelMode === 'job'" in menu_map_script
    assert ".job-event--completed summary" in menu_map_styles
    assert "Finished runs are cleared automatically" not in menu_map_template


def test_menu_map_uses_styled_confirmation_modal_for_large_actions():
    menu_map_script = (ROOT / "static" / "js" / "menu-map.js").read_text(encoding="utf-8")
    menu_map_template = (ROOT / "templates" / "menu_map.html").read_text(encoding="utf-8")

    assert "function showMenuMapConfirm({" in menu_map_script
    assert "menuMapConfirmModal" in menu_map_template
    assert "Start a large category scrape?" in menu_map_script
    assert "window.confirm(`This will queue automation" not in menu_map_script


def test_menu_map_automation_names_are_category_scoped_not_date_stamped():
    menu_map_script = (ROOT / "static" / "js" / "menu-map.js").read_text(encoding="utf-8")
    menu_map_template = (ROOT / "templates" / "menu_map.html").read_text(encoding="utf-8")
    automation_script = (ROOT / "static" / "js" / "automation.js").read_text(encoding="utf-8")
    history_script = (ROOT / "static" / "js" / "history.js").read_text(encoding="utf-8")

    assert "function targetScopeForJob(site, targets)" in menu_map_script
    assert "name: `${cleanJobScopeLabel(site.name)} - ${scope}`" in menu_map_script
    assert "category_query: scope" in menu_map_script
    assert "Send Categories to Scraper" in menu_map_template
    assert "Scrape Visible Categories" in menu_map_template
    assert "automationPayloadForSite(site, targets)" in menu_map_script
    assert "fetchJson(`/api/automation/jobs/${encodeURIComponent(jobId)}/run`" in menu_map_script
    assert "Menu Map - ${site.name}" not in menu_map_script
    assert "function automationDisplayName(record)" in automation_script
    assert "function automationScopeLabel(record)" in automation_script
    assert "${escapeHtml(displayName)}" in automation_script
    assert "JSON.stringify(isDeleteAll ? { delete_all: true } : { days: this.currentDays })" in history_script
    assert "elements.historyContainer.innerHTML = Array.from({ length: 5 })" in history_script


def test_menu_map_state_controls_do_not_advertise_unavailable_actions():
    script = (ROOT / "static" / "js" / "menu-map.js").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "menu_map.html").read_text(encoding="utf-8")

    assert "visible: Boolean(elements.visibleMode?.checked)" in script
    assert 'id="visibleMode"' not in template
    assert "const validOutput = Boolean(site?.has_output && !site.parse_error && site.output_valid !== false);" in script
    assert "treeHasMissingUrls(site)" in script
    assert "No websites are available." in script
    assert "Menu-map output could not be read." in script
    assert "const link = isUsableUrl(childUrl)" in script
    assert "if (sitesLoadPromise) return sitesLoadPromise;" in script


def test_menu_map_metrics_are_not_rendered_as_disabled_buttons():
    template = (ROOT / "templates" / "menu_map.html").read_text(encoding="utf-8")

    assert 'data-summary-action="parents"' not in template
    assert 'data-summary-action="subs"' not in template
    assert 'data-summary-action="children"' not in template
    assert 'data-detail-action="parents"' not in template
    assert 'data-detail-action="subs"' not in template
    assert 'data-detail-action="children"' not in template


def test_menu_map_tree_remove_actions_stay_at_the_end_of_each_row():
    styles = (ROOT / "static" / "css" / "menu-map.css").read_text(encoding="utf-8")

    assert ".tree-parent__head,\n.tree-sub__head" in styles
    assert "justify-content: space-between;" in styles
    assert "flex-wrap: nowrap;" in styles
    assert "margin-left: auto;" in styles


def test_automation_inspector_tabs_have_consistent_button_spacing():
    styles = (ROOT / "static" / "css" / "automation.css").read_text(encoding="utf-8")

    assert ".inspector-tabs" in styles
    assert "gap: .5rem;" in styles
    assert "min-height: 40px;" in styles
    assert "padding: .6rem 1.05rem;" in styles


def test_automation_panels_size_to_content_instead_of_forcing_empty_height():
    styles = (ROOT / "static" / "css" / "automation.css").read_text(encoding="utf-8")

    assert "min-height: 680px;" not in styles
    assert "min-height: 600px;" not in styles
    assert "min-height: 300px;" not in styles
    assert "min-height: 160px;" in styles
    assert "min-height: 180px;" in styles


def test_automation_live_runs_keep_visible_progress_through_finalizing():
    automation_script = (ROOT / "static" / "js" / "automation.js").read_text(encoding="utf-8")
    automation_styles = (ROOT / "static" / "css" / "automation.css").read_text(encoding="utf-8")
    automation_template = (ROOT / "templates" / "automation.html").read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    resume_helper = (ROOT / "scripts" / "resume_automation_run.py").read_text(encoding="utf-8")

    assert "function getRunProgressPercent(run)" in automation_script
    assert "function getRunPhaseName(run)" in automation_script
    assert "function getRunActivityMessage(run)" in automation_script
    assert "function showConfirmDialog({" in automation_script
    assert "automationConfirmModal" in automation_template
    assert "Delete past run?" in automation_script
    assert "window.confirm('Are you sure you want to delete this past run?')" not in automation_script
    assert "const isSelectedRun = Number(run.id) === Number(state.selectedRunId);" in automation_script
    assert "function hasPhase1CheckpointItems(run)" in automation_script
    assert "function getPhase2Progress(run)" in automation_script
    assert "Math.max(rawTotal || harvested, completed)" in automation_script
    assert "phase2Complete ? 'Finalizing'" in automation_script
    assert "const isPhase2 = ['running', 'resuming'].includes(status) && currentPhase === 2;" in automation_script
    assert "targetsPerMin: isPhase2 ? 0 : measuredRate" in automation_script
    assert "itemsPerMin: isPhase2 ? measuredRate : 0" in automation_script
    assert "activeEta = timing.stale ? 'Waiting for progress' : timing.etaLabel;" in automation_script
    assert "activeSpeed = timing.rateLabel;" in automation_script
    assert "function getMeasuredRunRate(run" in automation_script
    assert "function observeRunProgress(run)" in automation_script
    assert "Products Found" in automation_script
    assert "products found" in automation_script
    assert "Restoring Product Checkpoint" in automation_script
    assert "Checkpoint restored:" in automation_script
    assert "resume_checkpoint_targets" in resume_helper
    assert "resume_checkpoint_items" in resume_helper
    assert "automation-run-progress__fill" in automation_script
    assert "automation-run-progress__label" in automation_script
    assert "activeRunStatus && !isSelectedRun" in automation_script
    assert "automation-run-progress__line" not in automation_script
    assert "Phase 4: Saving Snapshot" in app_source
    assert "checkpoint_only_phase1" in app_source
    assert "Collecting Product Checkpoint" in app_source
    assert "phase2_total = max(phase2_total, phase2_completed)" in app_source
    assert "env.setdefault('XCELL_MAX_WORKERS', '24')" in app_source
    assert "env.setdefault('SCRAPER_XCELL_DETAIL_WORKERS', '64')" in app_source
    assert "use_curl=True" in resume_helper
    assert 'use_browser=_truthy_value(job["use_browser"]) if "use_browser" in job else None' in resume_helper
    assert "'status_message': 'Writing scraped products, comparison metadata, and run history to the database.'" in app_source
    assert ".automation-run-progress__track" in automation_styles
    assert ".automation-run-progress__label" in automation_styles
    assert "background: transparent;" in automation_styles
    assert "box-shadow: none;" in automation_styles
    assert "transition: width .55s cubic-bezier" in automation_styles


def test_automation_distinguishes_schedules_from_run_snapshots():
    template = (ROOT / "templates" / "automation.html").read_text(encoding="utf-8")
    script = (ROOT / "static" / "js" / "automation.js").read_text(encoding="utf-8")

    assert "Saved Schedules" in template
    assert "Run History" in template
    assert "Schedules control future scrapes. Run history preserves each result." not in template
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




def test_automation_ui_cleanup_removes_stale_overlay_and_discover_button_refs():
    script = (ROOT / "static" / "js" / "automation.js").read_text(encoding="utf-8")
    styles = (ROOT / "static" / "css" / "automation.css").read_text(encoding="utf-8")

    assert "automationDiscoverBtn" not in script
    assert "overlay: $('overlay')" not in script
    assert ".overlay {" not in styles
    assert ".overlay-status" not in styles
    assert ".automation-products-panel" not in styles
    assert styles.count("page-shell--table-mode") == 1
