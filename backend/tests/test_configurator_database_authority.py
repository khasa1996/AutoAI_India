from configurator_database_authority import assess_database_authority


def test_database_authority_requires_explicit_expected_name():
    result = assess_database_authority("autoai", None)
    assert result == {
        "ready": False,
        "reason": "expected production database name is not configured",
    }


def test_database_authority_rejects_database_name_mismatch():
    result = assess_database_authority("auto_ai", "autoai")
    assert result == {
        "ready": False,
        "reason": "configured database does not match expected production database",
    }


def test_database_authority_accepts_exact_database_name():
    result = assess_database_authority("autoai", "autoai")
    assert result == {"ready": True, "reason": None}
