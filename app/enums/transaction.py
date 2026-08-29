from enum import Enum


class TransactionType(str, Enum):
    AIRTIME = "AIRTIME"
    MOBILE_DATA = "MOBILE_DATA"
    CABLE_TV = "CABLE_TV"
    ELECTRICITY = "ELECTRICITY"


class TransactionStatus(str, Enum):
    INITIATED = "INITIATED"
    PROCESSING = "PROCESSING"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    REVERSAL_PENDING = "REVERSAL_PENDING"
    REVERSED = "REVERSED"


class LedgerEntryDirection(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class LedgerAccountType(str, Enum):
    USER_WALLET = "USER_WALLET"
    PROVIDER_CLEARING = "PROVIDER_CLEARING"
    SYSTEM = "SYSTEM"
    SUSPENSE = "SUSPENSE"
    REVENUE = "REVENUE"


# Allowed forward state transitions
VALID_TRANSITIONS: dict[TransactionStatus, set[TransactionStatus]] = {
    TransactionStatus.INITIATED: {TransactionStatus.PROCESSING},
    TransactionStatus.PROCESSING: {
        TransactionStatus.SUCCESSFUL,
        TransactionStatus.FAILED,
        TransactionStatus.UNKNOWN,
    },
    TransactionStatus.FAILED: {TransactionStatus.REVERSAL_PENDING},
    TransactionStatus.REVERSAL_PENDING: {TransactionStatus.REVERSED},
    TransactionStatus.UNKNOWN: {
        TransactionStatus.SUCCESSFUL,
        TransactionStatus.FAILED,
    },
    TransactionStatus.SUCCESSFUL: set(),
    TransactionStatus.REVERSED: set(),
}
