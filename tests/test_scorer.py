from smart_locator.scorer import build_locator_candidates


def test_accessible_hooks_rank_highest():
    element = {
        "tag": "input",
        "text": "",
        "attributes": {
            "data-testid": "login-username",
            "aria-label": "Username",
            "id": "user-field",
            "name": "username",
        },
        "css_path": "form > input",
    }
    candidates = build_locator_candidates(element)
    assert candidates[0].strategy == "data-testid"
    assert candidates[0].score >= 90
    assert candidates[1].strategy == "aria-label"
    assert candidates[1].score >= 90


def test_dynamic_id_is_penalized():
    element = {
        "tag": "button",
        "text": "Submit",
        "attributes": {"id": "btn-a3f92"},
        "css_path": "div > button",
    }
    candidates = build_locator_candidates(element)
    dynamic = next(candidate for candidate in candidates if candidate.strategy == "id")
    assert dynamic.score <= 20
    assert dynamic.warning == "dynamic — will break on redeploy"


def test_positional_xpath_is_avoid():
    element = {
        "tag": "input",
        "text": "",
        "attributes": {"name": "username"},
        "css_path": "div:nth-of-type(3) > input:nth-of-type(1)",
    }
    candidates = build_locator_candidates(element)
    positional = [candidate for candidate in candidates if candidate.strategy == "xpath"][-1]
    assert positional.score <= 25
    assert positional.reason == "position-based — breaks on DOM change"


def test_generated_class_is_penalized():
    element = {
        "tag": "div",
        "text": "",
        "attributes": {"class": "sc-abc123 panel"},
        "css_path": "main > div",
    }
    candidates = build_locator_candidates(element)
    css = next(candidate for candidate in candidates if candidate.strategy == "css" and ".sc-abc123" in candidate.value)
    assert css.score <= 20
