from app.core.auth import decode_token, hash_password, make_token, verify_password


def test_password_hash_roundtrip():
    h = hash_password("correct horse battery")
    assert verify_password("correct horse battery", h)
    assert not verify_password("wrong", h)
    assert h != hash_password("correct horse battery")  # unique salt


def test_jwt_roundtrip_and_tamper():
    t = make_token("a@b.co", "analyst")
    assert decode_token(t)["role"] == "analyst"
    assert decode_token(t[:-2] + "xx") is None
