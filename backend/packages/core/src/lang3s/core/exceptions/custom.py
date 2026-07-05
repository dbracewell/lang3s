class CodedException(Exception):
    code: int


class UnauthorizedException(CodedException):
    code: int = 401

    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message)


class NotFoundException(CodedException):
    code: int = 404

    def __init__(self, message: str = "Not Found"):
        super().__init__(message)


class BadDataException(CodedException):
    code: int = 400

    def __init__(self, message: str = "Bad Data"):
        super().__init__(message)


class TooManyRequests(CodedException):
    code: int = 429

    def __init__(self, message: str = "Too Many Requests"):
        super().__init__(message)
