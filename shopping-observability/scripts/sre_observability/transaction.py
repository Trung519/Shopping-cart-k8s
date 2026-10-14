"""Write-ahead Argo operation and field-aware compensation. Storage is untouched."""
import copy
import base64
import datetime
import json
import threading
import time
import uuid

from .core import Error, need, safe_snapshot
from .inventory import action_matches, managed, source_app, subset, wait_workload


# Purpose: Tạo timestamp chuẩn cho Kubernetes Lease.
# Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
# Flow: Giờ UTC có timezone → ISO8601 kết thúc bằng Z.
# Kiến thức liên quan: Lease.renewTime yêu cầu thời gian chuẩn; datetime.timezone.utc tránh giờ local mơ hồ.
def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


class Lease:
    # Purpose: Giữ độc quyền deploy/recover ở cấp cluster.
    # Syntax: a,b = ... unpack và gán nhiều giá trị theo thứ tự; số phần tử phải khớp.
    # Flow: Lease chưa có → create; có cùng run → renew; owner khác → RUN_BUSY; bật thread renew.
    # Kiến thức liên quan: Kubernetes Lease + holderIdentity giữ lock giữa các máy; không chiếm lock chỉ vì TTL cũ.
    def __init__(self, kube, namespace, run_id):
        self.kube, self.ns, self.run_id = kube, namespace, run_id
        self.name, self.stop, self.lost = "sre-observability-deploy", threading.Event(), False
        current = kube.get("lease", self.name, namespace, optional=True)
        if current:
            need(current["spec"].get("holderIdentity") == run_id, "RUN_BUSY", "S01", "Lease",
                 "Scope còn journal/lock của lượt khác.", "Chạy status/recover cho lượt đang giữ lock.")
            self.renew()
        else:
            lease = {"apiVersion": "coordination.k8s.io/v1", "kind": "Lease",
                     "metadata": {"name": self.name, "namespace": namespace},
                     "spec": {"holderIdentity": run_id, "leaseDurationSeconds": 60, "renewTime": utc()}}
            kube.cmd(["create", "-f", "-"], data=json.dumps(lease))
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    # Purpose: Gia hạn lock khi vẫn thuộc lượt hiện tại.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Đọc Lease → kiểm holder → JSON Patch test resourceVersion → cập nhật renewTime.
    # Kiến thức liên quan: Compare-and-swap ngăn gia hạn khi resource đã bị thay đổi đồng thời.
    def renew(self):
        obj = self.kube.get("lease", self.name, self.ns)
        need(obj["spec"].get("holderIdentity") == self.run_id, "LOCK_LOST", "runtime", "Lease", "Lock đã đổi owner.")
        self.kube.patch("lease", self.name, self.ns,
                        [{"op": "test", "path": "/metadata/resourceVersion", "value": obj["metadata"]["resourceVersion"]},
                         {"op": "replace", "path": "/spec/renewTime", "value": utc()}])

    # Purpose: Gia hạn Lease nền và ghi nhận khi không còn giữ lock.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Mỗi 15 giây renew; exception → lost=True và dừng thread; stop event → thoát.
    # Kiến thức liên quan: threading.Event.wait chờ có thể đánh thức; guard/check phát lỗi ở luồng deploy chính.
    def loop(self):
        while not self.stop.wait(15):
            try:
                self.renew()
            except Exception:
                self.lost = True
                return

    # Purpose: Dừng mutation khi thread không còn đảm bảo lock.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: lost=False → đi tiếp; True → LOCK_LOST.
    # Kiến thức liên quan: need tạo lỗi có cấu trúc để caller đi vào recovery.
    def check(self):
        need(not self.lost, "LOCK_LOST", "runtime", "Lease", "Không còn đảm bảo lock độc quyền.")

    # Purpose: Dừng renew và chỉ nhả Lease đúng ownership khi phục hồi hoàn tất.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dừng thread; retain=True giữ Lease; False → kiểm holder và DELETE với UID/resourceVersion.
    # Kiến thức liên quan: DeleteOptions preconditions ngăn xóa lock đã bị tạo lại hoặc đổi owner.
    def close(self, retain=False):
        self.stop.set()
        self.thread.join(timeout=20)
        if not retain:
            obj = self.kube.get("lease", self.name, self.ns, optional=True)
            if obj:
                need(obj["spec"].get("holderIdentity") == self.run_id, "LOCK_LOST", "cleanup", "Lease", "Không xóa lock của owner khác.")
                options = {"apiVersion": "v1", "kind": "DeleteOptions", "preconditions": {
                           "uid": obj["metadata"]["uid"], "resourceVersion": obj["metadata"]["resourceVersion"]}}
                self.kube.cmd(["delete", "--raw", "/apis/coordination.k8s.io/v1/namespaces/" + self.ns + "/leases/" + self.name,
                               "-f", "-"], json.dumps(options))


# Purpose: Đọc run ID gắn với Argo operation.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: Tìm info name=sre-run → value; operation thiếu → None.
# Kiến thức liên quan: next(generator,None) lấy kết quả đầu; run ID xác định lượt sở hữu operation.
def operation_id(operation):
    return next((i.get("value") for i in (operation or {}).get("info", []) if i.get("name") == "sre-run"), None)


# Purpose: Phân biệt từng operation của cùng một run.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: Tìm info name=sre-operation → token hoặc None.
# Kiến thức liên quan: Một run có nhiều batch; token riêng tránh nhận Succeeded của batch cũ.
def operation_token(operation):
    return next((i.get("value") for i in (operation or {}).get("info", []) if i.get("name") == "sre-operation"), None)


class Transaction:
    # Purpose: Gom config, API, journal và Lease cho transaction.
    # Syntax: a,b = ... unpack và gán nhiều giá trị theo thứ tự; số phần tử phải khớp.
    # Flow: Lấy run_id từ journal; lưu lease nếu được cấp để guard trước mutation.
    # Kiến thức liên quan: Transaction.sync/rollback dùng cùng journal write-ahead và ownership guard.
    def __init__(self, config, kube, journal, lease=None):
        self.config, self.kube, self.journal, self.lease = config, kube, journal, lease
        self.run_id = journal.data["run_id"]

    # Purpose: Kiểm Lease trước thao tác ghi resource.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Có lease → check; test không cấp lease → không gọi lock cluster.
    # Kiến thức liên quan: Lease.check phát LOCK_LOST khi renew thất bại; mock test chạy offline không giữ Lease thật.
    def guard(self):
        if self.lease:
            self.lease.check()

    # Purpose: Reconcile batch được chọn bằng đúng SHA và operation sở hữu.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Kiểm baseline → save PREPARED/token → patch Argo → chờ đúng operation/revision → verify fields/readiness.
    # Kiến thức liên quan: Write-ahead lưu intent trước ghi; SSA migration nhận ownership cũ để xóa field; prune=false giữ resource ngoài scope.
    def sync(self, name, actions):
        self.guard()
        app = source_app(self.config, self.kube, name)
        for action in actions:
            live = self.kube.get(action["kind"], action["name"], action["namespace"])
            need(not action.get("tracking_id") or live["metadata"].get("annotations", {}).get("argocd.argoproj.io/tracking-id") == action["tracking_id"],
                 "OWNER_CONFLICT", "S05", action["name"], "Argo resource owner đã đổi sau plan.")
            need(live["metadata"]["uid"] == action["uid"] and managed(live) == action["before"],
                 "PLAN_STALE", "S05", action["name"], "Resource đã thay đổi sau khi lập plan.")
            action["state"] = "PREPARED"
        token = uuid.uuid4().hex
        operation = {"info": [{"name": "sre-run", "value": self.run_id}, {"name": "sre-operation", "value": token}],
                     "sync": {"revisions": [self.journal.data["revision"]] * 2,
                              "prune": False, "syncStrategy": {"apply": {}},
                              "syncOptions": ["ServerSideApply=true", "ClientSideApplyMigration=true", "Replace=false", "Force=false"],
                              "resources": [{"group": a["apiVersion"].split("/")[0] if "/" in a["apiVersion"] else "",
                                             "kind": "Secret" if a["kind"] == "GeneratedScrapeConfig" else a["kind"],
                                             "name": a["name"], "namespace": a["namespace"]} for a in actions]}}
        self.journal.data.setdefault("operations", {})[name] = {"operation_id": token, "state": "PREPARED"}
        self.journal.save()  # durable BEFORE API write, including uncertain responses
        self.kube.patch("application", name, self.config["argo_namespace"],
                        [{"op": "test", "path": "/metadata/resourceVersion", "value": app["metadata"]["resourceVersion"]},
                         {"op": "add", "path": "/operation", "value": operation}])
        deadline = time.monotonic() + min(self.config["step_timeout"], self.kube.runner.deadline.remaining(self.config["step_timeout"]))
        seen = False
        while time.monotonic() < deadline:
            self.guard()
            app = self.kube.get("application", name, self.config["argo_namespace"])
            state = app.get("status", {}).get("operationState", {})
            mine = operation_id(state.get("operation")) == self.run_id and operation_token(state.get("operation")) == token
            need(not seen or mine, "OWNER_CONFLICT", "S05", name, "Operation đã bị thay bởi tác nhân khác.")
            if mine:
                seen = True
                phase = state.get("phase")
                need(phase not in ("Failed", "Error"), "ARGO_SYNC_FAILED", "S05", name, "Argo operation thất bại.")
                if phase == "Succeeded" and not app.get("operation"):
                    actual = state.get("syncResult", {}).get("revisions", [])
                    need(actual == [self.journal.data["revision"]] * 2, "OWNER_CONFLICT", "S05", name, "Operation dùng revision không đúng plan.")
                    for action in actions:
                        live = self.kube.get(action["kind"], action["name"], action["namespace"])
                        after = managed(live)
                        need(action_matches(live, action), "ARGO_SYNC_FAILED", "S05", action["name"], "Live resource chưa cập nhật/xóa đủ field được quản lý.")
                        action["after"], action["state"] = safe_snapshot(after), "APPLIED"
                        self.journal.save()
                        wait_workload(self.kube, action, self.config["step_timeout"])
                    self.journal.data["operations"][name]["state"] = "SUCCEEDED"
                    self.journal.save()
                    return
            time.sleep(2)
        raise Error("ARGO_SYNC_TIMEOUT", "S05", name, "Hết thời gian chờ operation đúng run ID.")

    # Purpose: Ngăn Argo còn ghi khi rollback bắt đầu.
    # Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
    # Flow: Kiểm run/token → chờ controller nhận → phase Terminating → chờ terminal; owner khác hoặc timeout → lỗi.
    # Kiến thức liên quan: Không xóa operation queue; Argo controller xử lý termination qua operationState phase.
    def stop_operation(self, name):
        app = self.kube.get("application", name, self.config["argo_namespace"])
        state = app.get("status", {}).get("operationState", {})
        active = app.get("operation")
        if not active and state.get("phase") not in ("Running", "Terminating"):
            return
        operation = active or state.get("operation")
        need(operation_id(operation) == self.run_id, "ROLLBACK_CONFLICT", "R00", name, "Không terminate operation của lượt khác.")
        token = self.journal.data.get("operations", {}).get(name, {}).get("operation_id")
        need(not token or operation_token(operation) == token, "ROLLBACK_CONFLICT", "R00", name, "Operation token khác journal.")
        receive_deadline = time.monotonic() + min(30, self.kube.runner.deadline.remaining(30))
        while active and (operation_id(state.get("operation")) != self.run_id or
                          (token and operation_token(state.get("operation")) != token)):
            need(time.monotonic() < receive_deadline, "ROLLBACK_INCOMPLETE", "R00", name, "Controller chưa nhận operation để terminate.")
            time.sleep(2)
            app = self.kube.get("application", name, self.config["argo_namespace"])
            active = app.get("operation")
            state = app.get("status", {}).get("operationState", {})
            if active:
                need(operation_id(active) == self.run_id and (not token or operation_token(active) == token),
                     "ROLLBACK_CONFLICT", "R00", name, "Operation queue đã bị đổi owner.")
        if not active and state.get("phase") in ("Failed", "Error", "Succeeded"):
            return
        # Argo controller's supported termination phase; never remove operation.
        if state.get("phase") != "Terminating":
            need(state and operation_id(state.get("operation")) == self.run_id, "ROLLBACK_INCOMPLETE", "R00", name,
                 "Operation chưa được controller nhận; recovery cần chờ nhận trước.")
            self.kube.patch("application", name, self.config["argo_namespace"],
                            [{"op": "test", "path": "/metadata/resourceVersion", "value": app["metadata"]["resourceVersion"]},
                             {"op": "replace", "path": "/status/operationState/phase", "value": "Terminating"}])
        end = time.monotonic() + min(60, self.kube.runner.deadline.remaining(60))
        while time.monotonic() < end:
            obj = self.kube.get("application", name, self.config["argo_namespace"])
            state = obj.get("status", {}).get("operationState", {})
            need(operation_id(state.get("operation")) == self.run_id, "ROLLBACK_CONFLICT", "R00", name, "Operation owner đã thay đổi.")
            need(not token or operation_token(state.get("operation")) == token, "ROLLBACK_CONFLICT", "R00", name, "Operation token đã đổi.")
            if not obj.get("operation") and state.get("phase") in ("Failed", "Error", "Succeeded"):
                return
            time.sleep(2)
        raise Error("ROLLBACK_INCOMPLETE", "R00", name, "Argo chưa xác nhận ngừng operation; không restore khi controller còn ghi.")

    # Purpose: Trả field đã thay đổi về snapshot mà không ghi đè actor khác.
    # Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
    # Flow: Kiểm owner/UID/current → đã đúng vẫn chờ ready; khác → save intent, CAS patch baseline, wait+verify.
    # Kiến thức liên quan: JSON Patch test resourceVersion chống race; field absence được restore bằng remove, không chỉ set giá trị.
    def restore(self, action):
        self.guard()
        live = self.kube.get(action["kind"], action["name"], action["namespace"])
        need(not action.get("tracking_id") or live["metadata"].get("annotations", {}).get("argocd.argoproj.io/tracking-id") == action["tracking_id"],
             "ROLLBACK_CONFLICT", "R02", action["name"], "Argo resource owner đã thay đổi.")
        need(live["metadata"]["uid"] == action["uid"], "ROLLBACK_CONFLICT", "R02", action["name"], "Resource đã bị tạo lại bởi tác nhân khác.")
        current = managed(live)
        if current == action["before"]:
            wait_workload(self.kube, action, self.config["step_timeout"])
            action["state"] = "RESTORED"
            self.journal.save()
            return
        expected = action.get("after")
        need(current == expected if expected else action_matches(live, action),
             "ROLLBACK_CONFLICT", "R02", action["name"], "Field đã bị đổi ngoài transaction; không ghi đè.")
        patch = [{"op": "test", "path": "/metadata/resourceVersion", "value": live["metadata"]["resourceVersion"]}]
        for key in set(current) | set(action["before"]):
            path = "/metadata/" + key.removeprefix("metadata_") if key.startswith("metadata_") else "/" + key
            if key == "scrape_config":
                path = "/data/additional-scrape-configs.yaml"
            if key in action["before"]:
                value = action["before"][key]
                if key == "scrape_config":
                    value = base64.b64encode(value.encode()).decode()
                patch.append({"op": "add", "path": path, "value": value})
            else:
                patch.append({"op": "remove", "path": path})
        action["state"] = "RESTORE_PREPARED"
        self.journal.save()
        if action.get("tracking_id"):
            # Compensate as the existing Argo field manager, so a restored field
            # remains discoverable for the next plan/removal instead of becoming
            # an unrelated kubectl-patch-owned extra that diff would ignore.
            self.kube.patch(action["kind"], action["name"], action["namespace"], patch, manager="argocd-controller")
        else:
            self.kube.patch(action["kind"], action["name"], action["namespace"], patch)
        wait_workload(self.kube, action, self.config["step_timeout"])
        need(managed(self.kube.get(action["kind"], action["name"], action["namespace"])) == action["before"],
             "ROLLBACK_INCOMPLETE", "R04", action["name"], "Live config chưa khớp baseline sau restore.")
        action["state"] = "RESTORED"
        self.journal.save()

    # Purpose: Hoàn tác các bước đã chạm resource và giữ lỗi conflict rõ ràng.
    # Syntax: lambda tạo hàm ngắn tại chỗ; closure dùng biến từ hàm/lớp bao ngoài; comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Stop operations → reverse app order, configs trước workloads/CR → restore; lỗi → INCOMPLETE, đủ → RESOURCES_RESTORED.
    # Kiến thức liên quan: Resource restore chưa đủ để nhả lock; recover_baseline kiểm thêm cleanup/business/PVC.
    def rollback(self):
        self.journal.data["state"] = "ROLLING_BACK"
        self.journal.save()
        errors, blocked = [], set()
        for name in self.journal.data.get("operations", {}):
            try:
                self.stop_operation(name)
            except Error as error:
                errors.append(error.record())
                blocked.add(name)
        # Restore each app in reverse deployment order, but restore its configs
        # BEFORE waiting for its old workload; otherwise a bad ConfigMap can
        # keep the restored image unready and prevent the next compensation.
        app_order = list(dict.fromkeys(a["app"] for a in reversed(self.journal.data.get("actions", []))))
        ordered = []
        for app in app_order:
            group = [a for a in reversed(self.journal.data["actions"]) if a["app"] == app]
            ordered.extend(sorted(group, key=lambda a: a["kind"] in ("Deployment", "StatefulSet", "DaemonSet", "Prometheus", "Alertmanager")))
        config_conflicts = set()
        for action in ordered:
            if action["state"] == "PLANNED":
                continue
            if action["app"] in blocked:
                continue
            if action["app"] in config_conflicts and action["kind"] in ("Deployment", "StatefulSet", "DaemonSet", "Prometheus", "Alertmanager"):
                continue
            try:
                self.restore(action)
            except Error as error:
                errors.append(error.record())
                if action["kind"] in ("ConfigMap", "GeneratedScrapeConfig"):
                    config_conflicts.add(action["app"])
        self.journal.data["rollback_errors"] = errors
        self.journal.data["reconciliation_pending"] = bool(self.journal.data.get("operations"))
        self.journal.data["state"] = "ROLLBACK_INCOMPLETE" if errors else "RESOURCES_RESTORED"
        self.journal.save()
        return not errors
