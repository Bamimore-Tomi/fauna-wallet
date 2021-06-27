class WalletNotFound(Exception):
    """Raised when user does not have at least one wallet"""

    def __str__(self):
        return "Now wallets found with this user id"
