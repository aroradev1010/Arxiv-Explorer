class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


class AssetError(Exception):
    """Sanitized startup failure; messages must not include absolute paths."""
