from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "history.html").read_text(encoding="utf-8")
SCRIPT = (ROOT / "static" / "js" / "history.js").read_text(encoding="utf-8")


class ElementParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def parsed_elements():
    parser = ElementParser()
    parser.feed(TEMPLATE)
    return parser.elements


def element_by_id(element_id):
    return next(attrs for _, attrs in parsed_elements() if attrs.get("id") == element_id)


def test_loading_overlay_uses_utility_class_and_live_status():
    overlay = element_by_id("overlay")

    assert "d-none" in overlay["class"].split()
    assert overlay["role"] == "status"
    assert overlay["aria-live"] == "polite"
    assert "Loading history data" in TEMPLATE
    assert "elements.overlay.classList.toggle('d-none', !on)" in SCRIPT
    assert "elements.overlay.style.display" not in SCRIPT


def test_history_dialogs_have_accessible_names_and_initial_hidden_state():
    history_overlay = element_by_id("historyModal")
    cleanup_overlay = element_by_id("cleanupModal")
    dialogs = [
        attrs
        for _, attrs in parsed_elements()
        if attrs.get("role") == "dialog"
    ]

    assert history_overlay["aria-hidden"] == "true"
    assert cleanup_overlay["aria-hidden"] == "true"
    assert "d-none" in history_overlay["class"].split()
    assert "d-none" in cleanup_overlay["class"].split()
    assert {dialog["aria-labelledby"] for dialog in dialogs} == {
        "historyModalTitle",
        "cleanupModalTitle",
        "confirmModalTitle",
    }
    assert all(dialog["aria-modal"] == "true" for dialog in dialogs)
    assert 'id="historyModalTitle"' in SCRIPT
    assert element_by_id("cleanupModalTitle")


def test_dialog_controller_covers_keyboard_focus_and_scroll_management():
    required_contracts = [
        "event.key === 'Escape'",
        "event.key !== 'Tab'",
        "lastElement.focus()",
        "firstElement.focus()",
        "returnFocus.focus()",
        "document.body.classList.toggle('modal-open', dialogStack.length > 0)",
        "initialFocus: elements.closeModal",
        "initialFocus: this.closeBtn",
        "onEscape: () => resolveConfirmDialog(false)",
    ]

    for contract in required_contracts:
        assert contract in SCRIPT


def test_dark_mode_accessible_name_is_preserved():
    assert element_by_id("darkMode")["aria-label"] == "Toggle dark mode"


def test_saved_theme_is_applied_before_theme_aware_critical_styles():
    head_theme_script = "const saved = sessionStorage.getItem('cy_theme')"

    assert TEMPLATE.index(head_theme_script) < TEMPLATE.index("<style>")
    assert "background: var(--history-startup-bg)" in TEMPLATE
    assert "color: var(--history-startup-text)" in TEMPLATE
    assert '[data-bs-theme="light"]' in TEMPLATE
    assert "opacity: 0" not in TEMPLATE
    assert "@keyframes fadeIn" not in TEMPLATE
