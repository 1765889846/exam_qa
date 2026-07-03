"""业务异常体系。"""


class AppException(Exception):
    """业务异常基类，携带 HTTP 状态码和消息。"""

    def __init__(self, message: str = "服务器内部错误", status_code: int = 500, detail: str = ""):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class NotFoundException(AppException):
    def __init__(self, message: str = "该资料不存在", detail: str = ""):
        super().__init__(message, status_code=404, detail=detail)


class BadRequestException(AppException):
    def __init__(self, message: str = "请求参数错误", detail: str = ""):
        super().__init__(message, status_code=400, detail=detail)


class LLMTimeoutException(AppException):
    def __init__(self, message: str = "AI 服务响应超时", detail: str = ""):
        super().__init__(message, status_code=504, detail=detail)


class LLMAPIException(AppException):
    def __init__(self, message: str = "AI 服务暂时不可用", detail: str = ""):
        super().__init__(message, status_code=502, detail=detail)


class UnsupportedFormatException(AppException):
    def __init__(self, message: str = "仅接受 PDF/TXT/MD/DOC/DOCX/PPTX", detail: str = ""):
        super().__init__(message, status_code=400, detail=detail)


class ServiceUnavailableException(AppException):
    def __init__(self, message: str = "服务暂时不可用", detail: str = ""):
        super().__init__(message, status_code=503, detail=detail)
