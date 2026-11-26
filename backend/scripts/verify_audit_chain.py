"""命令行校验指定案例的审计哈希链。"""

import argparse

from app.api.deps import container


def main() -> int:
    # 该脚本读取应用容器中的审计实现，返回值可直接用于 CI 门禁。
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("--tenant-id", default="tenant-demo")
    args = parser.parse_args()
    valid = container.audit.verify(args.case_id, args.tenant_id)
    print("valid" if valid else "invalid")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
