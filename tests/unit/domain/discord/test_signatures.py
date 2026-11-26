from nacl.signing import SigningKey

from wgm.domain.discord.signatures import is_valid_signature

BODY = b'{"type":1}'
TIMESTAMP = "1764170000"


def _signed(key: SigningKey) -> dict[str, str]:
    return {
        "public_key": key.verify_key.encode().hex(),
        "signature": key.sign(TIMESTAMP.encode() + BODY).signature.hex(),
        "timestamp": TIMESTAMP,
    }


def test_accepts_a_matching_signature(signing_key: SigningKey) -> None:
    assert is_valid_signature(**_signed(signing_key), body=BODY)


def test_rejects_a_changed_body(signing_key: SigningKey) -> None:
    assert not is_valid_signature(**_signed(signing_key), body=b'{"type":2}')


def test_rejects_a_changed_timestamp(signing_key: SigningKey) -> None:
    args = _signed(signing_key) | {"timestamp": "1764170001"}
    assert not is_valid_signature(**args, body=BODY)


def test_rejects_another_key(signing_key: SigningKey) -> None:
    other = SigningKey.generate().verify_key.encode().hex()
    args = _signed(signing_key) | {"public_key": other}
    assert not is_valid_signature(**args, body=BODY)


def test_rejects_a_signature_that_is_not_hex(signing_key: SigningKey) -> None:
    args = _signed(signing_key) | {"signature": "not-hex"}
    assert not is_valid_signature(**args, body=BODY)


def test_rejects_an_empty_signature(signing_key: SigningKey) -> None:
    args = _signed(signing_key) | {"signature": ""}
    assert not is_valid_signature(**args, body=BODY)
