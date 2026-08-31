from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]


def load_extractor_markup():
    return BeautifulSoup((ROOT / "templates" / "index.html").read_text(encoding="utf-8"), "html.parser")


def test_key_extractor_controls_have_associated_labels():
    soup = load_extractor_markup()
    control_ids = {
        "urls",
        "percent",
        "absOff",
        "addPercent",
        "priceMin",
        "priceMax",
        "dropPct",
        "kwInclude",
        "kwExclude",
        "sortBy",
    }

    labelled_ids = {label.get("for") for label in soup.find_all("label") if label.get("for")}
    assert control_ids <= labelled_ids


def test_filters_and_empty_results_have_accessible_initial_state():
    soup = load_extractor_markup()
    filters_toggle = soup.find(id="advancedToggle")

    assert filters_toggle.name == "button"
    assert filters_toggle.get("aria-expanded") == "false"
    assert filters_toggle.get("aria-controls") == "advancedControls"
    assert soup.find(id="advancedControls") is not None
    assert soup.find(id="resultsHeader").has_attr("hidden")
    assert soup.find(id="resultsTableWrap").has_attr("hidden")
    assert "d-none" not in soup.find(id="resultsEmpty").get("class", [])


def test_watchlist_action_and_dynamic_ui_state_contracts():
    script = (ROOT / "static" / "js" / "main.js").read_text(encoding="utf-8")

    assert '<button type="button" class="star"' in script
    assert 'aria-pressed="${r.watchlisted ? \'true\' : \'false\'}"' in script
    assert "advancedToggle.setAttribute('aria-expanded', String(filtersOpen))" in script
    assert "resultsHeader.hidden = !has" in script
    assert "resultsTableWrap.hidden = !has" in script
    assert "getConfirmDialogFocusableElements" in script
    assert "returnFocus.focus()" in script


def test_saved_theme_is_applied_before_critical_styles_without_startup_fade():
    markup = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(markup, "html.parser")
    head_children = [child for child in soup.head.children if getattr(child, "name", None)]
    theme_script_index = next(
        index
        for index, child in enumerate(head_children)
        if child.name == "script" and "cy_theme" in child.get_text()
    )
    first_style_index = next(
        index
        for index, child in enumerate(head_children)
        if child.name in {"style", "link"} and (child.name == "style" or child.get("rel") == ["stylesheet"])
    )

    assert theme_script_index < first_style_index
    assert "--startup-bg: #f2f4fb" in markup
    assert "background: var(--startup-bg)" in markup
    assert "color: var(--startup-text)" in markup
    assert "animation: fadeIn" not in markup
    assert "@keyframes fadeIn" not in markup
