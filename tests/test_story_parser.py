from smart_locator.story_parser import detect_intent, parse_story


def test_detect_intent_maps_login_story_to_semantic_elements():
    result = detect_intent("As a user, I want to log in successfully using valid credentials")

    assert result == {
        "username_field": "fill",
        "password_field": "fill",
        "submit_button": "click",
        "success_message": "assert_visible",
    }


def test_parse_story_uses_fallback_when_no_intent_matches():
    result = parse_story("Do something custom", llm_fallback=lambda story: {"custom_button": "click"})

    assert result == {"custom_button": "click"}
