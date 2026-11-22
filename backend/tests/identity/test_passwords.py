from app.modules.identity.domain.passwords import hash_password, verify_password


def test_hash_is_not_plaintext_and_verifies():
    stored = hash_password("s3cret-pass")
    assert "s3cret-pass" not in stored
    assert stored.startswith("scrypt$")
    assert verify_password("s3cret-pass", stored)
    assert not verify_password("wrong", stored)


def test_salts_are_unique():
    assert hash_password("same") != hash_password("same")


def test_malformed_hash_is_rejected_not_raised():
    for bad in ["", "plaintext", "scrypt$x$y", "md5$1$2$3$a$b", "scrypt$a$b$c$!!$!!"]:
        assert verify_password("x", bad) is False
