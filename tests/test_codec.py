import pytest
from pathlib import Path
from codec import encode_cxp, decode_cxp

def test_codec_roundtrip_traffic_light():
    cxt_path = Path("project/Traffic_Light.cxt")
    assert cxt_path.exists()
    original_bytes = cxt_path.read_bytes()
    encoded = encode_cxp(original_bytes)
    assert len(encoded) > 0
    decoded = decode_cxp(encoded)
    assert decoded == original_bytes, "Codec roundtrip byte mismatch on Traffic_Light"

def test_codec_templates():
    templates_dir = Path("templates")
    cxt_files = list(templates_dir.rglob("*.cxt"))
    assert len(cxt_files) >= 2
    for cxt in cxt_files:
        raw = cxt.read_bytes()
        enc = encode_cxp(raw)
        dec = decode_cxp(enc)
        assert dec == raw, f"Template codec roundtrip failed on {cxt.name}"
