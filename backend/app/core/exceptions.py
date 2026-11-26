"""领域异常：携带稳定错误码和 HTTP 映射状态。"""

class DomainError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(DomainError):
    def __init__(self, message: str = "resource not found"):
        super().__init__("NOT_FOUND", message, 404)


class IdempotencyConflict(DomainError):
    def __init__(self, message: str = "idempotency key conflicts with a different request"):
        super().__init__("IDEMPOTENCY_CONFLICT", message, 409)
