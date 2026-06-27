import base64
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import market_agent as m


def test_format_chart_wraps_base64_in_chart_tag():
    figure_json = '{"data": [], "layout": {"title": {"text": "Hi"}}}'
    out = m._format_chart(figure_json)
    assert out.startswith("<CHART>\n")
    assert out.endswith("\n</CHART>\n\n")
    body = out[len("<CHART>\n"):-len("\n</CHART>\n\n")]
    decoded = base64.b64decode(body.encode("ascii")).decode("utf-8")
    assert decoded == figure_json


def test_format_chart_body_has_no_raw_braces():
    # base64 wrapping keeps the payload opaque to the tag regex
    out = m._format_chart('{"a": "</RESPONSE>"}')
    body = out.split("\n")[1]
    assert "{" not in body and "}" not in body and "<" not in body
