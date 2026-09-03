"""Deterministic primitives for the synthetic fixture seed.

Every value here is fixed. The seed never reads the machine clock or generates a
random id, so a run on any machine produces byte-identical rows. The fixed clock
and the UUIDv5 derivation rule come from
``docs/migration/phase-0/SYNTHETIC_TEST_DATA.md``; the explicit ids below are the
ones that document pins by hand.
"""

import uuid
from datetime import date

# Fixed clock. Phase 0 forbids deriving any fixture date from the real date.
CLOCK_DATE = date(2026, 8, 27)
TODAY = date(2026, 8, 27)
YESTERDAY = date(2026, 8, 26)
PLUS_7D = date(2026, 9, 3)
PLUS_14D = date(2026, 9, 10)
PLUS_30D = date(2026, 9, 26)
PLUS_60D = date(2026, 10, 26)
PLUS_90D = date(2026, 11, 25)
MINUS_1D = date(2026, 8, 26)
AUG_START = date(2026, 8, 1)
JUL_END = date(2026, 7, 31)

# UUIDv5 namespace for every derived fixture id (Phase 0).
NAMESPACE = uuid.UUID("00000000-0000-5000-8000-000000000001")

# Seed identities are inert to real authentication: this issuer is not the live
# Keycloak issuer, so the application-user resolver never matches a seeded row
# against a real token. The synthetic-login verifier creates its own rows.
SEED_ISSUER = "https://seed.workloop.test"


def derive(
    table: str,
    tenant: str,
    branch: str | None = None,
    actor: str | None = None,
    scenario: str = "default",
) -> uuid.UUID:
    """Derive a fixture id from its canonical name.

    Canonical name: ``workloop/<table>/<tenant>/<branch-or-none>/<actor-or-none>/<scenario>``.
    """
    name = "/".join(["workloop", table, tenant, branch or "none", actor or "none", scenario])
    return uuid.uuid5(NAMESPACE, name)


# Explicit tenant, branch, identity, and financial ids that Phase 0 pins by hand.
HORIZON = "horizon"
CEDAR = "cedar"

COMPANY_ID = {
    HORIZON: derive("companies", HORIZON, scenario="tenant"),
    CEDAR: derive("companies", CEDAR, scenario="tenant"),
}

# Branch ids are the explicit Phase 0 values (its legacy "companies" rows).
BRANCH_DXB = uuid.UUID("20000000-0000-4000-8000-000000000001")
BRANCH_AUH = uuid.UUID("20000000-0000-4000-8000-000000000002")
BRANCH_SHJ = uuid.UUID("30000000-0000-4000-8000-000000000001")
BRANCH_DHC = uuid.UUID("30000000-0000-4000-8000-000000000002")

ADMIN_APP_USER = {
    HORIZON: uuid.UUID("10000000-0000-4000-8000-000000000001"),
    CEDAR: uuid.UUID("10000000-0000-4000-8000-000000000002"),
}


def emirates_id_display(sequence: int) -> str:
    """Format the fixture Emirates ID as the stored 3-4-7-1 display string."""
    raw = f"7841990{sequence:08d}"  # 15 digits
    return f"{raw[0:3]}-{raw[3:7]}-{raw[7:14]}-{raw[14:15]}"


def identifiers(sequence: int) -> dict[str, str]:
    """Generate the fixture government and bank identifiers for a sequence.

    The rules are Phase 0's exact formulas. Every value is fictional and fails a
    real-world lookup while still passing the project format validators.
    """
    return {
        "mol_id": f"900000000000{sequence:02d}",
        "iban": f"AE{sequence:021d}",
        "emirates_id": emirates_id_display(sequence),
        "visa_number": f"999/2026/{sequence:07d}",
        "passport_number": f"TESTP{sequence:06d}",
        "labour_card_number": f"TESTLC{sequence:06d}",
        "phone": f"+971{500000000 + sequence}",
    }
