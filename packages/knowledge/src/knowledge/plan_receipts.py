"""Verify and read both original sealed payloads and canonical plan references."""
from .util import canonical_json, fingerprint, loads, require


def reference(identifier):
    return canonical_json({'version': 1, 'plan': identifier})


def matches(identifier, payload, plan):
    return payload == reference(identifier) or loads(payload) == plan


def plans(db):
    for identifier, receipt, payload in db.execute(
            'SELECT receipts.plan, receipts.payload, plans.payload FROM receipts '
            'LEFT JOIN plans ON plans.id=receipts.plan ORDER BY receipts.plan'):
        require(payload is not None, 'receipt-plan-mismatch')
        plan = loads(payload)
        require(fingerprint(plan) == identifier and matches(identifier, receipt, plan), 'receipt-plan-mismatch')
        yield identifier, plan
