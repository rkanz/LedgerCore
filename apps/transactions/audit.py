import logging

from apps.transactions.models import AuditLog, Transaction

logger = logging.getLogger(__name__)


def record_audit_event(
    *,
    action:str,
    actor=None,
    transaction:Transaction | None = None,
    details:dict | None = None,

)-> None:
        AuditLog.objects.create(
            action=action,
            actor=actor,
            transaction=transaction,
            details=details or {}
        )
