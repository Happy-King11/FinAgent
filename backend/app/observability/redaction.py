"""日志敏感值脱敏工具。"""

def redact(value: str, secrets: tuple[str, ...] = ()) -> str:
    # 仅替换明确传入的敏感值，不对普通业务文本做不可逆改写。
    result = value
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    return result
