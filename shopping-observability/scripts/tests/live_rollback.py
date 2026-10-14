"""Opt-in real API compensation test; only an owned temporary ConfigMap changes."""
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sre_observability.config import load
from sre_observability.core import Error, Journal, Kube, Runner, need
from sre_observability.inventory import managed
from sre_observability.transaction import Transaction


# Purpose: Test rollback thật bằng ConfigMap tạm thuộc riêng lượt test.
# Syntax: finally luôn chạy để cleanup, dù nhánh try return hay phát lỗi.
# Flow: SSA tạo baseline → save PREPARED → SSA sửa/xóa key → reload+rollback hai lần → verify UID/baseline → xóa có precondition.
# Kiến thức liên quan: Kubernetes API thật kiểm SSA removal và compensation; chưa chứng minh Argo controller migration/rollout tổng quát.
def main():
    config = load()
    kube = Kube(config["context"], Runner(120))
    run_id = uuid.uuid4().hex
    name, namespace = "sre-rollback-test-" + run_id[:12], config["obs_namespace"]
    resource = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": name, "namespace": namespace,
                "labels": {"sre-owned-test": run_id}}, "data": {"endpoint": "baseline", "obsolete": "restore-me"}}
    journal = Journal(Path(config["log_dir"]) / ("obs-live-rollback-" + run_id + ".json"),
                      {"run_id": run_id, "state": "TESTING", "actions": [], "scope": "temporary ConfigMap only"})
    created = None
    try:
        kube.cmd(["apply", "--server-side", "--field-manager=sre-test-ssa", "-f", "-"], json.dumps(resource))
        created = kube.get("configmap", name, namespace)
        action = {"app": "owned-test", "kind": "ConfigMap", "name": name, "namespace": namespace,
                  "uid": created["metadata"]["uid"], "before": managed(created), "desired": {"data": {"endpoint": "broken"}}, "state": "PREPARED"}
        journal.data["actions"].append(action)
        journal.save()
        target = dict(resource, data={"endpoint": "broken"})
        kube.cmd(["apply", "--server-side", "--field-manager=sre-test-ssa", "-f", "-"], json.dumps(target))
        need(kube.get("configmap", name, namespace)["data"] == {"endpoint": "broken"},
             "TEST_FAILED", "test", name, "SSA chưa sửa và xóa đúng key declared.")
        journal.data["field_removal"] = "PASS"
        journal.save()
        # Simulate process failure BEFORE recording API success; PREPARED is recovered.
        reloaded = Journal(journal.path)
        tx = Transaction(config, kube, reloaded)
        need(tx.rollback(), "TEST_FAILED", "test", name, "Không restore được uncertain API write.")
        live = kube.get("configmap", name, namespace)
        need(managed(live) == action["before"] and live["metadata"]["uid"] == created["metadata"]["uid"],
             "TEST_FAILED", "test", name, "Baseline/UID không khớp.")
        need(tx.rollback(), "TEST_FAILED", "test", name, "Rollback lần hai không idempotent.")
        print("PASS: real API write → lost-response simulation → baseline restored → second rollback safe.")
        print("PASS: SSA removed obsolete key; rollback restored the key and its baseline value.")
        print("Report: " + str(journal.path))
    finally:
        current = kube.get("configmap", name, namespace, optional=True)
        if current:
            need(current["metadata"]["labels"].get("sre-owned-test") == run_id and
                 (created is None or current["metadata"]["uid"] == created["metadata"]["uid"]),
                 "CLEANUP_CONFLICT", "test", name, "Không xóa resource của owner khác.")
            # DeleteOptions preconditions protect against get/delete races.
            options = {"apiVersion": "v1", "kind": "DeleteOptions", "preconditions": {
                       "uid": current["metadata"]["uid"], "resourceVersion": current["metadata"]["resourceVersion"]}}
            kube.cmd(["delete", "--raw", "/api/v1/namespaces/" + namespace + "/configmaps/" + name, "-f", "-"], json.dumps(options))
        journal = Journal(journal.path)
        journal.data["test_cleanup"] = "PASS"
        journal.save()
        print("PASS: temporary ConfigMap removed; application resources were not modified.")


if __name__ == "__main__":
    main()
