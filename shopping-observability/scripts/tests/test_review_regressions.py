"""Regression cases from the SRE review: API faults remain offline and isolated."""
import copy
import json
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sre_observability.application import Application, GatewayHandler, GatewayRedirect
from sre_observability.cli import collector_window, coverage_summary, main, recover_baseline, route_baseline
from sre_observability.config import fingerprint, load, validate_contract
from sre_observability.core import BackendRedirect, Error, Forwards, Journal, Kube, Runner, safe_snapshot
from sre_observability.inventory import (action_matches, declarations, desired_matches,
                                        build_plan, cache_proofs, eligible_nodes, image_ref, managed, pvc_identity,
                                        ready, source_app, surge_mib, wait_workload)
from sre_observability.telemetry import Verify, graph_gaps
from sre_observability.transaction import Transaction
from test_sre import FakeKube


class ReviewRegressionTests(unittest.TestCase):
    # Purpose: Tạo baseline/PVC/journal tạm riêng cho từng regression test.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Temp folder → đăng ký cleanup → PVC a/b → journal test với context giả.
    # Kiến thức liên quan: addCleanup luôn dọn thư mục; không dùng workload/Secret thật.
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pvcs = [{"namespace": "ns", "name": "b", "uid": "2", "volume": "pv-b"},
                     {"namespace": "ns", "name": "a", "uid": "1", "volume": "pv-a"}]
        self.baseline = {"cluster_uid": "cluster", "pvcs": self.pvcs}
        self.journal = Journal(Path(self.temp.name) / "journal.json",
                               {"run_id": "a" * 32, "actions": [], "baseline": self.baseline,
                                "config": {"context": "test", "obs_namespace": "ns", "rollback_timeout": 10}})

    # Purpose: Kiểm đổi thứ tự PVC không gây lỗi; đổi UID/volume vẫn bị phát hiện.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → pvc_identity; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertEqual so hai giá trị; assertNotEqual yêu cầu khác nhau.
    def test_pvc_reordering_passes_but_replacement_fails(self):
        self.assertEqual(pvc_identity(self.pvcs), pvc_identity(self.pvcs[::-1]))
        for key in ("uid", "volume"):
            changed = copy.deepcopy(self.pvcs)
            changed[0][key] = "other"
            self.assertNotEqual(pvc_identity(self.pvcs), pvc_identity(changed))

    # Purpose: Kiểm recover restore trước cleanup rồi mới xác nhận business baseline.
    # Syntax: lambda tạo hàm ngắn tại chỗ; closure dùng biến từ hàm/lớp bao ngoài; with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → recover_baseline; kỳ vọng 'ROLLED_BACK'.
    # Kiến thức liên quan: patch thay dependency trong test rồi trả lại; assertEqual so hai giá trị; assertTrue yêu cầu đúng.
    def test_recovery_restores_before_cleanup_and_baseline(self):
        events, tx, app = [], Mock(), Mock()
        tx.rollback.side_effect = lambda: events.append("restore") or True
        app.cleanup.side_effect = lambda: events.append("cleanup")
        app.public_baseline.side_effect = lambda: events.append("business")
        with patch("sre_observability.cli.Application", return_value=app), patch("sre_observability.cli.inspect", return_value=self.baseline):
            self.assertTrue(recover_baseline({}, Mock(), Mock(), self.journal, tx))
        self.assertEqual(events, ["restore", "cleanup", "business"])
        self.assertEqual(self.journal.data["state"], "ROLLED_BACK")

    # Purpose: Kiểm cleanup/HTTP recovery lỗi thì state vẫn INCOMPLETE trên đĩa.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → recover_baseline; kỳ vọng 'ROLLBACK_INCOMPLETE'.
    # Kiến thức liên quan: patch thay dependency trong test rồi trả lại; assertEqual so hai giá trị; assertFalse yêu cầu sai.
    def test_failed_business_or_cleanup_keeps_incomplete_state(self):
        for step in ("cleanup", "public_baseline"):
            tx, app = Mock(), Mock()
            tx.rollback.return_value = True
            getattr(app, step).side_effect = Error("HTTP_UNREACHABLE", "R04", step, "offline")
            with patch("sre_observability.cli.Application", return_value=app):
                self.assertFalse(recover_baseline({}, Mock(), Mock(), self.journal, tx))
            self.assertEqual(Journal(self.journal.path).data["state"], "ROLLBACK_INCOMPLETE")

    # Purpose: Kiểm resource restore xong nhưng PVC bị thay không được full rollback PASS.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → recover_baseline; kỳ vọng 'ROLLBACK_INCOMPLETE'.
    # Kiến thức liên quan: patch thay dependency trong test rồi trả lại; assertEqual so hai giá trị; assertFalse yêu cầu sai.
    def test_recovery_storage_mismatch_fails_after_restore(self):
        tx = Mock()
        tx.rollback.return_value = True
        baseline = copy.deepcopy(self.baseline)
        baseline["pvcs"][0]["uid"] = "replacement"
        with patch("sre_observability.cli.Application"), patch("sre_observability.cli.inspect", return_value=baseline):
            self.assertFalse(recover_baseline({}, Mock(), Mock(), self.journal, tx))
        self.assertEqual(self.journal.data["state"], "ROLLBACK_INCOMPLETE")

    # Purpose: Kiểm CLI recover trả exit 5 và giữ Lease khi baseline còn lỗi.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → main; kỳ vọng 5, 'ROLLBACK_INCOMPLETE'.
    # Kiến thức liên quan: patch thay dependency trong test rồi trả lại; assertEqual so hai giá trị.
    def test_recovery_main_exit_five_retains_lease_on_failed_baseline(self):
        config = {"context": "test", "log_dir": self.temp.name, "timeout": 10}
        self.journal.data["lease"] = {"state": "ACQUIRED"}
        self.journal.save()
        kube, lease = Mock(), Mock()
        kube.get.return_value = {"metadata": {"uid": "cluster"}}
        with patch("sre_observability.cli.load", return_value=config), patch("sre_observability.cli.path_for", return_value=self.journal.path), \
             patch("sre_observability.cli.Kube", return_value=kube), patch("sre_observability.cli.Lease", return_value=lease), \
             patch("sre_observability.cli.Application") as app, patch("sre_observability.cli.Transaction") as tx, \
             patch("sre_observability.cli.install_signals"), patch("sre_observability.cli.print"):
            tx.return_value.rollback.return_value = True
            app.return_value.public_baseline.side_effect = Error("HTTP_UNREACHABLE", "R04", "app", "offline")
            self.assertEqual(main(["recover", "--run-id", "a" * 32]), 5)
        lease.close.assert_called_once_with(retain=True)
        self.assertEqual(Journal(self.journal.path).data["state"], "ROLLBACK_INCOMPLETE")

    # Purpose: Kiểm spec đã về baseline nhưng workload unready vẫn phải chờ và báo lỗi.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → restore; kỳ vọng 'RESTORED'.
    # Kiến thức liên quan: patch thay dependency trong test rồi trả lại; assertRaises yêu cầu lỗi chỉ định; assertNotEqual yêu cầu khác nhau.
    def test_idempotent_restore_still_waits_for_unready_workload(self):
        live = {"kind": "Deployment", "metadata": {"uid": "same"}, "spec": {"replicas": 1}}
        action = {"kind": "Deployment", "name": "app", "namespace": "ns", "uid": "same", "before": managed(live)}
        kube = Mock()
        kube.get.return_value = live
        with patch("sre_observability.transaction.wait_workload", side_effect=Error("ROLLOUT_TIMEOUT", "S07", "app", "unready")) as wait:
            with self.assertRaises(Error):
                Transaction({"step_timeout": 1}, kube, self.journal).restore(action)
            wait.assert_called_once()
        self.assertNotEqual(action.get("state"), "RESTORED")
        kube.patch.assert_not_called()

    # Purpose: Kiểm CR cần operator generation, child owner/revision và readiness cùng đạt.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → wait_workload; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: patch thay dependency trong test rồi trả lại; assertRaises yêu cầu lỗi chỉ định.
    def test_operator_generation_and_child_revision_both_required(self):
        cr = {"kind": "Prometheus", "metadata": {"generation": 2, "uid": "cr"},
              "status": {"conditions": [{"type": "Reconciled", "status": "True", "observedGeneration": 1}]}}
        child = {"kind": "StatefulSet", "metadata": {"generation": 2, "ownerReferences": [{"uid": "cr"}]},
                 "spec": {"replicas": 1}, "status": {"observedGeneration": 2, "readyReplicas": 1,
                 "updatedReplicas": 1, "currentRevision": "old", "updateRevision": "new"}}
        action = {"kind": "Prometheus", "name": "test", "namespace": "ns"}
        for incomplete in ("operator", "revision", "readiness", "owner"):
            candidate = copy.deepcopy(cr)
            stateful = copy.deepcopy(child)
            candidate["status"]["conditions"][0]["observedGeneration"] = 1 if incomplete == "operator" else 2
            stateful["status"]["currentRevision"] = "old" if incomplete == "revision" else "new"
            if incomplete == "readiness":
                stateful["status"]["readyReplicas"] = 0
            if incomplete == "owner":
                stateful["metadata"]["ownerReferences"] = []
            kube = Mock()
            kube.runner.deadline.remaining.return_value = 1
            kube.get.side_effect = [candidate, stateful]
            with patch("sre_observability.inventory.time.monotonic", side_effect=[0, 0, 2]), patch("sre_observability.inventory.time.sleep"):
                with self.assertRaises(Error):
                    wait_workload(kube, action, 1)
        cr["status"]["conditions"][0]["observedGeneration"] = 2
        child["status"]["currentRevision"] = "new"
        kube.get.side_effect = [cr, child]
        with patch("sre_observability.inventory.time.monotonic", side_effect=[0, 0]):
            wait_workload(kube, action, 1)

    # Purpose: Kiểm xóa ConfigMap key cũng là diff cần deploy.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → desired_matches; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertFalse yêu cầu sai.
    def test_deleted_configmap_key_is_a_change(self):
        live = {"kind": "ConfigMap", "metadata": {}, "data": {"A": "1", "B": "2"}}
        target = {"kind": "ConfigMap", "metadata": {}, "data": {"A": "1"}}
        self.assertFalse(desired_matches(live, target))
        self.assertFalse(action_matches(live, {"kind": "ConfigMap", "desired": managed(target)}))

    # Purpose: Kiểm xóa field spec/annotation thuộc Argo được phát hiện, API default được bỏ qua.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → desired_matches → declarations; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertTrue yêu cầu đúng; assertFalse yêu cầu sai.
    def test_owned_removed_spec_and_annotations_detected_defaults_ignored(self):
        live = {"kind": "Deployment", "metadata": {"annotations": {"owned": "old"}, "managedFields": [
            {"manager": "argocd-controller", "fieldsV1": {"f:spec": {"f:replicas": {}},
             "f:metadata": {"f:annotations": {"f:owned": {}}}}}]}, "spec": {"replicas": 2, "revisionHistoryLimit": 10}}
        target = {"kind": "Deployment", "metadata": {}, "spec": {}}
        self.assertFalse(desired_matches(live, target, declarations(live)))
        target["spec"]["replicas"] = 2
        target["metadata"]["annotations"] = {"owned": "old"}
        self.assertTrue(desired_matches(live, target, declarations(live)))

    # Purpose: Kiểm removal trong named container list được phát hiện từ last-applied.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới. **mapping unpack các key/value vào dict mới.
    # Flow: Dựng input/fault riêng → desired_matches → declarations; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertFalse yêu cầu sai.
    def test_last_applied_named_container_field_removal(self):
        previous = {"spec": {"template": {"spec": {"containers": [{"name": "app", "args": ["old"]}]}}}}
        live = {"kind": "Deployment", "metadata": {"annotations": {"kubectl.kubernetes.io/last-applied-configuration": json.dumps(previous)}}, **previous}
        target = copy.deepcopy(live)
        del target["spec"]["template"]["spec"]["containers"][0]["args"]
        self.assertFalse(desired_matches(live, target, declarations(live)))

    # Purpose: Tạo manifest workload giả cho test RAM strategy.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: replicas=3,maxSurge=50% → Deployment container request32Mi/limit100Mi.
    # Kiến thức liên quan: surge_mib phải dùng limit và rollout strategy của action này.
    def memory_action(self, kind="Deployment", replicas=3, surge="50%"):
        return {"kind": kind, "desired": {"spec": {"replicas": replicas,
            "strategy": {"rollingUpdate": {"maxSurge": surge}},
            "template": {"spec": {"containers": [{"name": "app", "resources": {
                "requests": {"memory": "32Mi"}, "limits": {"memory": "100Mi"}}}]}}}}}

    # Purpose: Kiểm budget replica/maxSurge phần trăm/số nguyên và strategy Recreate.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → surge_mib; kỳ vọng 500, 400, 300.
    # Kiến thức liên quan: assertEqual so hai giá trị.
    def test_surge_percentage_integer_and_recreate(self):
        action = self.memory_action()
        self.assertEqual(surge_mib(action, 3), 500)
        action["desired"]["spec"]["strategy"]["rollingUpdate"]["maxSurge"] = 1
        self.assertEqual(surge_mib(action, 3), 400)
        action["desired"]["spec"]["strategy"] = {"type": "Recreate"}
        self.assertEqual(surge_mib(action, 3), 300)

    # Purpose: Kiểm init sidecar chạy đồng thời và admission budget đều được cộng RAM.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → surge_mib; kỳ vọng 275.
    # Kiến thức liên quan: assertEqual so hai giá trị.
    def test_native_sidecar_and_injected_budget_counted(self):
        action = self.memory_action(replicas=1, surge=0)
        action["desired"]["spec"]["template"]["spec"]["initContainers"] = [
            {"name": "sidecar", "restartPolicy": "Always", "resources": {"limits": {"memory": "50Mi"}}},
            {"name": "init", "resources": {"limits": {"memory": "200Mi"}}}]
        action["admission_memory_mib"] = 25
        self.assertEqual(surge_mib(action, 1), 275)

    # Purpose: Kiểm chỉ có request không đủ để kết luận RAM rollout an toàn.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → surge_mib; kỳ vọng 'CAPACITY_UNKNOWN'.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_requests_without_limit_do_not_claim_capacity(self):
        action = self.memory_action()
        del action["desired"]["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]
        with self.assertRaises(Error) as caught:
            surge_mib(action, 1)
        self.assertEqual(caught.exception.code, "CAPACITY_UNKNOWN")
        for value in ("0", "0Mi"):
            action = self.memory_action()
            action["desired"]["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]["memory"] = value
            with self.assertRaises(Error) as caught:
                surge_mib(action, 1)
            self.assertEqual(caught.exception.code, "CAPACITY_UNKNOWN")

    # Purpose: Kiểm URL HTTPS/host/port/userinfo sai bị chặn trước gửi credential lên mạng.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → opener.open; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: patch thay dependency trong test rồi trả lại; assertRaises yêu cầu lỗi chỉ định; assertIs kiểm cùng object.
    def test_https_and_wrong_host_port_block_before_network(self):
        handler = GatewayHandler(12345, ["shop", "auth"], [80, 8080])
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), handler)
        with patch("sre_observability.application.socket.create_connection") as connect:
            for url in ("https://evil/login", "https://auth/login", "http://evil/login", "http://shop:9999/login", "http://u:p@shop/login"):
                with self.assertRaises(Error):
                    opener.open(urllib.request.Request(url, data=b"password=fake"))
            connect.assert_not_called()
        request = urllib.request.Request("http://auth:8080/login", data=b"fake")
        self.assertIs(handler.http_request(request), request)

    # Purpose: Kiểm redirect sang origin khác bỏ Authorization và Cookie.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → urllib.request.Request → redirect_request; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertIsNone yêu cầu None.
    def test_cross_origin_redirect_strips_credentials(self):
        request = urllib.request.Request("http://shop/login", headers={"Authorization": "Bearer fake", "Cookie": "fake=1"})
        redirected = GatewayRedirect().redirect_request(request, None, 302, "", {}, "http://auth/login")
        self.assertIsNone(redirected.get_header("Authorization"))
        self.assertIsNone(redirected.get_header("Cookie"))

    # Purpose: Kiểm API_KEY/client_secret/nested YAML/JSON bị từ chối trước tạo journal.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → safe_snapshot; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_sensitive_variants_refused_before_disk_write(self):
        for payload in ({"api_key": "fake"}, {"client_secret": "fake"}, {"env": [{"name": "API_KEY", "value": "fake"}]},
                        {"data": {"settings": "nested: {api_key: fake}"}},
                        {"metadata": {"annotations": {"config": '{"client_secret":"fake"}'}}}):
            path = Path(self.temp.name) / "unsafe.json"
            with self.assertRaises(Error):
                Journal(path, payload)
            self.assertFalse(path.exists())
        safe_snapshot({"env": [{"name": "API_KEY", "valueFrom": {"secretKeyRef": {"name": "ref", "key": "api_key"}}}]})

    # Purpose: Kiểm image alias chuẩn Docker Hub và latest ngầm bị chặn.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → image_ref; kỳ vọng 'docker.io/library/redis:7', 'docker.io/team/app:v1', 'quay.io/team/app:v1'.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_image_normalization_and_implicit_latest_rejection(self):
        self.assertEqual(image_ref("redis:7"), "docker.io/library/redis:7")
        self.assertEqual(image_ref("team/app:v1"), "docker.io/team/app:v1")
        self.assertEqual(image_ref("quay.io/team/app:v1"), "quay.io/team/app:v1")
        self.assertEqual(image_ref("redis:7@sha256:" + "a" * 64), "docker.io/library/redis@sha256:" + "a" * 64)
        for image in ("redis", "team/app", "redis:latest"):
            with self.assertRaises(Error):
                image_ref(image)

    # Purpose: Kiểm image preflight bỏ node sai selector hoặc đã cordon.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Dựng input/fault riêng → eligible_nodes; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertEqual so hai giá trị.
    def test_image_checks_only_eligible_nodes(self):
        nodes = [{"metadata": {"name": "a", "labels": {"pool": "app"}}, "spec": {}},
                 {"metadata": {"name": "b", "labels": {"pool": "other"}}, "spec": {}},
                 {"metadata": {"name": "c", "labels": {"pool": "app"}}, "spec": {"unschedulable": True}}]
        self.assertEqual([n["metadata"]["name"] for n in eligible_nodes(nodes, {"nodeSelector": {"pool": "app"}})], ["a"])

    # Purpose: Kiểm contract thiếu checkout/trùng ID/sai kiểu/edge/logs bị loại trước fixture.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → load → validate_contract; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_invalid_contract_rejected_without_fixture_writes(self):
        original = load()["contract_data"]
        for change in ("checkout", "duplicate", "status", "boolean", "edge", "logs"):
            contract = copy.deepcopy(original)
            if change == "checkout":
                del contract["checkout"]
            elif change == "duplicate":
                contract["routes"][1]["id"] = contract["routes"][0]["id"]
            elif change == "status":
                contract["routes"][0]["expected"] = [True]
            elif change == "boolean":
                contract["routes"][0]["authenticated"] = "false"
            elif change == "edge":
                contract["routes"][1]["edges"][0]["to"] = "unknown"
            else:
                contract["routes"][1]["logs"] = []
            with self.assertRaises(Error):
                validate_contract(contract)

    # Purpose: Kiểm report giữ logs PASS khi chỉ metric lỗi và không bịa Redis/Rabbit PASS.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → coverage_summary; kỳ vọng 'PASS', 'FAIL', 'NOT_DECLARED'.
    # Kiến thức liên quan: assertEqual so hai giá trị.
    def test_metrics_failure_does_not_mark_good_logs_failed(self):
        contract = {"routes": [{"id": "a"}], "checkout": {"id": "b"}}
        self.journal.data.update({"coverage": {}, "signal_results": {
            "a": {"trace": "PASS", "logs": "PASS", "metrics": "FAIL"},
            "b": {"trace": "PASS", "logs": "PASS", "metrics": "PASS"}}})
        coverage_summary(self.journal, contract)
        self.assertEqual(self.journal.data["coverage"]["logs"], "PASS")
        self.assertEqual(self.journal.data["coverage"]["mesh_metrics"], "FAIL")
        self.assertEqual(self.journal.data["coverage"]["redis"], "NOT_DECLARED")
        self.assertEqual(self.journal.data["coverage"]["rabbitmq"], "NOT_DECLARED")

    # Purpose: Kiểm DB span trace cũ không chứng minh Redis của request mới.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → graph_gaps; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertTrue yêu cầu đúng.
    def test_wrong_trace_db_or_http_never_satisfies_graph(self):
        spans = [{"service": "app", "trace": "old", "id": "1", "kind": 3, "attrs": {"db.system": "redis"}}]
        self.assertTrue(graph_gaps(spans, {"services": [], "databases": [{"service": "app", "system": "redis"}]}, "new"))

    # Purpose: Kiểm tuổi scrape thực được xét dù timestamp query mới.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → verifier.counter; kỳ vọng 'METRIC_STALE'.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_stale_scrape_rejected_even_with_fresh_query_timestamp(self):
        verifier = Verify.__new__(Verify)
        verifier.service_namespace = Mock(return_value="ns")
        verifier.scalar = Mock(return_value=120)
        with self.assertRaises(Error) as caught:
            verifier.counter("app")
        self.assertEqual(caught.exception.code, "METRIC_STALE")

    # Purpose: Kiểm lỗi permission có mã RBAC_DENIED và không lộ stderr nhạy cảm.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → runner.run; kỳ vọng 'RBAC_DENIED'.
    # Kiến thức liên quan: patch thay dependency trong test rồi trả lại; assertRaises yêu cầu lỗi chỉ định; assertEqual so hai giá trị.
    def test_runner_error_is_specific_without_raw_stderr(self):
        runner = Runner()
        result = subprocess.CompletedProcess(["kubectl"], 1, "", "Forbidden: fake-sensitive-value")
        with patch("sre_observability.core.subprocess.run", return_value=result):
            with self.assertRaises(Error) as caught:
                runner.run(["kubectl"])
        self.assertEqual(caught.exception.code, "RBAC_DENIED")
        self.assertNotIn("fake-sensitive-value", str(caught.exception))

    # Purpose: Kiểm mở cùng Service tái dùng tunnel sống thay vì tạo thêm process.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → forwards.open; kỳ vọng 'http://127.0.0.1:1000'.
    # Kiến thức liên quan: patch thay dependency trong test rồi trả lại; assertEqual so hai giá trị.
    def test_forward_reuses_healthy_owned_process(self):
        forwards = Forwards(Mock(), self.temp.name)
        process = Mock()
        process.poll.return_value = None
        forwards.cache[("ns", "service", 80)] = (process, "http://127.0.0.1:1000")
        with patch("sre_observability.core.subprocess.Popen") as create:
            self.assertEqual(forwards.open("ns", "service", 80), "http://127.0.0.1:1000")
            create.assert_not_called()

    # Purpose: Tạo Application fake để inject fixture/API response.
    # Syntax: a,b = ... unpack và gán nhiều giá trị theo thứ tự; số phần tử phải khớp.
    # Flow: Không chạy constructor network → gán fixture/journal/mock HTTP/API và authenticate.
    # Kiến thức liên quan: __new__ tạo instance chưa gọi __init__; Mock giữ test hoàn toàn offline.
    def fixture_app(self, fixture):
        app = Application.__new__(Application)
        app.fixture = fixture
        app.j, app.http, app.api = self.journal, Mock(), Mock()
        app.base = "http://shop"
        app.authenticate = Mock()
        return app

    # Purpose: Kiểm product POST mất response vẫn được tìm đúng SKU ở page sau.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → app.find_product; kỳ vọng 'owned'.
    # Kiến thức liên quan: assertEqual so hai giá trị; assertIn kiểm phần tử tồn tại.
    def test_product_lost_response_searches_exact_sku_across_pages(self):
        app = self.fixture_app({"sku": "sre-owned"})
        app.http.get.side_effect = [{"items": [{"sku": "other", "id": "other"}], "pages": 2},
                                    {"items": [{"sku": "sre-owned", "id": "owned"}], "pages": 2}]
        self.assertEqual(app.find_product(), "owned")
        self.assertIn("search=sre-owned", app.http.get.call_args_list[0].args[0])
        self.assertIn("page=2", app.http.get.call_args_list[1].args[0])

    # Purpose: Kiểm thiếu bằng chứng phân trang không được kết luận product đã vắng mặt.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → app.find_product; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_missing_pagination_cannot_claim_product_absent(self):
        app = self.fixture_app({"sku": "sre-owned"})
        app.http.get.return_value = {"items": []}
        with self.assertRaises(Error):
            app.find_product()

    # Purpose: Kiểm user đã xóa nhưng chưa save CLEANED có thể recover từ business evidence.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → app.cleanup; kỳ vọng 'CLEANED'.
    # Kiến thức liên quan: assertEqual so hai giá trị.
    def test_user_delete_lost_response_recovers_from_cleanup_evidence(self):
        app = self.fixture_app({"state": "USER_DELETE_PREPARED", "business_cleaned": True, "sku": "sre-owned", "orders": ["owned"]})
        app.resolve_user = Mock(return_value=None)
        app.cleanup()
        self.assertEqual(app.fixture["state"], "CLEANED")
        app.authenticate.assert_not_called()

    # Purpose: Kiểm user mất trước business cleanup không được báo CLEANED.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → app.cleanup; kỳ vọng 'CLEANED'.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_absent_identity_without_business_evidence_fails(self):
        app = self.fixture_app({"state": "CLEANUP_PREPARED", "sku": "sre-owned", "orders": []})
        app.resolve_user = Mock(return_value=None)
        with self.assertRaises(Error):
            app.cleanup()
        self.assertNotEqual(app.fixture["state"], "CLEANED")

    # Purpose: Tạo plan offline có image cache chuẩn, thiếu hoặc digest conflict.
    # Syntax: lambda tạo hàm ngắn tại chỗ; closure dùng biến từ hàm/lớp bao ngoài; with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Fake Helm/Git/API → node cache old/new + baseline pod → build_plan → plan có proof hoặc blockers.
    # Kiến thức liên quan: Mock chỉ thay boundary Git/Helm/Kubernetes; build_plan thật vẫn chạy ownership/diff/image logic.
    def image_plan(self, missing=False, conflict=False):
        live = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "app", "uid": "same",
                "annotations": {"argocd.argoproj.io/tracking-id": "app:apps/Deployment:ns/app"}},
                "spec": {"selector": {"matchLabels": {"app": "test"}}, "template": {"spec": {"containers": [
                    {"name": "app", "image": "redis:7", "resources": {"limits": {"memory": "100Mi"}}}]}}}}
        target = copy.deepcopy(live)
        target["spec"]["template"]["spec"]["containers"][0]["image"] = "redis:8"
        nodes = []
        for name in ("a", "b"):
            digest = "b" * 64 if conflict and name == "b" else "a" * 64
            nodes.append({"metadata": {"name": name}, "status": {"images": [] if missing else [
                {"names": ["docker.io/library/redis:7", "docker.io/library/redis@sha256:" + "c" * 64]},
                {"names": ["docker.io/library/redis:8", "docker.io/library/redis@sha256:" + digest]}]}})
        kube = Mock()
        kube.can.return_value = True
        kube.get.side_effect = lambda kind, *args, **kwargs: {"items": nodes} if kind == "nodes" else {"items": [
            {"metadata": {"labels": {"app": "test"}}, "spec": live["spec"]["template"]["spec"]}]} if kind == "pods" else live
        kube.runner.run.side_effect = lambda args, **kwargs: json.dumps(target) if args[0] == "helm" else "rev refs/heads/main" if "ls-remote" in args else "rev" if "rev-parse" in args else ""
        config = {"repo_root": self.temp.name, "branch": "main", "argo_namespace": "argocd",
                  "managed_apps": [{"name": "app", "resources": [["Deployment", "app"]]}]}
        source = {"metadata": {}, "spec": {"sources": [{"path": "chart", "helm": {"valueFiles": []}}], "destination": {"namespace": "ns"}}}
        with patch("sre_observability.inventory.source_app", return_value=source):
            return build_plan(config, kube, self.baseline)

    # Purpose: Kiểm thiếu cache proof/digest khác giữa node chặn deploy; đủ proof mới được tiếp tục.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Dựng input/fault riêng → self.image_plan → len; kỳ vọng 'IMAGE_CACHE_UNKNOWN', 4.
    # Kiến thức liên quan: assertEqual so hai giá trị; assertIn kiểm phần tử tồn tại.
    def test_image_cache_unknown_and_digest_conflict_are_blockers(self):
        self.assertEqual(self.image_plan(missing=True)["blocking_reasons"][0]["code"], "IMAGE_CACHE_UNKNOWN")
        self.assertIn("IMAGE_DIGEST_CONFLICT", {row["code"] for row in self.image_plan(conflict=True)["blocking_reasons"]})
        proven = self.image_plan()
        self.assertEqual(proven["blocking_reasons"], [])
        self.assertEqual(len(proven["actions"][0]["image_proofs"]), 4)

    # Purpose: Tạo verifier fake chỉ thay trace/log retrieval để test phân loại metric.
    # Syntax: a,b = ... unpack và gán nhiều giá trị theo thứ tự; số phần tử phải khớp.
    # Flow: Tạo instance không mở tunnel → mock graph/log đã đủ → counter=1, deadline=1.
    # Kiến thức liên quan: __new__/Mock cô lập backend; verify_route thật đánh giá metric và lưu signal_results.
    def verifier_with_complete_trace_logs(self):
        verifier = Verify.__new__(Verify)
        verifier.c, verifier.k, verifier.j = {}, Mock(), self.journal
        verifier.k.runner.deadline.remaining.return_value = 1
        verifier.trace = Mock(return_value=[{"service": "app"}])
        verifier.logs = Mock(return_value={"app": "application log with exported span_id"})
        verifier.counter = Mock(return_value=1)
        return verifier

    # Purpose: Kiểm metric mesh PASS không bị báo thành app metric PASS.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → self.verifier_with_complete_trace_logs → verifier.verify_route; kỳ vọng 'PASS_MESH', 'NOT_DECLARED'.
    # Kiến thức liên quan: assertEqual so hai giá trị.
    def test_mesh_metrics_do_not_claim_application_metrics(self):
        verifier = self.verifier_with_complete_trace_logs()
        proof = verifier.verify_route({"trace_id": "a" * 32, "started": 1}, {"id": "test", "services": ["app"], "logs": ["app"]}, {"app": 0})
        self.assertEqual(proof["metrics"], "PASS_MESH")
        self.assertEqual(proof["application_metrics"], "NOT_DECLARED")

    # Purpose: Kiểm app metric thiếu giữ trace/logs PASS và ghi app metric FAIL riêng.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → self.verifier_with_complete_trace_logs → Error; kỳ vọng 'PASS', 'FAIL'.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_declared_app_metric_missing_preserves_good_trace_logs(self):
        verifier = self.verifier_with_complete_trace_logs()
        verifier.scalar = Mock(side_effect=Error("METRIC_MISSING", "S09", "app", "missing"))
        contract = {"id": "test", "services": ["app"], "logs": ["app"], "application_metrics": [
            {"service": "app", "query": "sum(app_requests_total)", "freshness_query": "time()-min(timestamp(app_requests_total))"}]}
        with self.assertRaises(Error):
            verifier.verify_route({"trace_id": "a" * 32, "started": 1}, contract, {"app": 0, "app:app": 0})
        proof = Journal(self.journal.path).data["signal_results"]["test"]
        self.assertEqual(proof["trace"], "PASS")
        self.assertEqual(proof["logs"], "PASS")
        self.assertEqual(proof["application_metrics"], "FAIL")

    # Purpose: Kiểm enqueue/loss series thiếu còn là None, không biến thành zero.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → Verify.__new__ → verifier.losses; kỳ vọng 100.
    # Kiến thức liên quan: assertEqual so hai giá trị; assertIsNone yêu cầu None.
    def test_missing_collector_loss_series_stays_unknown(self):
        verifier = Verify.__new__(Verify)
        verifier.scalar = Mock(side_effect=[1, 100, 1, 99, None, None, None, None])
        metrics = verifier.losses()
        self.assertEqual(metrics["receiver_accepted_spans"], 100)
        self.assertIsNone(metrics["exporter_enqueue_failed_spans"])

    # Purpose: Kiểm product chưa chứng minh inactive thì không xóa identity cần cho cleanup.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → app.cleanup; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_product_delete_unverified_cannot_remove_test_identity(self):
        app = self.fixture_app({"state": "PRODUCT_CREATED", "product_id": "owned", "sku": "sre-owned", "orders": []})
        app.resolve_user = Mock(return_value="user")
        app.http.request.side_effect = [None, (200, b'{"is_active":true}', {})]
        with self.assertRaises(Error):
            app.cleanup()
        app.api.assert_not_called()
        self.assertFalse(app.fixture.get("business_cleaned"))

    # Purpose: Kiểm logout mất response vẫn giữ business evidence và xóa đúng user test.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → app.cleanup; kỳ vọng 'CLEANED', 'HTTP_UNREACHABLE'.
    # Kiến thức liên quan: assertEqual so hai giá trị; assertTrue yêu cầu đúng.
    def test_logout_failure_does_not_lose_business_cleanup_evidence(self):
        app = self.fixture_app({"state": "PRODUCT_CREATED", "product_id": "owned", "sku": "sre-owned", "orders": []})
        app.resolve_user = Mock(side_effect=["user", None])
        app.http.request.side_effect = [None, (404, b'', {}), Error("HTTP_UNREACHABLE", "R01", "logout", "lost")]
        app.cleanup()
        self.assertEqual(app.fixture["state"], "CLEANED")
        self.assertTrue(app.fixture["business_cleaned"])
        self.assertEqual(app.fixture["logout_warning"], "HTTP_UNREACHABLE")

    # Purpose: Kiểm report phân biệt series thiếu, loss tăng và reset mà không báo zero loss sai.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Dựng input/fault riêng → dict → collector_window; kỳ vọng 'UNKNOWN', 'LOSS_OBSERVED', 'COUNTER_RESET'.
    # Kiến thức liên quan: assertEqual so hai giá trị.
    def test_collector_loss_reset_and_unknown_evidence(self):
        before = {"receiver_accepted_spans": 100, "exporter_send_failed_spans": 0, "exporter_enqueue_failed_spans": None}
        after = dict(before, receiver_accepted_spans=110)
        self.assertEqual(collector_window(before, after)["loss_evidence"], "UNKNOWN")
        after["exporter_send_failed_spans"] = 1
        self.assertEqual(collector_window(before, after)["loss_evidence"], "LOSS_OBSERVED")
        after["receiver_accepted_spans"] = 2
        self.assertEqual(collector_window(before, after)["loss_evidence"], "COUNTER_RESET")

    # Purpose: Kiểm cache tag không được xem là proof khi policy Always có thể pull tag đã đổi.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi.
    # Flow: Dựng input/fault riêng → cache_proofs; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertRaises yêu cầu đúng exception; assertEqual/True/False kiểm output hoặc state sau thao tác.
    def test_always_pull_mutable_tag_not_proven_by_cache(self):
        with self.assertRaises(Error):
            cache_proofs([{"metadata": {"name": "node"}, "status": {"images": []}}],
                         [{"containers": [{"image": "redis:7", "imagePullPolicy": "Always"}]}], "app")

    # Purpose: Kiểm deploy cleanup lỗi được retry sau restore và trả exit 4 khi phục hồi đã đủ.
    # Syntax: with patch thay boundary dependency trong test; hàm lồng dùng journal được truyền để inject fault.
    # Flow: Plan giả → acceptance cleanup lỗi → rollback → cleanup lại → baseline đạt → ROLLED_BACK, nhả Lease.
    # Kiến thức liên quan: main/perform_deploy thật chạy luồng phục hồi; Mock không tác động cluster thật.
    def test_deploy_cleanup_retry_returns_four_and_releases_lease(self):
        config = load(allow_writes=True)
        config.update({"log_dir": self.temp.name, "timeout": 10, "managed_apps": [{"name": "app"}], "obs_app": "app"})
        action = {"app": "app", "kind": "ConfigMap", "name": "cfg", "namespace": "ns", "state": "PLANNED",
                  "desired": {"data": {"endpoint": "new"}}, "before": {"data": {"endpoint": "old"}}, "uid": "same"}
        baseline = dict(self.baseline, mesh_hash="mesh", node_count=1, vm_free_memory_mib=10000)
        plan = {"state": "PLANNED", "run_id": "b" * 32, "config": config, "config_hash": fingerprint(config),
                "created": time.time(), "revision": "rev", "apps": [], "actions": [action], "baseline": baseline,
                "dirty_apps": [], "blocking_reasons": []}
        Journal(Path(self.temp.name) / ("obs-plan-" + "b" * 32 + ".json"), plan)
        kube, lease, app, tx = Mock(), Mock(), Mock(), Mock()
        kube.runner.run.return_value = "rev refs/heads/dev"
        tx.rollback.return_value = True

        # Purpose: Inject acceptance cleanup failure để kiểm compensation retry.
        # Syntax: *args nhận các đối số orchestration; raise đưa lỗi vào nhánh rollback.
        # Flow: Lấy journal của run → lưu cleanup_error → phát CLEANUP_FAILED.
        # Kiến thức liên quan: Journal.save giữ recovery intent trước khi caller bắt Error.
        def failed_acceptance(*args):
            journal = args[3]
            journal.data["cleanup_error"] = {"code": "CLEANUP_FAILED"}
            journal.save()
            raise Error("CLEANUP_FAILED", "S11", "fixtures", "lost response")

        with patch("sre_observability.cli.load", return_value=config), patch("sre_observability.cli.Kube", return_value=kube), \
             patch("sre_observability.cli.inspect", return_value=baseline), patch("sre_observability.cli.build_plan", return_value=plan), \
             patch("sre_observability.cli.Lease", return_value=lease), patch("sre_observability.cli.Transaction", return_value=tx), \
             patch("sre_observability.cli.Application", return_value=app), patch("sre_observability.cli.Verify"), \
             patch("sre_observability.cli.verify_all", side_effect=failed_acceptance), \
             patch("sre_observability.cli.install_signals"), patch("sre_observability.cli.print"):
            self.assertEqual(main(["deploy", "--plan-id", "b" * 32, "--allow-test-writes"]), 4)
        lease.close.assert_called_once_with(retain=False)
        app.cleanup.assert_called_once()
        run = Journal(next(Path(self.temp.name).glob("obs-run-*.json"))).data
        self.assertEqual(run["state"], "ROLLED_BACK")
        self.assertNotIn("cleanup_error", run)

    # Purpose: Kiểm ngắt trong lúc nhả Lease không bị báo rollback đã hoàn tất.
    # Syntax: with patch cô lập CLI; KeyboardInterrupt cần bắt riêng vì không thuộc Exception.
    # Flow: Resource/business/PVC đạt → lease.close bị ngắt → journal INCOMPLETE và exit 5.
    # Kiến thức liên quan: Nhả lock cũng là gate recovery; không dựa chỉ vào tx.rollback trả True.
    def test_interrupted_lease_release_keeps_recovery_incomplete(self):
        config = {"context": "test", "log_dir": self.temp.name, "timeout": 10}
        self.journal.data["lease"] = {"state": "ACQUIRED"}
        self.journal.save()
        kube, lease = Mock(), Mock()
        kube.get.return_value = {"metadata": {"uid": "cluster"}}
        lease.close.side_effect = KeyboardInterrupt()
        with patch("sre_observability.cli.load", return_value=config), patch("sre_observability.cli.path_for", return_value=self.journal.path), \
             patch("sre_observability.cli.Kube", return_value=kube), patch("sre_observability.cli.Lease", return_value=lease), \
             patch("sre_observability.cli.Transaction") as tx, patch("sre_observability.cli.Application"), \
             patch("sre_observability.cli.inspect", return_value=self.baseline), \
             patch("sre_observability.cli.install_signals"), patch("sre_observability.cli.print"):
            tx.return_value.rollback.return_value = True
            self.assertEqual(main(["recover", "--run-id", "a" * 32]), 5)
        self.assertEqual(Journal(self.journal.path).data["state"], "ROLLBACK_INCOMPLETE")

    # Purpose: Kiểm admin/backend credential không theo redirect ra origin khác.
    # Syntax: assertRaises yêu cầu guard phát Error; Request mô phỏng header nhạy cảm nhưng không gửi mạng.
    # Flow: Backend localhost có Authorization → external/HTTPS/port khác → chặn; cùng origin/path mới → cho phép.
    # Kiến thức liên quan: BackendRedirect là default HTTP handler; GatewayRedirect có allowlist OIDC riêng.
    def test_backend_redirect_cannot_forward_credentials_outside_origin(self):
        request = urllib.request.Request("http://127.0.0.1:1000/api", headers={"Authorization": "Bearer fake"})
        for target in ("http://evil/api", "https://127.0.0.1:1000/api", "http://127.0.0.1:2000/api"):
            with self.assertRaises(Error):
                BackendRedirect().redirect_request(request, None, 302, "", {}, target)
        result = BackendRedirect().redirect_request(request, None, 302, "", {}, "http://127.0.0.1:1000/next")
        self.assertEqual(result.full_url, "http://127.0.0.1:1000/next")

    # Purpose: Kiểm query nhiều series hoặc sample sai không được lấy đại phần tử đầu để PASS.
    # Syntax: with assertRaises yêu cầu Error có mã tương ứng; Mock thay response Prometheus.
    # Flow: Hai series → METRIC_AMBIGUOUS; giá trị không phải số → METRIC_INVALID; sample đúng → 2.0.
    # Kiến thức liên quan: Scalar query cần đúng một sample hữu hạn; timestamp query khác với tuổi scrape gốc.
    def test_scalar_rejects_ambiguous_or_malformed_query_result(self):
        verifier = Verify.__new__(Verify)
        row = {"value": [time.time(), "2"]}
        verifier.prom = Mock(return_value=[row, row])
        with self.assertRaises(Error) as caught:
            verifier.scalar("app_counter")
        self.assertEqual(caught.exception.code, "METRIC_AMBIGUOUS")
        verifier.prom.return_value = [{"value": [time.time(), "not-a-number"]}]
        with self.assertRaises(Error) as caught:
            verifier.scalar("app_counter")
        self.assertEqual(caught.exception.code, "METRIC_INVALID")
        verifier.prom.return_value = [row]
        self.assertEqual(verifier.scalar("app_counter"), 2.0)

    # Purpose: Kiểm replica default do API thêm lại không bị coi là field cũ chưa xóa khi SSA đã nhả ownership.
    # Syntax: Không có cú pháp nâng cao; các dict lồng mô phỏng resource và FieldsV1.
    # Flow: SSA đã bỏ sở hữu replicas, API default=1 → đạt; Argo vẫn sở hữu replicas → không đạt.
    # Kiến thức liên quan: Last-applied cũ không còn quyết định ownership khi đã dùng SSA hiện đại.
    def test_released_replica_default_is_not_stale_declared_field(self):
        live = {"kind": "Deployment", "metadata": {"managedFields": [{"manager": "argocd-controller", "operation": "Apply", "fieldsV1": {"f:spec": {"f:template": {}}}}],
                "annotations": {"kubectl.kubernetes.io/last-applied-configuration": '{"spec":{"replicas":3}}'}},
                "spec": {"replicas": 1, "template": {}}}
        action = {"kind": "Deployment", "desired": {"spec": {"template": {}}}, "owned_paths": [["spec", "replicas"]]}
        self.assertTrue(action_matches(live, action))
        live["metadata"]["managedFields"][0]["fieldsV1"]["f:spec"]["f:replicas"] = {}
        self.assertFalse(action_matches(live, action))

    # Purpose: Kiểm Argo policy có thể recreate resource bị chặn trước sync và rollback mất UID.
    # Syntax: with assertRaises yêu cầu guard phát Error; tuple các options được test lần lượt.
    # Flow: Application có Replace=true hoặc Force=true → source_app dừng CHANGE_UNSAFE trước thao tác ghi.
    # Kiến thức liên quan: Replace/Force khác SSA update; recreate làm UID cũ không còn để compensate.
    def test_destructive_argo_sync_policy_rejected(self):
        config, kube = {"argo_namespace": "argocd"}, Mock()
        for option in ("Replace=true", "Force=true"):
            kube.get.return_value = {"metadata": {}, "spec": {"syncPolicy": {"syncOptions": [option]}}}
            with self.assertRaises(Error) as caught:
                source_app(config, kube, "app")
            self.assertEqual(caught.exception.code, "CHANGE_UNSAFE")

    # Purpose: Kiểm Kube.get không để kubectl giấu managedFields cần cho ownership/removal.
    # Syntax: lambda trả JSON khác theo argv, mô phỏng chế độ in của kubectl.
    # Flow: get Deployment → bật show-managed-fields → declarations thấy ownership spec.replicas.
    # Kiến thức liên quan: kubectl JSON mặc định có thể bỏ managedFields; missing metadata làm diff/release proof sai.
    def test_kube_get_preserves_field_ownership_for_diff(self):
        metadata = {"managedFields": [{"manager": "argocd-controller", "operation": "Apply", "fieldsV1": {"f:spec": {"f:replicas": {}}}}]}
        runner = Mock()
        runner.run.side_effect = lambda args, *a: json.dumps({"kind": "Deployment", "metadata": metadata if "--show-managed-fields=true" in args else {}, "spec": {"replicas": 1}})
        live = Kube("test", runner).get("Deployment", "app", "ns")
        self.assertIn(["spec", "replicas"], declarations(live))

    # Purpose: Kiểm restore resource Argo không để field vừa phục hồi bị coi là field của actor khác ở plan sau.
    # Syntax: Dict lồng giữ metadata tracking; không có cú pháp nâng cao.
    # Flow: Tracked ConfigMap new → restore old với field manager argocd-controller → data baseline và RESTORED.
    # Kiến thức liên quan: JSON Patch vẫn kiểm UID/resourceVersion; field manager phục vụ ownership/removal ở lần tiếp theo.
    def test_argo_restore_keeps_field_attribution_for_next_plan(self):
        tracking = "app:/ConfigMap:ns/cfg"
        live = {"kind": "ConfigMap", "metadata": {"name": "cfg", "uid": "same", "resourceVersion": "1",
                "annotations": {"argocd.argoproj.io/tracking-id": tracking}}, "data": {"endpoint": "new"}}
        before = managed(live)
        before["data"] = {"endpoint": "old"}
        action = {"app": "app", "kind": "ConfigMap", "name": "cfg", "namespace": "ns", "uid": "same", "tracking_id": tracking,
                  "before": before, "desired": managed(live), "state": "APPLIED"}
        kube = FakeKube(live)
        Transaction({"step_timeout": 1}, kube, self.journal).restore(action)
        self.assertEqual(kube.last_manager, "argocd-controller")
        self.assertEqual(kube.current["data"], {"endpoint": "old"})
        self.assertEqual(action["state"], "RESTORED")

    # Purpose: Kiểm log trùng service/span ID nhưng span thuộc trace khác không được coi là correlation hợp lệ.
    # Syntax: with patch thay đồng hồ và sleep để test timeout ngay; Mock mô phỏng Loki/Grafana.
    # Flow: Log trace=a, span=b → exported span cùng ID nhưng trace=c → thiếu correlation và Error.
    # Kiến thức liên quan: Span ID chỉ cần duy nhất trong trace; phải so cả trace ID, span ID và service.
    def test_log_span_from_different_trace_is_not_correlation_proof(self):
        verifier = Verify.__new__(Verify)
        verifier.c, verifier.k, verifier.http = {"telemetry_wait": 1}, Mock(), Mock()
        verifier.k.runner.deadline.remaining.return_value = 1
        verifier.urls, verifier.auth = {"grafana": "http://test"}, {}
        verifier.http.get.return_value = {"jsonData": {"derivedFields": [{"datasourceUid": "tempo", "matcherRegex": "trace_id[^a-f0-9]+([a-f0-9]{32})"}]}}
        verifier.proxy = Mock(return_value={"data": {"result": [{"stream": {"kubernetes_container_name": "app"},
            "values": [["1", json.dumps({"trace_id": "a" * 32, "span_id": "b" * 16})]]}]}})
        spans = [{"service": "app", "id": "b" * 16, "trace": "c" * 32}]
        with patch("sre_observability.telemetry.time.monotonic", side_effect=[0, 0, 2]), patch("sre_observability.telemetry.time.sleep"):
            with self.assertRaises(Error) as caught:
                verifier.logs("a" * 32, spans, {"logs": ["app"]}, 0)
        self.assertEqual(caught.exception.code, "LOG_CORRELATION_MISSING")

    # Purpose: Kiểm public baseline không dùng session test để che lỗi truy cập anonymous.
    # Syntax: assertRaises kiểm Error; không có cú pháp nâng cao khác.
    # Flow: Auth client trả JSON nhưng anonymous trả 401 → public_baseline vẫn lỗi, không được PASS.
    # Kiến thức liên quan: public_http không có CookieJar của fixture; baseline cần đúng quyền truy cập ban đầu.
    def test_authenticated_session_cannot_mask_public_baseline_failure(self):
        app = self.fixture_app({"state": "NONE", "orders": []})
        app.c = {"contract_data": {"routes": [{"id": "public", "authenticated": False, "path": "/products", "expected": [200]}]}}
        app.http.request.return_value = {"items": []}
        app.public_http = Mock()
        app.public_http.request.side_effect = Error("AUTH_FAILED", "verify", "/products", "HTTP 401")
        with self.assertRaises(Error) as caught:
            app.public_baseline()
        self.assertEqual(caught.exception.code, "AUTH_FAILED")

    # Purpose: Kiểm counter lạnh được khởi động bằng GET và mutation không bị phát lại để tạo baseline.
    # Syntax: Mock.side_effect trả lỗi rồi giá trị; with patch thay clock để test không chờ thật.
    # Flow: GET baseline thiếu → một GET → baseline=1; checkout/POST baseline thiếu → Error và không gọi app.
    # Kiến thức liên quan: Baseline thật sau scrape cho phép đo delta; đây không phải coercion missing thành zero.
    def test_cold_counter_get_warmup_never_replays_mutation(self):
        app, verifier, kube = Mock(), Mock(), Mock()
        kube.runner.deadline.remaining.return_value = 1
        verifier.metric_baseline.side_effect = [Error("METRIC_MISSING", "S09", "app", "missing"), {"app": 1}]
        with patch("sre_observability.cli.time.monotonic", side_effect=[0, 0]):
            self.assertEqual(route_baseline(app, verifier, {"id": "get", "method": "GET"}, kube), {"app": 1})
        app.call.assert_called_once()
        app.call.reset_mock()
        verifier.metric_baseline.side_effect = Error("METRIC_MISSING", "S09", "app", "missing")
        with self.assertRaises(Error):
            route_baseline(app, verifier, {"id": "checkout", "method": "POST"}, kube)
        app.call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
