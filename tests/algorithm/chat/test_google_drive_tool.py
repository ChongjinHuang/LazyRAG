from lazymind.chat.service.component.tool_registry import DEFAULT_TOOLS


def test_google_drive_tool_group_exposes_search_and_find():
    group = next(item for item in DEFAULT_TOOLS if item.name == 'google_drive')

    assert group.instance.__class__.__name__ == 'GoogleDriveFS'
    assert 'search' in group.instance.__public_apis__
    assert 'find' in group.instance.__public_apis__
