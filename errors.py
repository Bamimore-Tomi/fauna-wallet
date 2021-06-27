class WalletNotFound(Exception):
    """Raised when user does not have at least one wallet"""

    def __str__(self):
        return "No wallets found with this user id"


class InsufficientBalance(Exception):
    """Raise when user does not have sufficient balance for a transaction."""

    def __str__(self):
        return "Insufficient  Balance"
