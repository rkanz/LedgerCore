from rest_framework.throttling import UserRateThrottle


class FinancialOperationThrottle(UserRateThrottle):
    scope="financial_operation"