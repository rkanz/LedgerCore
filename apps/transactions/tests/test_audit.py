import pytest

from apps.transactions.audit import record_audit_event
from apps.transactions.models import AuditLog


@pytest.mark.django_db
def test_record_audit_event(user):
    record_audit_event(
        action=AuditLog.Action.DEPOSIT,
        actor=user,
        details={
            "amount":"100",
            "currency":"USDT"
        }
    )
    audit_log=AuditLog.objects.get(actor=user)
    assert audit_log.action == AuditLog.Action.DEPOSIT
    assert audit_log.transaction is None
    assert audit_log.details == {
            "amount":"100",
            "currency":"USDT"
        }