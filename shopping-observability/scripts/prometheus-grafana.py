#!/usr/bin/env python3
"""Compatibility entrypoint. Deployment now requires an explicit saved plan."""
import argparse
from sre_observability.cli import main


# Purpose: Giữ entry point cũ và hướng người dùng sang CLI thống nhất.
# Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
# Flow: --check-only → main(check); --verify-only → main(verify --read-only); không có mode → hướng dẫn plan/deploy và exit2.
# Kiến thức liên quan: argparse mutually_exclusive_group chặn hai mode cùng lúc; main là CLI observability thống nhất.
def legacy():
    parser = argparse.ArgumentParser(description="Dùng observability.py cho toàn stack có rollback.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--context")
    args = parser.parse_args()
    if not (args.check_only or args.verify_only):
        print("Chạy observability.py plan, sau đó deploy --plan-id ID. Xem scripts/README.md.")
        return 2
    options = ["check"] if args.check_only else ["verify", "--read-only"]
    if args.context:
        options += ["--context", args.context]
    return main(options)


if __name__ == "__main__":
    raise SystemExit(legacy())
