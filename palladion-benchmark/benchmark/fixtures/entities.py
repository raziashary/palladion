"""Fixed vocabulary of the Meridian Switchworks world: organisations, tenants, roles, principals and more (B02-T01.01).

Everything is generated from one seed by code. The vocabulary is evaluator-side state; nothing here is arm-visible.
Every record is fictional and carries the notice when serialised.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, TypeVar

from benchmark.fixtures import FICTIONAL_NOTICE, digest_of, to_plain

T = TypeVar("T")


class WorldError(ValueError):
    """The world violates one of its own invariants. The message names the record, never a secret."""


def rng_for(seed: int, purpose: str) -> random.Random:
    """An independent deterministic stream per purpose, so adding one generator never shifts another's draws."""
    return random.Random(f"meridian-world:{seed}:{purpose}")


@dataclass(frozen=True)
class Organization:
    org_id: str
    name: str
    kind: str


@dataclass(frozen=True)
class Tenant:
    tenant_id: str
    slug: str
    name: str
    org_id: str
    internal: bool


@dataclass(frozen=True)
class Role:
    role_id: str
    name: str
    can_approve: bool
    internal_only: bool


@dataclass(frozen=True)
class Principal:
    principal_id: str
    tenant_id: str
    role_id: str
    display_name: str


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str


@dataclass(frozen=True)
class MerchantClass:
    class_id: str
    name: str
    risk_tier: int


@dataclass(frozen=True)
class TransactionType:
    txn_type_id: str
    name: str
    settles: bool


@dataclass(frozen=True)
class ErrorCode:
    code: str
    name: str
    txn_type_id: str
    severity: int


@dataclass(frozen=True)
class CaseType:
    case_type_id: str
    name: str
    txn_type_id: str


@dataclass(frozen=True)
class Merchant:
    merchant_id: str
    tenant_id: str
    display_name: str
    class_id: str


@dataclass(frozen=True)
class WorldEntities:
    seed: int
    organizations: tuple[Organization, ...]
    tenants: tuple[Tenant, ...]
    roles: tuple[Role, ...]
    principals: tuple[Principal, ...]
    products: tuple[Product, ...]
    merchant_classes: tuple[MerchantClass, ...]
    transaction_types: tuple[TransactionType, ...]
    error_codes: tuple[ErrorCode, ...]
    case_types: tuple[CaseType, ...]
    merchants: tuple[Merchant, ...]

    def records(self) -> Iterator[dict[str, Any]]:
        """Every entity as a plain record carrying the fictional notice, in a fixed order."""
        for kind in (
            "organizations",
            "tenants",
            "roles",
            "principals",
            "products",
            "merchant_classes",
            "transaction_types",
            "error_codes",
            "case_types",
            "merchants",
        ):
            for item in getattr(self, kind):
                yield {"kind": kind, "fictional": FICTIONAL_NOTICE, **to_plain(item)}

    def digest(self) -> str:
        return digest_of({"seed": self.seed, "records": list(self.records())})

    def tenant(self, tenant_id: str) -> Tenant:
        return lookup(self.tenants, "tenant_id", tenant_id)

    def principal(self, principal_id: str) -> Principal:
        return lookup(self.principals, "principal_id", principal_id)

    def merchant(self, merchant_id: str) -> Merchant:
        return lookup(self.merchants, "merchant_id", merchant_id)


def lookup(items: tuple[T, ...], attr: str, value: str) -> T:
    for item in items:
        if getattr(item, attr) == value:
            return item
    raise WorldError(f"unknown {attr}: {value}")


ORG_ID = "ORG-MERIDIAN"
INTERNAL_TENANT = "T-MERIDIAN"
_PARTNERS = (("northwave", "Northwave Bank"), ("harborline", "Harborline Payments"), ("kestrel", "Kestrel Financial"))
_ROLES = (
    ("support_l1", "Support level 1", False, False),
    ("support_l2", "Support level 2", False, False),
    ("risk_analyst", "Risk analyst", False, False),
    ("engineer", "Platform engineer", False, True),
    ("approver", "Policy approver", True, True),
    ("auditor", "Internal auditor", False, True),
)
_PRODUCTS = (
    "Switch Core",
    "QR Gateway",
    "Card Acquiring",
    "Transfer Rail",
    "Settlement Engine",
    "Dispute Desk",
    "Merchant Console",
    "Reconciliation Hub",
)
_MERCHANT_CLASSES = (
    ("MC-RETAIL", "Retail", 1),
    ("MC-FOOD", "Food and beverage", 1),
    ("MC-TRAVEL", "Travel", 3),
    ("MC-DIGITAL", "Digital goods", 4),
    ("MC-UTILITY", "Utilities", 2),
)
_TXN_TYPES = (
    ("card_payment", "Card payment", True),
    ("qr_payment", "QR payment", True),
    ("bank_transfer", "Bank transfer", True),
    ("refund", "Refund", True),
    ("reversal", "Reversal", False),
    ("chargeback", "Chargeback", True),
    ("settlement_payout", "Settlement payout", True),
    ("top_up", "Wallet top-up", True),
    ("bill_payment", "Bill payment", True),
    ("cash_withdrawal", "Cash withdrawal", False),
)
_FAULTS = (
    "Issuer timeout",
    "Duplicate reference",
    "Amount mismatch",
    "Beneficiary account closed",
    "Signature verification failed",
    "Limit exceeded",
    "Clearing file rejected",
    "Currency not enabled",
    "Merchant suspended",
    "Late capture",
    "Partial capture mismatch",
    "Settlement hold",
    "Routing unavailable",
    "Stale authorization",
    "Invalid terminal",
)
_CASE_TYPES = (
    ("failed_payment_dispute", "Failed payment dispute", "card_payment"),
    ("missing_settlement", "Missing settlement", "settlement_payout"),
    ("reversal_request", "Reversal request", "reversal"),
    ("refund_request", "Refund request", "refund"),
    ("chargeback_response", "Chargeback response", "chargeback"),
    ("duplicate_charge", "Duplicate charge", "qr_payment"),
    ("transfer_not_received", "Transfer not received", "bank_transfer"),
    ("top_up_missing", "Top-up not credited", "top_up"),
    ("bill_not_posted", "Bill payment not posted", "bill_payment"),
    ("cash_withdrawal_failure", "Cash withdrawal failure", "cash_withdrawal"),
)
_NAME_HEAD = (
    "Sentosa",
    "Harapan",
    "Mekar",
    "Lintang",
    "Cahaya",
    "Bahari",
    "Nusa",
    "Permata",
    "Cendana",
    "Gemilang",
    "Rimba",
    "Surya",
    "Kencana",
    "Teduh",
    "Laut",
)
_NAME_TAIL = (
    "Mart",
    "Kopi",
    "Mobile",
    "Bakery",
    "Pharmacy",
    "Travel",
    "Digital",
    "Laundry",
    "Electronics",
    "Fresh",
    "Garage",
    "Books",
)
_GIVEN = (
    "Ayu",
    "Bimo",
    "Citra",
    "Dewi",
    "Eko",
    "Farah",
    "Galih",
    "Hana",
    "Indra",
    "Joko",
    "Kirana",
    "Lukman",
    "Maya",
    "Nadia",
    "Oka",
    "Putri",
    "Rangga",
    "Sari",
    "Tama",
    "Wulan",
)
MERCHANTS_PER_TENANT = 14
SHARED_MERCHANT_NAMES = 6
ERROR_CODE_COUNT = 60


def build_entities(seed: int) -> WorldEntities:
    """Generate the fixed vocabulary of the world from one seed. The same seed gives the same bytes."""
    organizations = (Organization(ORG_ID, "Meridian Switchworks", "payment switch operator"),)
    partner_tenants = [Tenant(f"T-{slug.upper()}", slug, name, ORG_ID, False) for slug, name in _PARTNERS]
    tenants = (*partner_tenants, Tenant(INTERNAL_TENANT, "meridian", "Meridian Switchworks (internal)", ORG_ID, True))
    roles = tuple(Role(rid, name, approve, internal) for rid, name, approve, internal in _ROLES)
    principals = _build_principals(seed, tenants)
    products = tuple(Product(f"PRD-{i + 1:02d}", name) for i, name in enumerate(_PRODUCTS))
    merchant_classes = tuple(MerchantClass(cid, name, tier) for cid, name, tier in _MERCHANT_CLASSES)
    transaction_types = tuple(TransactionType(tid, name, settles) for tid, name, settles in _TXN_TYPES)
    case_types = tuple(CaseType(f"CT-{cid.upper()}", name, tid) for cid, name, tid in _CASE_TYPES)
    world = WorldEntities(
        seed=seed,
        organizations=organizations,
        tenants=tenants,
        roles=roles,
        principals=principals,
        products=products,
        merchant_classes=merchant_classes,
        transaction_types=transaction_types,
        error_codes=_build_error_codes(seed, transaction_types),
        case_types=case_types,
        merchants=_build_merchants(seed, tenants, merchant_classes),
    )
    validate_entities(world)
    return world


def validate_entities(world: WorldEntities) -> None:
    """Refuse a world whose ids repeat or whose references dangle. Run at build time and by fixture validation."""
    for kind in ("tenants", "roles", "principals", "merchants", "error_codes", "case_types", "transaction_types"):
        ids = [getattr(item, _ID_FIELD[kind]) for item in getattr(world, kind)]
        if len(set(ids)) != len(ids):
            raise WorldError(f"duplicate id in {kind}")
    tenants = {t.tenant_id for t in world.tenants}
    roles = {r.role_id for r in world.roles}
    classes = {c.class_id for c in world.merchant_classes}
    txn_types = {t.txn_type_id for t in world.transaction_types}
    if any(p.tenant_id not in tenants or p.role_id not in roles for p in world.principals):
        raise WorldError("principal references an unknown tenant or role")
    if any(m.tenant_id not in tenants or m.class_id not in classes for m in world.merchants):
        raise WorldError("merchant references an unknown tenant or class")
    if any(e.txn_type_id not in txn_types for e in world.error_codes) or any(
        c.txn_type_id not in txn_types for c in world.case_types
    ):
        raise WorldError("error code or case type references an unknown transaction type")


_ID_FIELD = {
    "tenants": "tenant_id",
    "roles": "role_id",
    "principals": "principal_id",
    "merchants": "merchant_id",
    "error_codes": "code",
    "case_types": "case_type_id",
    "transaction_types": "txn_type_id",
}


def _build_principals(seed: int, tenants: tuple[Tenant, ...]) -> tuple[Principal, ...]:
    rng = rng_for(seed, "principals")
    names = list(_GIVEN)
    rng.shuffle(names)
    partner_roles = ("support_l1", "support_l1", "support_l2", "risk_analyst")
    internal_roles = ("engineer", "engineer", "approver", "approver", "auditor")
    out: list[Principal] = []
    for tenant in tenants:
        counters: dict[str, int] = {}
        for role in internal_roles if tenant.internal else partner_roles:
            counters[role] = counters.get(role, 0) + 1
            name = names[len(out) % len(names)]
            out.append(Principal(f"{tenant.slug}.{role}.{counters[role]:02d}", tenant.tenant_id, role, name))
    return tuple(out)


def _build_error_codes(seed: int, txn_types: tuple[TransactionType, ...]) -> tuple[ErrorCode, ...]:
    rng = rng_for(seed, "error_codes")
    numbers = sorted(rng.sample(range(1000, 9999), ERROR_CODE_COUNT))
    out: list[ErrorCode] = []
    for number in numbers:
        txn = rng.choice(txn_types)
        out.append(ErrorCode(f"MS-{number}", rng.choice(_FAULTS), txn.txn_type_id, rng.randint(1, 4)))
    return tuple(out)


def _build_merchants(
    seed: int, tenants: tuple[Tenant, ...], classes: tuple[MerchantClass, ...]
) -> tuple[Merchant, ...]:
    """Partner tenants get merchants; some display names repeat across tenants under distinct ids (merge identity)."""
    rng = rng_for(seed, "merchants")
    partners = [t for t in tenants if not t.internal]
    combos = [f"{head} {tail}" for head in _NAME_HEAD for tail in _NAME_TAIL]
    rng.shuffle(combos)
    shared, unique = combos[:SHARED_MERCHANT_NAMES], combos[SHARED_MERCHANT_NAMES:]
    names_by_tenant: dict[str, list[str]] = {t.tenant_id: [] for t in partners}
    for name in shared:
        for tenant in rng.sample(partners, 2):
            names_by_tenant[tenant.tenant_id].append(name)
    cursor = 0
    for tenant in partners:
        slots = MERCHANTS_PER_TENANT - len(names_by_tenant[tenant.tenant_id])
        names_by_tenant[tenant.tenant_id].extend(unique[cursor : cursor + slots])
        cursor += slots
    out: list[Merchant] = []
    for tenant in partners:
        numbers = rng.sample(range(1, 9999), MERCHANTS_PER_TENANT)
        for number, name in zip(numbers, names_by_tenant[tenant.tenant_id], strict=True):
            out.append(
                Merchant(
                    f"MRC-{tenant.slug[:3].upper()}-{number:04d}", tenant.tenant_id, name, rng.choice(classes).class_id
                )
            )
    return tuple(out)
