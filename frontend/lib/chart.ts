// Decode a base64-encoded Plotly figure JSON (the <CHART> payload) back to its
// JSON string. Mirrors the Python frontend's chart_utils.decode_chart. Returns
// null if the payload does not base64-decode to parseable JSON, so a bad chart
// never throws into the render.
//
// Runtime-agnostic: works in the browser (atob/TextDecoder) and in Node/tests
// (Buffer fallback). This module is imported by streamParser.ts (used
// client-side), where Node's Buffer is not defined.
function fromBase64(b64: string): string {
  if (typeof atob === 'function') {
    const bin = atob(b64);
    const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
    return new TextDecoder('utf-8').decode(bytes);
  }
  // Node fallback (tests / server)
  return Buffer.from(b64, 'base64').toString('utf-8');
}

export function decodeChartBase64(b64: string): string | null {
  try {
    const json = fromBase64(b64.trim());
    JSON.parse(json); // validate; throws if not JSON
    return json;
  } catch {
    return null;
  }
}
