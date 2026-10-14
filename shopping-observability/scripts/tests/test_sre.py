"""Offline API integration: faults do not touch the user's running cluster."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sre_observability.config import load, merge
from sre_observability.core import Error, Journal, LocalLock, atomic, safe_snapshot
from sre_observability.inventory import ready, subset, managed, memory_mib, surge_mib
from sre_observability.telemetry import flatten, graph_gaps, ident, log_ids
from sre_observability.transaction import Transaction, operation_id
from sre_observability.telemetry import Verify
from sre_observability.application import Application
from sre_observability.core import HTTP


# Purpose: Tạo ConfigMap giả để test compensation offline.
# Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
# Flow: value=old,uid=same → resource có resourceVersion=1 và data.endpoint.
# Kiến thức liên quan: FakeKube đọc/patch dict này; đây không phải resource cluster thật.
def obj(value="old", uid="same"):
    return {"kind": "ConfigMap", "metadata": {"name": "cfg", "uid": uid, "resourceVersion": "1"}, "data": {"endpoint": value}}


class FakeKube:
    # Purpose: Tạo API giả có thể chủ động inject lỗi.
    # Syntax: a,b = ... unpack và gán nhiều giá trị theo thứ tự; số phần tử phải khớp.
    # Flow: Copy resource → patches=[]; outage/lose_response/race mặc định False.
    # Kiến thức liên quan: deepcopy tách test state; fault flag mô phỏng API outage, mất response và concurrent write.
    def __init__(self, current):
        self.current = copy.deepcopy(current)
        self.patches = []
        self.outage, self.lose_response, self.race = False, False, False

    # Purpose: Mô phỏng đọc resource và operation của owner khác.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: outage → Error; application → operation another-run; còn lại → deepcopy current.
    # Kiến thức liên quan: API fake không kết nối cluster; ownership test dùng operation_id để từ chối another-run.
    def get(self, kind, name=None, namespace=None, optional=False):
        if self.outage:
            raise Error("HTTP_UNREACHABLE", "runtime", "API", "offline")
        if kind == "application":
            return {"metadata": {"resourceVersion": "1"}, "status": {"operationState": {
                "operation": {"info": [{"name": "sre-run", "value": "another-run"}]}, "phase": "Running"}},
                "operation": {"info": [{"name": "sre-run", "value": "another-run"}]}}
        return copy.deepcopy(self.current)

    # Purpose: Mô phỏng JSON Patch, CAS và lỗi sau khi ghi thành công.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: race đổi version → test precondition; apply patch → tăng version; lose_response → lỗi sau write.
    # Kiến thức liên quan: CAS kiểm resourceVersion; lost response không có nghĩa API chưa ghi.
    def patch(self, kind, name, namespace, changes, manager=None):
        self.last_manager = manager
        if self.race:
            self.current["metadata"]["resourceVersion"] = "99"
        for change in changes:
            if change["op"] == "test":
                if self.current["metadata"]["resourceVersion"] != change["value"]:
                    raise Error("COMMAND_FAILED", "runtime", "CAS", "concurrent write")
            else:
                segments = change["path"].strip("/").split("/")
                target = self.current
                for segment in segments[:-1]:
                    target = target.setdefault(segment, {})
                if change["op"] == "remove":
                    target.pop(segments[-1])
                else:
                    target[segments[-1]] = copy.deepcopy(change["value"])
        self.patches.append(changes)
        self.current["metadata"]["resourceVersion"] = "2"
        if self.lose_response:
            self.lose_response = False
            raise Error("COMMAND_TIMEOUT", "runtime", "write", "lost response")


class TransactionTests(unittest.TestCase):
    # Purpose: Tạo journal và API giả riêng cho mỗi test rollback.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Temp folder → action PREPARED old→new → FakeKube new → Transaction.
    # Kiến thức liên quan: unittest gọi setUp trước từng test; TemporaryDirectory cô lập journal khỏi report thật.
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.action = {"app": "app", "kind": "ConfigMap", "name": "cfg", "namespace": "ns", "uid": "same",
                       "before": {"data": {"endpoint": "old"}}, "desired": {"data": {"endpoint": "new"}}, "state": "PREPARED"}
        self.journal = Journal(Path(self.temp.name) / "journal.json", {"run_id": "r", "actions": [self.action]})
        self.k = FakeKube(obj("new"))
        self.tx = Transaction({"argo_namespace": "argocd", "step_timeout": 1}, self.k, self.journal)

    # Purpose: Dọn file tạm sau mỗi test transaction.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Test kết thúc → temp.cleanup xóa thư mục journal giả.
    # Kiến thức liên quan: unittest gọi tearDown cả khi assertion test thất bại.
    def tearDown(self):
        self.temp.cleanup()

    # Purpose: Kiểm restore được intent PREPARED dù response ghi trước đó bị mất.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → self.tx.restore; kỳ vọng 'RESTORED', 1.
    # Kiến thức liên quan: assertEqual so hai giá trị.
    def test_uncertain_api_response_recovers_by_live_state(self):
        self.tx.restore(self.action)
        self.assertEqual(self.k.current["data"], {"endpoint": "old"})
        self.assertEqual(self.action["state"], "RESTORED")
        self.tx.restore(self.action)
        self.assertEqual(len(self.k.patches), 1)

    # Purpose: Kiểm không ghi đè field người vận hành khác đã sửa.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → self.tx.restore; kỳ vọng 'ROLLBACK_CONFLICT'.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_other_operator_change_not_overwritten(self):
        self.k.current["data"]["endpoint"] = "operator-change"
        with self.assertRaises(Error) as ctx:
            self.tx.restore(self.action)
        self.assertEqual(ctx.exception.code, "ROLLBACK_CONFLICT")
        self.assertFalse(self.k.patches)

    # Purpose: Kiểm resource bị tạo lại với UID khác không bị restore nhầm.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → self.tx.restore; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_recreated_uid_not_touched(self):
        self.k.current["metadata"]["uid"] = "other"
        with self.assertRaises(Error):
            self.tx.restore(self.action)
        self.assertFalse(self.k.patches)

    # Purpose: Kiểm restore rồi crash trước save vẫn recover được mà không ghi lại.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → self.tx.restore → restore; kỳ vọng 'RESTORE_PREPARED', 'RESTORED'.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_write_then_crash_recovery_idempotent(self):
        self.k.lose_response = True
        with self.assertRaises(Error):
            self.tx.restore(self.action)
        reloaded = Journal(self.journal.path)
        self.assertEqual(reloaded.data["actions"][0]["state"], "RESTORE_PREPARED")
        Transaction(self.tx.config, self.k, reloaded).restore(reloaded.data["actions"][0])
        self.assertEqual(reloaded.data["actions"][0]["state"], "RESTORED")

    # Purpose: Kiểm CAS chặn race khi resourceVersion đổi giữa get và patch.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → self.tx.restore; kỳ vọng 'new'.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_resource_version_cas_race(self):
        self.k.race = True
        with self.assertRaises(Error):
            self.tx.restore(self.action)
        self.assertEqual(self.k.current["data"]["endpoint"], "new")

    # Purpose: Kiểm action độc lập vẫn được restore khi action khác conflict.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → self.tx.rollback; kỳ vọng 'old', 'ROLLBACK_INCOMPLETE'.
    # Kiến thức liên quan: assertEqual so hai giá trị; assertFalse yêu cầu sai.
    def test_independent_actions_continue_after_conflict(self):
        bad = copy.deepcopy(self.action)
        bad["uid"] = "wrong"
        self.journal.data["actions"].append(bad)
        self.assertFalse(self.tx.rollback())
        self.assertEqual(self.k.current["data"]["endpoint"], "old")
        self.assertEqual(self.journal.data["state"], "ROLLBACK_INCOMPLETE")

    # Purpose: Kiểm API outage không bị kết luận rollback thành công.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → self.tx.rollback; kỳ vọng 'ROLLBACK_INCOMPLETE'.
    # Kiến thức liên quan: assertEqual so hai giá trị; assertFalse yêu cầu sai.
    def test_api_outage_is_incomplete_not_success(self):
        self.k.outage = True
        self.assertFalse(self.tx.rollback())
        self.assertEqual(self.journal.data["state"], "ROLLBACK_INCOMPLETE")

    # Purpose: Kiểm không terminate Argo operation của run khác.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → self.tx.stop_operation; kỳ vọng 'ROLLBACK_CONFLICT'.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_other_run_operation_not_terminated(self):
        with self.assertRaises(Error) as ctx:
            self.tx.stop_operation("app")
        self.assertEqual(ctx.exception.code, "ROLLBACK_CONFLICT")
        self.assertFalse(self.k.patches)

    # Purpose: Kiểm action chưa ghi API không bị rollback.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → self.tx.rollback; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertTrue yêu cầu đúng; assertFalse yêu cầu sai.
    def test_planned_not_applied_action_not_restored(self):
        self.action["state"] = "PLANNED"
        self.assertTrue(self.tx.rollback())
        self.assertFalse(self.k.patches)

    # Purpose: Kiểm field được thêm lúc deploy được xóa khi baseline không có.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → self.tx.restore; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertNotIn yêu cầu không tồn tại phần tử.
    def test_field_absence_preserved_after_rollback(self):
        self.k.current["metadata"]["labels"] = {"new": "label"}
        self.action["desired"]["metadata_labels"] = {"new": "label"}
        self.tx.restore(self.action)
        self.assertNotIn("labels", self.k.current["metadata"])

    # Purpose: Kiểm config được restore trước workload phụ thuộc.
    # Syntax: lambda tạo hàm ngắn tại chỗ; closure dùng biến từ hàm/lớp bao ngoài.
    # Flow: Dựng input/fault riêng → self.tx.rollback; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertEqual so hai giá trị; assertTrue yêu cầu đúng.
    def test_rollback_restores_config_before_workload(self):
        workload = copy.deepcopy(self.action)
        workload.update({"kind": "Deployment", "name": "app"})
        self.journal.data["actions"].append(workload)
        calls = []
        self.tx.restore = lambda action: calls.append(action["kind"])
        self.assertTrue(self.tx.rollback())
        self.assertEqual(calls, ["ConfigMap", "Deployment"])

    # Purpose: Kiểm config conflict chặn restore workload phụ thuộc để tránh trạng thái hỏng.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → self.tx.rollback; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertEqual so hai giá trị; assertFalse yêu cầu sai.
    def test_config_conflict_blocks_dependent_workload_restore(self):
        workload = copy.deepcopy(self.action)
        workload.update({"kind": "Deployment", "name": "app"})
        self.journal.data["actions"].append(workload)
        calls = []
        # Purpose: Inject lỗi config để kiểm chặn workload phụ thuộc.
        # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
        # Flow: Ghi kind đã được gọi → raise ROLLBACK_CONFLICT ngay.
        # Kiến thức liên quan: Closure dùng calls ở test ngoài; gán tx.restore thay hành vi thật trong test này.
        def conflict(action):
            calls.append(action["kind"])
            raise Error("ROLLBACK_CONFLICT", "R02", action["name"], "other owner")
        self.tx.restore = conflict
        self.assertFalse(self.tx.rollback())
        self.assertEqual(calls, ["ConfigMap"])


# Purpose: Tạo span giả cho test graph propagation.
# Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
# Flow: service/sid/parent/kind → dict span trace=a×32; attrs/links thiếu thì default rỗng.
# Kiến thức liên quan: SpanKind và parent/links quyết định graph_gaps có đủ bằng chứng không.
def span(service, sid, parent="", kind=2, attrs=None, links=None):
    return {"service": service, "sdk": "opentelemetry", "id": sid, "parent": parent, "kind": kind,
            "trace": "a" * 32, "attrs": attrs or {}, "links": links or []}


class BehaviourTests(unittest.TestCase):
    # Purpose: Kiểm trace Envoy không thay bằng chứng instrumentation của app.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → graph_gaps; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertEqual so hai giá trị.
    def test_proxy_only_trace_cannot_pass_application(self):
        gaps = graph_gaps([span("envoy", "1")], {"services": ["catalog"]}, "a" * 32)
        self.assertEqual(gaps, ["server:catalog"])

    # Purpose: Kiểm HTTP ancestry đi qua proxy vẫn nối đúng caller với receiver.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → graph_gaps; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertTrue yêu cầu đúng; assertFalse yêu cầu sai.
    def test_http_parent_through_proxy(self):
        spans = [span("bff", "1", kind=2), span("bff", "2", "1", 3), span("envoy", "3", "2"), span("catalog", "4", "3")]
        contract = {"services": ["bff", "catalog"], "edges": [{"from": "bff", "to": "catalog", "type": "http"}]}
        self.assertFalse(graph_gaps(spans, contract, "a" * 32))
        spans[-1]["parent"] = "wrong"
        self.assertTrue(graph_gaps(spans, contract, "a" * 32))

    # Purpose: Kiểm AMQP chưa có consumer span không được PASS.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → graph_gaps; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertTrue yêu cầu đúng; assertFalse yêu cầu sai.
    def test_late_consumer_requires_complete_edge(self):
        contract = {"services": ["order"], "edges": [{"from": "order", "to": "catalog", "type": "rabbitmq", "relation": "exact_parent"}]}
        spans = [span("order", "1"), span("order", "2", "1", 4)]
        self.assertTrue(graph_gaps(spans, contract, "a" * 32))
        spans.append(span("catalog", "3", "2", 5))
        self.assertFalse(graph_gaps(spans, contract, "a" * 32))

    # Purpose: Kiểm AMQP consumer span link trỏ đúng producer được chấp nhận.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → graph_gaps; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertFalse yêu cầu sai.
    def test_messaging_link(self):
        contract = {"services": [], "edges": [{"from": "a", "to": "b", "type": "rabbitmq", "relation": "link"}]}
        self.assertFalse(graph_gaps([span("a", "1", kind=4), span("b", "2", kind=5, links=[("a" * 32, "1")])], contract, "a" * 32))

    # Purpose: Kiểm DB span của service khác không thay bằng chứng cần thiết.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → graph_gaps; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertTrue yêu cầu đúng.
    def test_db_span_from_wrong_service_not_enough(self):
        contract = {"services": [], "databases": [{"service": "catalog", "system": "postgresql"}]}
        self.assertTrue(graph_gaps([span("bff", "1", kind=3, attrs={"db.system": "postgresql"})], contract, "a" * 32))

    # Purpose: Kiểm SERVER span cùng service nhưng trace cũ bị loại.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → graph_gaps; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertTrue yêu cầu đúng.
    def test_same_service_wrong_trace_rejected(self):
        self.assertTrue(graph_gaps([span("catalog", "1")], {"services": ["catalog"]}, "b" * 32))

    # Purpose: Kiểm ID hex/base64 được chuẩn hóa và chuỗi sai bị loại.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → ident; kỳ vọng ''.
    # Kiến thức liên quan: assertEqual so hai giá trị.
    def test_ids_hex_and_base64(self):
        import base64
        self.assertEqual(ident(base64.b64encode(bytes.fromhex("a" * 32)).decode()), "a" * 32)
        self.assertEqual(ident("A" * 32), "a" * 32)
        self.assertEqual(ident("invalid"), "")

    # Purpose: Kiểm SQL attribute chưa được lọc gây PRIVACY_FAILED.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → flatten; kỳ vọng 'PRIVACY_FAILED'.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_privacy_processor_required(self):
        payload = {"resourceSpans": [{"scopeSpans": [{"spans": [{"attributes": [{"key": "db.statement", "value": {"stringValue": "secret"}}]}]}]}]}
        with self.assertRaises(Error) as ctx:
            flatten(payload)
        self.assertEqual(ctx.exception.code, "PRIVACY_FAILED")

    # Purpose: Kiểm ID đọc được từ JSON escaped; log không có ID trả None.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → log_ids; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertEqual so hai giá trị.
    def test_escaped_go_log_and_missing_id(self):
        line = json.dumps({"log": json.dumps({"trace_id": "a" * 32, "span_id": "b" * 16})})
        self.assertEqual(log_ids(line), ("a" * 32, "b" * 16))
        self.assertEqual(log_ids("old access log"), (None, None))

    # Purpose: Kiểm workload chưa observed spec mới không được Ready.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → ready; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertTrue yêu cầu đúng; assertFalse yêu cầu sai.
    def test_native_sidecar_ready_gate_observed_generation(self):
        d = {"kind": "Deployment", "metadata": {"generation": 2}, "spec": {"replicas": 1},
             "status": {"observedGeneration": 1, "readyReplicas": 1, "updatedReplicas": 1}}
        self.assertFalse(ready(d))
        d["status"]["observedGeneration"] = 2
        self.assertTrue(ready(d))


class SafetyTests(unittest.TestCase):
    # Purpose: Kiểm CLI thắng env và biến env rỗng không dùng default âm thầm.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → load; kỳ vọng 'cli'.
    # Kiến thức liên quan: patch thay dependency trong test rồi trả lại; assertRaises yêu cầu lỗi chỉ định; assertEqual so hai giá trị.
    def test_config_priority_and_invalid_empty(self):
        with patch.dict(os.environ, {"KUBE_CONTEXT": "env"}):
            self.assertEqual(load(context="cli")["context"], "cli")
        with patch.dict(os.environ, {"KUBE_CONTEXT": ""}):
            with self.assertRaises(Error):
                load()

    # Purpose: Kiểm timeout sai kiểu bị dừng thay vì dùng fallback.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → load; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: patch thay dependency trong test rồi trả lại; assertRaises yêu cầu lỗi chỉ định.
    def test_invalid_type_does_not_fallback(self):
        with patch.dict(os.environ, {"STEP_TIMEOUT_SECONDS": "no"}):
            with self.assertRaises(Error):
                load()

    # Purpose: Kiểm override có tên biến chưa hỗ trợ bị từ chối.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → load; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_unknown_input_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.yaml"
            path.write_text("made_up: true\n")
            with self.assertRaises(Error):
                load(path)

    # Purpose: Kiểm credential trong field override lạ không lọt qua schema.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → load; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_unknown_nested_input_cannot_hide_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.yaml"
            path.write_text("auth:\n  inline_api_key: forbidden\n")
            with self.assertRaises(Error):
                load(path)

    # Purpose: Kiểm Secret/credential literal bị chặn nhưng Secret reference hợp lệ.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → safe_snapshot; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_sensitive_snapshot_never_written(self):
        for value in ({"kind": "Secret"}, {"password": "secret"}, {"url": "amqp://a:secret@host"},
                      {"env": [{"name": "API_TOKEN", "value": "secret"}]}):
            with self.assertRaises(Error):
                safe_snapshot(value)
        self.assertEqual(safe_snapshot({"secretKeyRef": {"name": "credentials", "key": "password"}}),
                         {"secretKeyRef": {"name": "credentials", "key": "password"}})

    # Purpose: Kiểm journal quyền 0600 và đọc lại đúng nội dung.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → atomic; kỳ vọng 384, 'PREPARED'.
    # Kiến thức liên quan: assertEqual so hai giá trị.
    def test_atomic_journal_permissions_and_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "journal.json"
            atomic(path, {"state": "PREPARED"})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(Journal(path).data["state"], "PREPARED")

    # Purpose: Kiểm process thứ hai không lấy được cùng lock local.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi; finally luôn chạy để cleanup, dù nhánh try return hay phát lỗi.
    # Flow: Dựng input/fault riêng → LocalLock; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_local_lock_exclusive(self):
        with tempfile.TemporaryDirectory() as folder:
            first = LocalLock(Path(folder) / "lock")
            try:
                with self.assertRaises(Error):
                    LocalLock(Path(folder) / "lock")
            finally:
                first.close()

    # Purpose: Kiểm API default thêm field không tạo diff giả với subset.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → subset; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertTrue yêu cầu đúng.
    def test_server_defaults_not_false_diff(self):
        self.assertTrue(subset({"spec": {"replicas": 1, "revisionHistoryLimit": 10}}, {"spec": {"replicas": 1}}))

    # Purpose: Kiểm info không phải sre-run không được nhận làm owner.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → operation_id; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertIsNone yêu cầu None.
    def test_wrong_run_operation_id(self):
        self.assertIsNone(operation_id({"info": [{"name": "old-script", "value": "r"}]}))

    # Purpose: Kiểm credential trong JSON annotation bị chặn.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → safe_snapshot; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_nested_json_secret_cannot_enter_journal(self):
        with self.assertRaises(Error):
            safe_snapshot({"annotations": {"last-applied": json.dumps({"password": "secret"})}})

    # Purpose: Kiểm chỉ public scrape YAML được snapshot, auth-bearing config bị từ chối.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → safe_snapshot; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_only_public_generated_scrape_config_journaled(self):
        import base64
        resource = {"kind": "Secret", "metadata": {"name": "scrape"}, "data": {
            "additional-scrape-configs.yaml": base64.b64encode(b"- job_name: tempo\n  static_configs: [{targets: ['tempo:3200']}]\n").decode()}}
        data = managed(resource)
        self.assertEqual(set(data), {"scrape_config"})
        self.assertNotIn("data", data)
        safe_snapshot(data)
        resource["data"]["additional-scrape-configs.yaml"] = base64.b64encode(b"- job_name: auth\n  basic_auth: {username: user, password: forbidden}\n").decode()
        with self.assertRaises(Error):
            managed(resource)

    # Purpose: Kiểm budget DaemonSet bao gồm mọi node và dùng limit thay request.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → surge_mib → memory_mib; kỳ vọng 192, 1024.
    # Kiến thức liên quan: assertEqual so hai giá trị.
    def test_surge_budget_includes_all_daemon_nodes(self):
        action = {"kind": "DaemonSet", "desired": {"spec": {"template": {"spec": {"containers": [
            {"resources": {"requests": {"memory": "32Mi"}, "limits": {"memory": "64Mi"}}}]}}}}}
        self.assertEqual(surge_mib(action, 3), 192)
        self.assertEqual(memory_mib("1Gi"), 1024)


class RuntimeRegressionTests(unittest.TestCase):
    # Purpose: Kiểm admin token được refresh khi hết TTL trước cleanup.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → app.admin_ready; kỳ vọng 1, 2.
    # Kiến thức liên quan: patch thay dependency trong test rồi trả lại; assertEqual so hai giá trị.
    def test_expired_admin_token_is_refreshed_before_cleanup(self):
        app = Application.__new__(Application)
        app.c = {"auth": {"namespace": "ns", "service": "keycloak", "port": 80, "secret": "ref",
                           "username_key": "user", "password_key": "pass", "realm": "test"}}
        app.k, app.f, app.admin = Mock(), Mock(), Mock()
        app.admin_base, app.admin_deadline = "http://127.0.0.1:1000", 0
        app.admin.request.return_value = {"access_token": "not-logged", "expires_in": 60}
        with patch("sre_observability.application.secret", return_value={"user": "name", "pass": "not-logged"}):
            app.admin_ready()
            app.admin_ready()
            self.assertEqual(app.admin.request.call_count, 1)
            app.admin_deadline = 0
            app.admin_ready()
            self.assertEqual(app.admin.request.call_count, 2)
        app.f.open.assert_not_called()

    # Purpose: Kiểm POST timeout chỉ gửi một lần để tránh tạo trùng dữ liệu.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → request; kỳ vọng 1.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_post_timeout_never_blindly_retried(self):
        import urllib.error
        opener = Mock()
        opener.open.side_effect = urllib.error.URLError("network")
        with self.assertRaises(Error):
            HTTP(opener=opener).request("http://test/orders", "POST", {})
        self.assertEqual(opener.open.call_count, 1)

    # Purpose: Kiểm metric vắng mặt là None/error theo required, không phải zero.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → verifier.scalar; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_absent_metric_not_coerced_to_zero(self):
        verifier = Verify.__new__(Verify)
        verifier.prom = Mock(return_value=[])
        self.assertIsNone(verifier.scalar("metric", required=False))
        with self.assertRaises(Error):
            verifier.scalar("metric", required=True)

    # Purpose: Kiểm log istio-proxy không thay app log có exported span ID.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → verifier.logs; kỳ vọng 'LOG_CORRELATION_MISSING'.
    # Kiến thức liên quan: patch thay dependency trong test rồi trả lại; assertRaises yêu cầu lỗi chỉ định; assertEqual so hai giá trị.
    def test_proxy_log_cannot_satisfy_application_log(self):
        verifier = Verify.__new__(Verify)
        verifier.c, verifier.k, verifier.http = {"telemetry_wait": 1}, Mock(), Mock()
        verifier.k.runner.deadline.remaining.return_value = 1
        verifier.urls, verifier.auth = {"grafana": "http://test"}, {}
        verifier.http.get.return_value = {"jsonData": {"derivedFields": [{"datasourceUid": "tempo", "matcherRegex": "trace_id[^a-f0-9]+([a-f0-9]{32})"}]}}
        verifier.proxy = Mock(return_value={"data": {"result": [{"stream": {"kubernetes_container_name": "istio-proxy"},
                        "values": [["1", json.dumps({"trace_id": "a" * 32, "span_id": "b" * 16})]]}]}})
        with patch("sre_observability.telemetry.time.monotonic", side_effect=[0, 0, 2]), patch("sre_observability.telemetry.time.sleep"):
            with self.assertRaises(Error) as ctx:
                verifier.logs("a" * 32, [span("app", "b" * 16)], {"logs": ["app"]}, 0)
        self.assertEqual(ctx.exception.code, "LOG_CORRELATION_MISSING")

    # Purpose: Kiểm chuỗi false không âm thầm tắt boolean gate.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → load; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_invalid_nested_boolean_cannot_disable_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.yaml"
            path.write_text('notification_required: "false"\n')
            with self.assertRaises(Error):
                load(path)


class ArgoApiIntegrationTests(unittest.TestCase):
    # Purpose: Kiểm token batch mới không nhận Succeeded của operation cũ.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → self.exercise; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: unittest chạy mỗi test độc lập; assertion kiểm manifest/state thực tế, không chỉ việc hàm được gọi.
    def test_new_token_does_not_accept_old_succeeded_operation(self):
        self.exercise(False)

    # Purpose: Kiểm Argo sync failed vẫn restore resource đã bị ghi trước đó.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → self.exercise; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: unittest chạy mỗi test độc lập; assertion kiểm manifest/state thực tế, không chỉ việc hàm được gọi.
    def test_partial_failed_sync_rolls_back_prior_write(self):
        self.exercise(True)

    # Purpose: Mô phỏng Argo ghi resource rồi trả status cũ/mới hoặc failed.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Tạo journal/action → fake operation token cũ rồi token mới → sync; fail=True → rollback và kiểm old.
    # Kiến thức liên quan: unittest.mock.patch thay source_app/time.sleep; test không chạy Argo controller thật.
    def exercise(self, fail):
        with tempfile.TemporaryDirectory() as folder:
            action = {"app": "app", "kind": "ConfigMap", "name": "cfg", "namespace": "ns", "apiVersion": "v1",
                      "uid": "same", "before": {"data": {"endpoint": "old"}}, "desired": {"data": {"endpoint": "new"}}, "state": "PLANNED"}
            journal = Journal(Path(folder) / "journal.json", {"run_id": "run", "revision": "rev", "actions": [action]})
            testcase = self
            class Argo(FakeKube):
                # Purpose: Khởi tạo fake Argo cho tình huống sync nhiều poll.
                # Syntax: a,b = ... unpack và gán nhiều giá trị theo thứ tự; số phần tử phải khớp.
                # Flow: FakeKube old → mock deadline → operation=None, polls=0.
                # Kiến thức liên quan: super khởi tạo API giả; Mock tránh dùng deadline hoặc cluster thật.
                def __init__(self):
                    super().__init__(obj())
                    self.runner, self.operation, self.polls = Mock(), None, 0
                    self.runner.deadline.remaining.return_value = 30
                # Purpose: Kiểm intent đã lưu trước khi fake Argo thay live data.
                # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
                # Flow: Patch resource → FakeKube; patch Application → đọc journal, assert PREPARED, lưu operation và đổi data new.
                # Kiến thức liên quan: Write-ahead journal được đọc lại từ đĩa; closure giữ testcase để gọi assertion.
                def patch(self, kind, name, namespace, changes):
                    if kind != "application":
                        return super().patch(kind, name, namespace, changes)
                    stored = Journal(journal.path).data
                    testcase.assertEqual(stored["actions"][0]["state"], "PREPARED")
                    testcase.assertEqual(stored["operations"]["app"]["state"], "PREPARED")
                    self.operation = changes[-1]["value"]
                    testcase.assertIn("ClientSideApplyMigration=true", self.operation["sync"]["syncOptions"])
                    testcase.assertIn("Replace=false", self.operation["sync"]["syncOptions"])
                    self.current["data"] = {"endpoint": "new"}
                # Purpose: Trả operation cũ ở poll đầu rồi operation đúng token.
                # Syntax: X if C else Y chọn X khi điều kiện C đúng, còn lại dùng Y (fallback).
                # Flow: Không phải application → FakeKube; poll1 → old-token Succeeded; poll sau → Failed/Succeeded của operation mới.
                # Kiến thức liên quan: Operation token phân biệt các batch; closure fail điều khiển tình huống lỗi.
                def get(self, kind, name=None, namespace=None, optional=False):
                    if kind != "application":
                        return super().get(kind, name, namespace, optional)
                    self.polls += 1
                    if self.polls == 1:
                        return {"operation": self.operation, "status": {"operationState": {"phase": "Succeeded", "operation": {
                            "info": [{"name": "sre-run", "value": "run"}, {"name": "sre-operation", "value": "old-token"}]}}}}
                    return {"status": {"operationState": {"phase": "Failed" if fail else "Succeeded", "operation": self.operation,
                                                         "syncResult": {"revisions": ["rev", "rev"]}}}}
            kube = Argo()
            tx = Transaction({"argo_namespace": "argocd", "step_timeout": 30}, kube, journal)
            with patch("sre_observability.transaction.source_app", return_value={"metadata": {"resourceVersion": "1"}}), patch("sre_observability.transaction.time.sleep"):
                if fail:
                    with self.assertRaises(Error) as ctx:
                        tx.sync("app", [action])
                    self.assertEqual(ctx.exception.code, "ARGO_SYNC_FAILED")
                    self.assertTrue(tx.rollback())
                    self.assertEqual(kube.current["data"]["endpoint"], "old")
                else:
                    tx.sync("app", [action])
                    self.assertEqual(action["state"], "APPLIED")
                    self.assertEqual(journal.data["operations"]["app"]["state"], "SUCCEEDED")
                    self.assertGreaterEqual(kube.polls, 2)


if __name__ == "__main__":
    unittest.main()
