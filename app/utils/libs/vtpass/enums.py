VTPASS_ERRORS: dict[str, str] = {
    "010": "Low wallet balance",
    "011": "Invalid service ID",
    "012": "Transaction verification failed",
    "013": "Invalid phone number",
    "014": "Invalid amount",
    "015": "Transaction failed",
    "016": "Service temporarily unavailable",
    "017": "Invalid biller code",
    "018": "Duplicate transaction",
    "019": "Invalid variation code",
    "020": "Transaction limit exceeded",
    "021": "Account suspended",
    "022": "Authentication failed",
    "023": "Request timeout",
    "024": "Invalid request ID",
}

VTPASS_SUCCESS: dict[str, str] = {
    "000": "Transaction successful",
    "099": "Transaction processing",
}
