import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import bootstrap_sentinel as b


def test_container_spec_targets_sentinel_convo():
    name, partition_path = b.container_spec()
    assert name == "sentinelConvo"
    assert partition_path == "/thread_id"
