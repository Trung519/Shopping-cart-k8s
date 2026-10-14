import argparse
import builtins
import copy
import json
import re
import time
import uuid
from pathlib import Path

from .application import Application
from .config import fingerprint, load
from .core import Deadline, Error, Forwards, Journal, Kube, LocalLock, Runner, atomic, digest, install_signals, need
from .inventory import build_plan, inspect, managed, pvc_identity, source_app, surge_mib
from .telemetry import Verify
from .transaction import Lease, Transaction

ASCII = False

# Purpose: Đổi icon sang chữ khi terminal chỉ hỗ trợ ASCII.
# Syntax: *values gom đối số không tên thành tuple; **kwargs gom đối số có tên thành dict; lúc gọi thì unpack; lambda tạo hàm ngắn.
# Flow: (✅,Done,123) → reduce thay icon mỗi value → tuple ([OK],Done,123) → builtins.print.
# Kiến thức liên quan: reduce gộp các lượt thay; lambda text,pair thực hiện một lượt; __import__ lấy module theo tên; builtins.print là hàm in gốc.
def print(*values, **kwargs):
    if ASCII:
        mapping = {"✅": "[OK]", "❌": "[FAIL]", "ℹ": "[INFO]", "↩": "[RECOVERY]", "📄": "[REPORT]", "→": "->"}
        values = tuple(__import__("functools").reduce(lambda text, pair: text.replace(*pair), mapping.items(), str(value)) for value in values)
    builtins.print(*values, **kwargs)


# Purpose: Chọn đúng file plan/run và chặn ID không hợp lệ.
# Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
# Flow: ID hex 32 ký tự → log_dir/obs-run-ID.json hoặc obs-plan-ID.json; sai → CONFIG_INVALID.
# Kiến thức liên quan: Path ghép đường dẫn; regex chặn path traversal từ input run/plan ID.
def path_for(config, identifier, kind="run"):
    need(re.fullmatch(r"[a-f0-9]{32}", identifier or ""), "CONFIG_INVALID", "S00", "ID", "ID phải là 32 ký tự hex do script tạo.")
    return Path(config["log_dir"]) / ("obs-" + kind + "-" + identifier + ".json")


# Purpose: Khai báo lệnh và option CLI theo từng tác vụ.
# Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
# Flow: Tạo subcommands → options chung → deploy bắt plan ID; recover/status bắt run ID; verify có read-only.
# Kiến thức liên quan: argparse kiểm tham số; store_true tạo bool, default=None giữ quyền ưu tiên profile khi chưa truyền.
def parser():
    root = argparse.ArgumentParser(description="Observability: kiểm tra, deploy có rollback, nghiệm thu request thật.")
    commands = root.add_subparsers(dest="command")
    for name in ("plan", "check", "deploy", "verify", "status", "rollback", "recover"):
        sub = commands.add_parser(name)
        sub.add_argument("--config", help="YAML overrides; bỏ trống dùng profile shopping-cart-local")
        sub.add_argument("--context")
        sub.add_argument("--ascii", action="store_true")
        sub.add_argument("--allow-test-writes", action="store_true", default=None,
                         help="Cho phép fixture user/product/cart/order riêng; luôn cleanup")
        if name == "deploy":
            sub.add_argument("--plan-id", required=True)
        if name in ("rollback", "recover", "status"):
            sub.add_argument("--run-id", required=True)
        if name == "verify":
            sub.add_argument("--read-only", action="store_true", help="Chỉ public request; không báo full PASS")
            sub.add_argument("--collect-errors", action="store_true", help="Kiểm đủ flows và báo tất cả gate lỗi; không đổi tiêu chuẩn PASS")
    return root


# Purpose: In thông báo bước đã đạt và ghi cùng kết quả vào journal.
# Syntax: X if C else Y chọn X khi điều kiện C đúng, còn lại dùng Y (fallback).
# Flow: S04 + summary → icon/ASCII message → journal.step(PASS).
# Kiến thức liên quan: flush=True đẩy output ngay; Journal.step ghi evidence ngắn có timestamp.
def show_step(journal, step, message, ascii_mode=False):
    print(("[OK]" if ascii_mode else "✅") + " " + step + " · " + message, flush=True)
    journal.step(step, details={"summary": message})


# Purpose: Tổng hợp đúng capability, không đánh logs FAIL vì metric lỗi.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: Đọc signal_results từng route/checkout → PASS/FAIL/PARTIAL; capability không khai báo → NOT_DECLARED.
# Kiến thức liên quan: Contract xác định bằng chứng bắt buộc; mesh metrics và application_metrics được báo riêng.
def coverage_summary(journal, contract):
    results = journal.data.get("signal_results", {})
    routes = contract["routes"] + [contract["checkout"]]
    coverage = journal.data["coverage"]
    for output, signal in (("traces", "trace"), ("logs", "logs"), ("mesh_metrics", "metrics")):
        statuses = [results.get(route["id"], {}).get(signal, "NOT_TESTED") for route in routes]
        coverage[output] = "FAIL" if "FAIL" in statuses else "PASS" if all(s == "PASS" for s in statuses) else "PARTIAL" if "PASS" in statuses else "NOT_TESTED"
    for capability in ("application_metrics", "redis", "rabbitmq"):
        if capability == "application_metrics":
            required = [r for r in routes if r.get(capability)]
        elif capability == "redis":
            required = [r for r in routes if any(d["system"] == "redis" for d in r.get("databases", []))]
        else:
            required = [r for r in routes if any(e["type"] == "rabbitmq" for e in r.get("edges", []))]
        statuses = [results.get(r["id"], {}).get(capability, "NOT_TESTED") for r in required]
        coverage[capability] = "NOT_DECLARED" if not required else "FAIL" if "FAIL" in statuses else "PASS" if all(s == "PASS" for s in statuses) else "NOT_TESTED"
    app_metrics, mesh_metrics = coverage["application_metrics"], coverage["mesh_metrics"]
    coverage["metrics"] = "FAIL" if "FAIL" in (app_metrics, mesh_metrics) else "MESH_ONLY" if app_metrics == "NOT_DECLARED" and mesh_metrics == "PASS" else "PASS_DECLARED" if app_metrics == mesh_metrics == "PASS" else "PARTIAL" if "PASS" in (app_metrics, mesh_metrics) else "NOT_TESTED"
    coverage["application_metric_services"] = sorted({m["service"] for r in routes for m in r.get("application_metrics", [])})
    journal.save()


# Purpose: Ghi metric baseline failure vào đúng capability của route.
# Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
# Flow: Error APP_METRIC_* → app metric FAIL; METRIC_* → mesh FAIL nếu chưa có app failure; save.
# Kiến thức liên quan: signal_results giữ bằng chứng từng phần; coverage_summary không suy đoán logs lỗi từ mã metric.
def signal_failure(journal, route, error):
    proof = journal.data.setdefault("signal_results", {}).setdefault(route["id"], {})
    if error.code.startswith("APP_METRIC_"):
        proof["application_metrics"] = "FAIL"
    elif error.code.startswith("METRIC_"):
        # Do not clobber a failed app metric with a mesh failure classification.
        if proof.get("application_metrics") != "FAIL":
            proof["metrics"] = "FAIL"
    journal.save()


# Purpose: Phân loại loss/reset/unknown đúng theo cửa sổ quan sát Collector.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: So counters trước/sau → reset ưu tiên, rồi loss tăng, missing, cuối cùng no-new-loss; trả evidence.
# Kiến thức liên quan: Counter giảm có thể do restart; series thiếu không phải 0; dữ liệu aggregate không chứng minh từng trace.
def collector_window(before, after):
    counters = [key for key in after if not key.endswith("size")]
    loss = [key for key in counters if "failed" in key or "refused" in key]
    reset = any(before[key] is not None and after[key] is not None and after[key] < before[key] for key in counters)
    dropped = any(before[key] is not None and after[key] is not None and after[key] > before[key] for key in loss)
    missing = any(before[key] is None or after[key] is None for key in loss)
    evidence = "COUNTER_RESET" if reset else "LOSS_OBSERVED" if dropped else "UNKNOWN" if missing else "NO_NEW_LOSS_OBSERVED"
    return {"before": before, "after": after, "missing_series": [key for key, value in after.items() if value is None],
            "loss_evidence": evidence, "scope": "aggregate observation window; not per-trace delivery proof"}


# Purpose: Cho counter của pod mới có cơ hội xuất hiện trước khi đo baseline, không suy missing thành 0.
# Syntax: except Error as error phân loại lỗi; raise giữ nguyên lỗi khác; vòng try lồng chỉ chờ series còn thiếu.
# Flow: Đọc baseline → missing+GET thì gọi GET một lần → chờ scrape ≤90 giây → baseline thật hoặc lỗi route; mutation không warmup.
# Kiến thức liên quan: Application.call ghi trace ID riêng cho GET khởi động; metric_baseline kiểm freshness; Deadline giới hạn thời gian chung.
def route_baseline(app, verifier, route, kube):
    try:
        return verifier.metric_baseline(route)
    except Error as error:
        missing = ("METRIC_MISSING", "APP_METRIC_MISSING")
        if route.get("method") != "GET" or error.code not in missing:
            raise
        app.call(route)
        last = error
        end = time.monotonic() + min(90, kube.runner.deadline.remaining(90))
        while time.monotonic() < end:
            try:
                return verifier.metric_baseline(route)
            except Error as pending:
                if pending.code not in missing:
                    raise
                last = pending
            time.sleep(2)
        raise Error(last.code, "S09", route["id"], "Counter vẫn thiếu sau GET khởi động và chờ scrape.",
                    "Kiểm tra scrape job, namespace/workload và exporter; xem report.") from None


# Purpose: Nghiệm thu hệ thống qua request thật rồi luôn cleanup fixture.
# Syntax: raise ... from None ẩn exception gốc khỏi thông báo để tránh lộ dữ liệu; finally luôn chạy để cleanup, dù nhánh try return hay phát lỗi. **mapping unpack các key/value vào dict mới.
# Flow: Baseline/backend → routes/auth/checkout → alerts+loss window → coverage; finally cleanup có deadline riêng.
# Kiến thức liên quan: Application tạo fixture riêng; Verify kiểm span/log/counter; cleanup_error lưu intent để recover retry.
def verify_all(config, kube, forwards, journal, read_only=False, collect_errors=False):
    verifier = Verify(config, kube, forwards, journal)
    app = Application(config, kube, forwards, journal)
    journal.data["coverage"] = {"metrics": "NOT_TESTED", "logs": "NOT_TESTED", "traces": "NOT_TESTED",
                                 "rabbitmq": "NOT_TESTED", "redis": "NOT_TESTED", "alerts": "NOT_TESTED"}
    try:
        app.public_baseline()
        journal.data["rabbitmq_inventory"] = verifier.rabbit()
        journal.step("S04")
        journal.data["backend_probe"] = verifier.backend_probe()
        journal.step("S06")
        before_loss = verifier.losses()
        authenticated = not read_only and config["allow_test_writes"]
        if authenticated:
            app.authenticate()
        for route in config["contract_data"]["routes"]:
            if route.get("authenticated") and not authenticated:
                journal.data.setdefault("not_tested", []).append(route["id"])
                continue
            try:
                before = route_baseline(app, verifier, route, kube)
                row, response = app.call(route)
                need(isinstance(response, (dict, list)), "RESPONSE_INVALID", "S08", route["id"], "Response không khớp schema business.")
                proof = verifier.verify_route(row, route, before)
                journal.data.setdefault("acceptance", []).append(proof)
                scope = "mesh trace/access log" if route.get("scope") == "mesh-http-only" else "trace + app logs"
                print("✅ S09 · " + route["id"] + ": HTTP + " + scope + " + metric delta", flush=True)
            except Error as error:
                signal_failure(journal, route, error)
                if not collect_errors:
                    raise
                journal.data.setdefault("acceptance_failures", []).append({"route": route["id"], **error.record()})
                print("❌ S09 · " + route["id"] + ": " + error.code + " · " + error.subject, flush=True)
            journal.save()
        if authenticated:
            route = config["contract_data"]["checkout"]
            try:
                before = verifier.metric_baseline(route)
                row = app.checkout()
                journal.data.setdefault("acceptance", []).append(verifier.verify_route(row, route, before))
            except Error as error:
                signal_failure(journal, route, error)
                if not collect_errors:
                    raise
                journal.data.setdefault("acceptance_failures", []).append({"route": route["id"], **error.record()})
                print("❌ S09 · checkout: " + error.code + " · " + error.subject, flush=True)
        else:
            journal.data.setdefault("not_tested", []).append("checkout")
        journal.data["alerts"] = verifier.alerts()
        journal.data["coverage"]["alerts"] = "PASS_EVALUATOR_ONLY"
        after_loss = verifier.losses()
        journal.data["collector_metrics"] = collector_window(before_loss, after_loss)
        journal.save()
        for name, initial in before_loss.items():
            final = after_loss[name]
            if not name.endswith("size"):
                need(initial is None or final is None or final >= initial, "METRIC_RESET", "S09", name, "Collector restart/counter reset trong acceptance.")
            if "failed" in name or "refused" in name:
                need(initial is None or final is None or final == initial, "TELEMETRY_DROPPED", "S09", name, "Có loss/refusal mới trong acceptance.")
        failures = journal.data.get("acceptance_failures", [])
        coverage_summary(journal, config["contract_data"])
        need(not failures, "ACCEPTANCE_FAILED", "S09", "full contract", str(len(failures)) + " flow chưa qua nghiệm thu.", "Xem acceptance_failures trong report; sửa từng capability bị thiếu.")
        need(not journal.data.get("not_tested"), "CONTRACT_NOT_FULLY_TESTED", "S09", "full contract",
             "Public checks đã qua; auth/Redis/AMQP flows chưa được test.", "Chạy verify --allow-test-writes để nghiệm thu đầy đủ.")
    except (Exception, KeyboardInterrupt) as error:
        coverage_summary(journal, config["contract_data"])
        journal.data["forward_failure"] = error.record() if isinstance(error, Error) else {"code": "INTERRUPTED"}
        journal.save()
        raise
    finally:
        forward_deadline = kube.runner.deadline
        cleanup_deadline = Deadline(config["rollback_timeout"])
        kube.runner.deadline = cleanup_deadline
        app.http.deadline = app.admin.deadline = cleanup_deadline
        try:
            app.cleanup()
            journal.step("S11_CLEANUP")
        except Exception as error:
            journal.data["cleanup_error"] = error.record() if isinstance(error, Error) else {"code": "CLEANUP_FAILED"}
            journal.save()
            raise Error("CLEANUP_FAILED", "S11", "fixtures", "Chưa hoàn tất cleanup; journal giữ recovery intent.") from None
        finally:
            kube.runner.deadline = forward_deadline


# Purpose: Deploy tuần tự sau preflight và phục hồi nếu bất kỳ gate nào lỗi.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt; raise ... from None ẩn exception gốc khỏi thông báo để tránh lộ dữ liệu.
# Flow: Revalidate plan/SHA/PVC/RAM/images → Lease → batches → acceptance+stability; lỗi → recover_baseline.
# Kiến thức liên quan: Argo selected sync là writer; independent rollback deadline và Lease giữ an toàn khi forward timeout.
def perform_deploy(config, kube, journal, forwards):
    need(config["allow_test_writes"], "TEST_WRITES_REQUIRED", "S03", "full deploy", "Full nghiệm thu cần fixture auth/AMQP.")
    need(not config["notification_required"], "NOTIFICATION_NOT_SUPPORTED", "S03", "receiver", "V1 chưa nghiệm thu notification receiver.")
    need(not journal.data["dirty_apps"], "SOURCE_NOT_COMMITTED", "S02", ",".join(journal.data["dirty_apps"]),
         "Argo đọc remote; source local có thay đổi chưa commit/push.")
    need(time.time() - journal.data["created"] < config["plan_ttl"], "PLAN_STALE", "S02", "plan", "Plan đã hết TTL; tạo plan mới.")
    current = inspect(config, kube, mutation=True)
    need(current["cluster_uid"] == journal.data["baseline"]["cluster_uid"] and pvc_identity(current["pvcs"]) == pvc_identity(journal.data["baseline"]["pvcs"])
         and current["mesh_hash"] == journal.data["baseline"]["mesh_hash"], "PLAN_STALE", "S03", "cluster", "Cluster/storage/mesh đổi sau plan.")
    remote = kube.runner.run(["git", "-C", config["repo_root"], "ls-remote", "origin", "refs/heads/" + config["branch"]]).split()[0]
    need(remote == journal.data["revision"], "PLAN_STALE", "S02", "Git", "Remote SHA đổi sau plan.")
    for expected in journal.data["apps"]:
        app = source_app(config, kube, expected["name"])
        need(digest(app["spec"]) == expected["spec_hash"], "PLAN_STALE", "S02", expected["name"], "Argo spec đã đổi.")
    refreshed = build_plan(config, kube, current)
    need(not refreshed["dirty_apps"], "SOURCE_NOT_COMMITTED", "S02", "Git", "Source local đổi sau plan; commit/push trước.")
    need(digest(refreshed["actions"]) == digest(journal.data["actions"]), "PLAN_STALE", "S02", "resources", "Live/source manifest đổi sau plan.")
    need(not refreshed["blocking_reasons"], "IMAGE_UNAVAILABLE", "S02", "deploy/rollback", "Chưa xác minh image trên mọi node; xem blocking_reasons của plan.")
    worst_surge = max([0, *[surge_mib(a, current["node_count"]) for a in journal.data["actions"]]])
    need(current["vm_free_memory_mib"] >= config["min_memory_mib"] + worst_surge, "CAPACITY_LOW", "S03", "VM", "Không đủ memory cho surge lớn nhất và recovery headroom.")
    # No change until baseline prerequisites and Rabbit consumer have been proven.
    app = Application(config, kube, forwards, journal)
    app.public_baseline()
    pre = Verify(config, kube, forwards, journal)
    pre.rabbit()
    journal.data["lease"] = {"state": "PREPARED", "holder": journal.data["run_id"]}
    journal.save()
    lease = Lease(kube, config["obs_namespace"], journal.data["run_id"])
    journal.data["lease"]["state"] = "ACQUIRED"
    journal.save()
    tx = Transaction(config, kube, journal, lease)
    journal.data["state"] = "RUNNING"
    journal.save()
    incomplete = False
    try:
        for entry in config["managed_apps"]:
            actions = [a for a in journal.data["actions"] if a["app"] == entry["name"]]
            if not actions:
                continue
            # Configs/services first; then ONE workload/CR per operation. Never
            # launch all observability rollouts simultaneously on this small VM.
            control = [a for a in actions if a["kind"] not in ("Deployment", "StatefulSet", "DaemonSet", "Prometheus", "Alertmanager")]
            rollouts = [a for a in actions if a not in control]
            batches = ([control] if control else []) + [[a] for a in rollouts]
            for batch in batches:
                capacity = inspect(config, kube, mutation=True)
                need(capacity["vm_free_memory_mib"] >= config["min_memory_mib"] + sum(surge_mib(a, capacity["node_count"]) for a in batch),
                     "CAPACITY_LOW", "S07", entry["name"], "Không đủ memory cho rollout này.")
                tx.sync(entry["name"], batch)
            show_step(journal, "S05" if entry["name"] == config["obs_app"] else "S07", "Reconciled " + entry["name"])
            if entry["name"] == config["obs_app"]:
                Verify(config, kube, forwards, journal).backend_probe()
        verify_all(config, kube, forwards, journal)
        end = time.monotonic() + config["stability_seconds"]
        while time.monotonic() < end:
            lease.check()
            kube.runner.deadline.remaining()
            app.public_baseline()
            time.sleep(min(5, max(0, end - time.monotonic())))
        inspect(config, kube)
        journal.data["state"] = "SUCCEEDED"
        journal.save()
    except (Exception, KeyboardInterrupt) as error:
        journal.data["failure"] = error.record() if isinstance(error, Error) else {"code": "INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "INTERNAL_ERROR"}
        journal.save()
        kube.runner.deadline = Deadline(config["rollback_timeout"])
        app.http.deadline = app.admin.deadline = kube.runner.deadline
        # Stop writes before business/config compensation.
        try:
            restored = recover_baseline(config, kube, forwards, journal, tx)
        except (Exception, KeyboardInterrupt):
            incomplete = True
            journal.data["state"] = "ROLLBACK_INCOMPLETE"
            journal.save()
            raise Error("ROLLBACK_INCOMPLETE", "R05", "run", "Recovery bị ngắt hoặc chưa hoàn tất.") from None
        incomplete = not restored
        journal.data["state"] = "ROLLBACK_INCOMPLETE" if incomplete else "ROLLED_BACK"
        journal.save()
        if incomplete:
            raise Error("ROLLBACK_INCOMPLETE", "R05", "run", "Có bước chưa phục hồi; không deploy lại.", "Chạy recover --run-id với ID của report.") from None
        raise error
    finally:
        try:
            lease.close(retain=incomplete)
            if not incomplete:
                journal.data["lease"]["state"] = "RELEASED"
                journal.save()
        except (Exception, KeyboardInterrupt):
            journal.data["state"] = "ROLLBACK_INCOMPLETE"
            journal.save()
            raise Error("ROLLBACK_INCOMPLETE", "R05", "Lease", "Chưa giải phóng được lock đúng ownership.") from None


# Purpose: Chỉ kết luận rollback xong sau mọi kiểm chứng phục hồi.
# Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
# Flow: tx.rollback → cleanup → public HTTP → inspect cluster/PVC; tất cả đạt → ROLLED_BACK, lỗi → INCOMPLETE.
# Kiến thức liên quan: pvc_identity so UID/volume không phụ thuộc thứ tự; caller chỉ nhả Lease khi hàm trả True.
def recover_baseline(config, kube, forwards, journal, tx):
    try:
        # Restore services/configs before requesting business cleanup; broken auth
        # must not prevent compensation of the very change that broke auth.
        restored = tx.rollback()
        journal.data["state"] = "RECOVERY_VERIFYING"
        journal.save()
        need(restored, "ROLLBACK_INCOMPLETE", "R02", "resources", "Có resource chưa restore; giữ lock.")
        app = Application(config, kube, forwards, journal)
        app.cleanup()
        app.public_baseline()
        baseline = inspect(config, kube)
        need(baseline["cluster_uid"] == journal.data["baseline"]["cluster_uid"] and
             pvc_identity(baseline["pvcs"]) == pvc_identity(journal.data["baseline"]["pvcs"]),
             "ROLLBACK_INCOMPLETE", "R04", "PVC", "Cluster hoặc UID/volume PVC khác baseline.")
        journal.data.pop("cleanup_error", None)
        journal.step("R04_BUSINESS_BASELINE")
        journal.data["state"] = "ROLLED_BACK"
        journal.save()
        return True
    except (Exception, KeyboardInterrupt) as error:
        record = error.record() if isinstance(error, Error) else {"code": "RECOVERY_INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "RECOVERY_FAILED"}
        journal.data.setdefault("rollback_errors", []).append(record)
        journal.data["state"] = "ROLLBACK_INCOMPLETE"
        journal.save()
        return False


# Purpose: Điều phối CLI và trả exit code ngắn theo kết quả thực tế.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt; finally luôn chạy để cleanup, dù nhánh try return hay phát lỗi.
# Flow: Parse/load → lock/journal/tunnels → check/plan/deploy/verify/recover/status → error report → finally cleanup local.
# Kiến thức liên quan: LocalLock/Lease bảo vệ scope; exit 5 biểu thị recovery còn thiếu, status đọc journal không deploy lại.
def main(argv=None):
    global ASCII
    args = parser().parse_args(argv)
    ASCII = getattr(args, "ascii", False)
    if not args.command:
        parser().print_help()
        return 0
    journal, forwards, lock = None, None, None
    try:
        config = load(args.config, args.context, args.allow_test_writes)
        log_dir = Path(config["log_dir"])
        need(log_dir.is_dir(), "TRACE_MISSING", "S00", "Log_agents", "Chưa có thư mục trace trung tâm.")
        runner = Runner(config["timeout"])
        kube = Kube(config["context"], runner)
        install_signals()
        if args.command in ("rollback", "recover"):
            saved = Journal(path_for(config, args.run_id))
            need(not args.context or args.context == saved.data["config"]["context"], "CONTEXT_MISMATCH", "R00", "context", "Context khác journal.")
            config = saved.data["config"]
        if args.command == "status":
            journal = Journal(path_for(config, args.run_id))
            print(json.dumps({"run_id": args.run_id, "state": journal.data["state"], "coverage": journal.data.get("coverage", {}),
                              "failure": journal.data.get("failure"), "rollback_errors": journal.data.get("rollback_errors", [])}, ensure_ascii=False, indent=2))
            return 0
        lock = LocalLock(log_dir / ("obs-scope-" + digest(config["context"])[:12] + ".lock"))
        forwards = Forwards(kube, log_dir)
        if args.command in ("rollback", "recover"):
            journal = Journal(path_for(config, args.run_id))
            config = journal.data["config"]
            need(not args.context or args.context == config["context"], "CONTEXT_MISMATCH", "R00", "context", "Context khác journal.")
            kube = Kube(config["context"], runner)
            forwards.kube = kube
            need(kube.get("namespace", "kube-system")["metadata"]["uid"] == journal.data["baseline"]["cluster_uid"], "CONTEXT_MISMATCH", "R00", "cluster", "Cluster khác baseline journal.")
            runner.deadline = Deadline(config["rollback_timeout"])
            touched = bool(journal.data.get("operations")) or any(a["state"] != "PLANNED" for a in journal.data.get("actions", []))
            lease = Lease(kube, config["obs_namespace"], args.run_id) if touched or journal.data.get("lease") else None
            ok = False
            try:
                tx = Transaction(config, kube, journal, lease)
                ok = recover_baseline(config, kube, forwards, journal, tx)
            finally:
                if lease:
                    try:
                        lease.close(retain=not ok)
                    except (Exception, KeyboardInterrupt):
                        ok = False
                        journal.data["state"] = "ROLLBACK_INCOMPLETE"
                        journal.save()
                    if ok:
                        journal.data["lease"] = {"state": "RELEASED", "holder": args.run_id}
                        journal.save()
            need(ok, "ROLLBACK_INCOMPLETE", "R05", "run", "Có conflict hoặc bước chưa restore.")
            print("↩ Recovery hoàn tất. Git desired có thể còn cần sửa; xem reconciliation_pending trong report.")
            return 0
        if args.command == "deploy":
            planned = json.loads(path_for(config, args.plan_id, "plan").read_text())
            need(planned["config_hash"] == fingerprint(config), "PLAN_STALE", "S00", "config", "Config/contract khác plan.")
            data = copy.deepcopy(planned)
            data["run_id"] = uuid.uuid4().hex
            journal = Journal(path_for(config, data["run_id"]), data)
            print("ℹ Run ID: " + data["run_id"], flush=True)
            perform_deploy(config, kube, journal, forwards)
        else:
            run_id = uuid.uuid4().hex
            journal = Journal(path_for(config, run_id), {"run_id": run_id, "config": config,
                              "config_hash": fingerprint(config), "state": "CHECKING", "actions": []})
            print("ℹ Run ID: " + run_id, flush=True)
            baseline = inspect(config, kube)
            journal.data["baseline"] = baseline
            show_step(journal, "S01", "Workloads/dependencies/storage baseline Ready", args.ascii)
            if args.command in ("plan", "check"):
                planned = build_plan(config, kube, baseline)
                journal.data.update(planned)
                journal.save()
                app = Application(config, kube, forwards, journal)
                app.public_baseline()
                verifier = Verify(config, kube, forwards, journal)
                journal.data["rabbitmq_inventory"] = verifier.rabbit()
                if args.command == "plan":
                    journal.data["plan_id"] = run_id
                    journal.save()
                    atomic(path_for(config, run_id, "plan"), journal.data)
                    print("✅ Plan ID: " + run_id + "; " + str(len(planned["actions"])) + " thay đổi reversible.")
                else:
                    journal.data["state"] = "CHECKED"
                    journal.save()
                    print("✅ CHECK: source/render/prerequisites đã kiểm tra; chưa deploy.")
                if planned["dirty_apps"]:
                    print("ℹ Deploy sẽ dừng: source chưa commit/push cho " + ",".join(planned["dirty_apps"]))
                if planned["blocking_reasons"]:
                    print("ℹ Deploy sẽ dừng: một số image deploy/rollback chưa có bằng chứng cache trên mọi node.")
            elif args.command == "verify":
                verify_all(config, kube, forwards, journal, args.read_only, args.collect_errors)
                journal.data["state"] = "VERIFIED"
                journal.save()
                print("✅ Contract đã khai báo đạt; xem coverage cho phần chưa khai báo.")
        print("📄 Report: " + str(journal.path))
        return 0
    except (Exception, KeyboardInterrupt) as exception:
        error = exception if isinstance(exception, Error) else Error("INTERRUPTED" if isinstance(exception, KeyboardInterrupt) else "INTERNAL_ERROR",
                        "runtime", "run", "Đã ngắt lượt chạy." if isinstance(exception, KeyboardInterrupt) else "Không hoàn tất thao tác; xem state trong report.")
        if journal:
            journal.data.setdefault("failure", error.record())
            if journal.data["state"] not in ("ROLLED_BACK", "ROLLBACK_INCOMPLETE"):
                journal.data["state"] = "CLEANUP_INCOMPLETE" if journal.data.get("cleanup_error") else "FAILED"
            journal.save()
        icon = "[FAIL]" if getattr(args, "ascii", False) else "❌"
        print(icon + " [" + error.code + "] " + error.step + " · " + error.subject + ": " + error.message)
        print("→ " + error.action)
        if journal:
            print("↩ State: " + journal.data["state"])
            print("📄 Report: " + str(journal.path))
        if journal and journal.data["state"] == "ROLLED_BACK":
            return 4
        if error.code in ("ROLLBACK_INCOMPLETE", "CLEANUP_FAILED") or (journal and journal.data.get("cleanup_error")):
            return 5
        if isinstance(exception, KeyboardInterrupt):
            return 130
        return 6 if args.command == "verify" else 2 if error.step == "S00" else 3
    finally:
        if forwards:
            forwards.close()
        if lock:
            lock.close()
