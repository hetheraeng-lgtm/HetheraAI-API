class AppException(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InsufficientBalanceError(AppException):
    pass


class DuplicateIdempotencyKeyError(AppException):
    pass


class InvalidTransactionStateError(AppException):
    pass


class WalletNotFoundError(AppException):
    pass


class TransactionNotFoundError(AppException):
    pass


class InvalidVariationError(AppException):
    pass


class ProviderValidationError(AppException):
    pass
