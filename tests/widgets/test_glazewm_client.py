import json
from unittest.mock import Mock

import pytest

from core.widgets.services.glazewm.client import GlazewmClient, QueryType


@pytest.mark.parametrize("queries", [[query.value] for query in QueryType] + [[], [query.value for query in QueryType]])
def test_subscription_events_refresh_only_configured_queries(qapp, queries):
    initial_messages = ["sub -e focus_changed", *queries]
    client = GlazewmClient("ws://localhost:6123", initial_messages)
    client._websocket = Mock()

    for _ in range(2):
        client._on_connected()
        assert [call.args[0] for call in client._websocket.sendTextMessage.call_args_list] == initial_messages
        client._websocket.reset_mock()

        for _ in range(10):
            client._handle_message(
                json.dumps({"messageType": "event_subscription", "data": {"eventType": "focus_changed"}})
            )

        assert [call.args[0] for call in client._websocket.sendTextMessage.call_args_list] == queries * 10
        client._websocket.reset_mock()
