import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import db


def test_sentinel_convo_container_exists():
    assert hasattr(db, "sentinel_convo_container")
    assert db.SENTINEL_CONVO_CONTAINER_NAME == "sentinelConvo"
    assert db.SENTINEL_CHECKPOINT_CONTAINER_NAME == "sentinelChatbot"
