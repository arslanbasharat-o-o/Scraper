from scrapers.menu_map.common import (
    CategoryRecord,
    SEMANTIC_MENU_JS,
    hierarchy_health,
    hierarchy_needs_healing,
    hierarchy_score,
)
from tests.botasaurus_test_utils import evaluate_script


def record(parent, parent_order, sub="", child="", url=""):
    return CategoryRecord(
        website="Test",
        website_url="https://example.com/",
        parent_name=parent,
        parent_url="",
        parent_display_order=parent_order,
        parent_open_method="click",
        sub_child_name=sub,
        sub_child_url="",
        sub_child_display_order=1 if sub else 0,
        child_name=child,
        child_url=url,
        child_display_order=1 if child else 0,
    )


def test_sparse_parent_only_menu_triggers_healing():
    records = [record(f"Parent {index}", index) for index in range(1, 6)]

    assert hierarchy_needs_healing(records) is True
    assert hierarchy_health(records)["children"] == 0


def test_group_only_menu_triggers_healing():
    records = [
        record("Apple", 1, "iPhone"),
        record("Apple", 1, "iPad"),
        record("Samsung", 2, "Galaxy S"),
    ]

    assert hierarchy_needs_healing(records) is True
    assert hierarchy_health(records)["sub_children"] == 3
    assert hierarchy_health(records)["children"] == 0


def test_large_drop_from_learned_health_triggers_healing():
    records = [record("Apple", 1, "iPhone", "iPhone 17", "https://example.com/iphone-17")]

    assert hierarchy_needs_healing(records, {"unique_urls": 100}) is True


def test_recovered_children_outscore_parent_only_result():
    sparse = [record("Apple", 1), record("Samsung", 2), record("Google", 3)]
    recovered = [
        record("Apple", 1, "iPhone", "iPhone 17", "https://example.com/iphone-17"),
        record("Apple", 1, "iPad", "iPad Pro", "https://example.com/ipad-pro"),
    ]

    assert hierarchy_score(recovered) > hierarchy_score(sparse)


def test_semantic_healer_rebuilds_changed_nested_menu():
    hierarchy = evaluate_script(
        SEMANTIC_MENU_JS,
        """
        <nav aria-label="menunavigation">
          <ul id="nav">
            <li class="changed-apple-menu">
              <a href="javascript:;">Apple</a>
              <ul class="new-mega-menu">
                <li>
                  <ul class="new-model-group">
                    <li><a href="javascript:;">iPhone</a></li>
                    <li><a href="/replacement-parts/apple/iphone-17">iPhone 17</a></li>
                    <li><a href="/replacement-parts/apple/iphone-16">iPhone 16</a></li>
                  </ul>
                </li>
                <li>
                  <ul class="new-model-group">
                    <li><a href="javascript:;">iPad</a></li>
                    <li><a href="/replacement-parts/apple/ipad-pro">iPad Pro</a></li>
                  </ul>
                </li>
              </ul>
            </li>
          </ul>
        </nav>
        """,
        "https://www.mobilesentrix.ca/",
        "#nav",
    )

    assert hierarchy[0]["name"] == "Apple"
    assert [group["name"] for group in hierarchy[0]["sub_children"]] == ["iPhone", "iPad"]
    assert hierarchy[0]["sub_children"][0]["children"][0]["url"].endswith("/iphone-17")
