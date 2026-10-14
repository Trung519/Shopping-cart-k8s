import copy
import base64
import re
import json
import math
import time
from pathlib import Path

from .config import load_yaml, yaml
from .core import Error, digest, need, safe_snapshot

WORKLOADS = {"Deployment", "StatefulSet", "DaemonSet"}
ALLOWED = WORKLOADS | {"ConfigMap", "Service", "PrometheusRule", "Telemetry", "Prometheus", "Alertmanager", "GeneratedScrapeConfig"}


# Purpose: So PVC theo định danh, tránh lỗi giả do API trả thứ tự khác.
# Syntax: lambda tạo hàm ngắn tại chỗ; closure dùng biến từ hàm/lớp bao ngoài; comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: List PVC → chọn namespace/name/UID/volume → sắp xếp namespace/name; UID đổi vẫn bị phát hiện.
# Kiến thức liên quan: sorted trả list mới; UID nhận diện PVC thật, volume nhận diện storage được bind.
def pvc_identity(rows):
    return sorted(({key: row.get(key) for key in ("namespace", "name", "uid", "volume")} for row in rows),
                  key=lambda row: (row["namespace"], row["name"]))


# Purpose: Chuẩn hóa alias image và chặn tag latest ngầm.
# Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
# Flow: redis:7 → docker.io/library/redis:7; redis hoặc :latest → IMAGE_UNAVAILABLE.
# Kiến thức liên quan: OCI reference gồm registry/repository:tag hoặc @sha256:digest; tag có thể đổi nên cần proof digest.
def image_ref(image):
    need(isinstance(image, str) and re.fullmatch(r"[a-zA-Z0-9._:/@-]+", image), "IMAGE_UNAVAILABLE", "S02", "image", "Image reference không hợp lệ.")
    if "@" in image:
        need(re.fullmatch(r".+@sha256:[a-f0-9]{64}", image), "IMAGE_UNAVAILABLE", "S02", "image", "Digest image cần sha256 đủ 64 ký tự hex.")
        repository, pinned = image.split("@", 1)
        if ":" in repository.rsplit("/", 1)[-1]:
            repository = repository.rsplit(":", 1)[0]
        image = repository + "@" + pinned
    name = image.split("@", 1)[0]
    need("@sha256:" in image or (":" in name.rsplit("/", 1)[-1] and not name.endswith((":latest", ":"))),
         "IMAGE_UNAVAILABLE", "S02", "image", "Image phải có tag cụ thể hoặc digest; không dùng latest/untagged.")
    if "/" not in image or ("." not in image.split("/")[0] and ":" not in image.split("/")[0] and image.split("/")[0] != "localhost"):
        image = "docker.io/" + image
    if image.startswith("docker.io/") and image.count("/") == 1:
        image = "docker.io/library/" + image.split("/", 1)[1]
    return image


# Purpose: Xác minh image cũ/mới theo digest ở các node phù hợp.
# Syntax: lambda tạo hàm ngắn tại chỗ; closure dùng biến từ hàm/lớp bao ngoài; comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: Chuẩn image refs → cache aliases theo eligible node → proofs hoặc UNKNOWN/conflicting digest blockers.
# Kiến thức liên quan: Node.status.images có thể bị giới hạn; thiếu entry là chưa có bằng chứng, không kết luận image không tồn tại.
def cache_proofs(nodes, pod_specs, subject):
    proofs, blockers = [], []
    for pod in pod_specs:
        eligible = eligible_nodes(nodes, pod)
        for container in pod.get("containers", []) + pod.get("initContainers", []):
            image = container["image"]
            normalized = image_ref(image)
            need(container.get("imagePullPolicy") != "Always" or "@sha256:" in image,
                 "IMAGE_UNAVAILABLE", "S02", subject, "imagePullPolicy=Always cần digest; cache tag không chứng minh image sẽ được pull.")
            for node in eligible:
                matched = []
                for row in node["status"].get("images", []):
                    aliases = []
                    for name in row.get("names", []):
                        try:
                            aliases.append(image_ref(name))
                        except Error:
                            continue
                    if normalized in aliases:
                        matched.extend(name for name in aliases if "@sha256:" in name)
                if not matched:
                    blockers.append({"code": "IMAGE_CACHE_UNKNOWN", "subject": subject, "image": image, "node": node["metadata"]["name"]})
                else:
                    proofs.append({"image": normalized, "node": node["metadata"]["name"], "digests": sorted(set(matched))})
    for image in {p["image"] for p in proofs}:
        digests = {d.split("@", 1)[1] for p in proofs if p["image"] == image for d in p["digests"]}
        if len(digests) != 1:
            blockers.append({"code": "IMAGE_DIGEST_CONFLICT", "subject": subject, "image": image})
    unique = {(p["image"], p["node"]): p for p in proofs}
    return sorted(unique.values(), key=lambda p: (p["image"], p["node"])), blockers


# Purpose: Giới hạn image preflight vào node có thể chạy pod theo chính sách hỗ trợ.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: Bỏ node cordoned/sai nodeSelector/taint chưa tolerate; affinity/nodeName → dừng thay vì đoán.
# Kiến thức liên quan: Taint/toleration và nodeSelector là ràng buộc scheduling; profile V1 chưa chứng minh affinity.
def eligible_nodes(nodes, pod):
    selected = []
    for node in nodes:
        if node.get("spec", {}).get("unschedulable"):
            continue
        labels = node["metadata"].get("labels", {})
        if not all(labels.get(k) == v for k, v in pod.get("nodeSelector", {}).items()):
            continue
        # Affinity/topology constraints need scheduler proof; fail closed instead
        # of guessing eligible nodes and claiming a rollback cache guarantee.
        need(not pod.get("affinity") and not pod.get("nodeName"), "CHANGE_UNSAFE", "S02", "scheduling",
             "Image preflight chưa hỗ trợ affinity/nodeName; cần profile chứng minh scheduling.")
        tolerated = True
        for taint in node.get("spec", {}).get("taints", []):
            if taint.get("effect") not in ("NoSchedule", "NoExecute"):
                continue
            tolerated &= any((t.get("effect", taint["effect"]) == taint["effect"] or not t.get("effect")) and
                             (t.get("key", "") == taint["key"] or (t.get("operator") == "Exists" and not t.get("key"))) and
                             (t.get("operator", "Equal") == "Exists" or t.get("value", "") == taint.get("value", ""))
                             for t in pod.get("tolerations", []))
        if tolerated:
            selected.append(node)
    need(selected, "IMAGE_UNAVAILABLE", "S02", "nodes", "Không có node phù hợp cho workload.")
    return selected


# Purpose: Đưa memory quantity về MiB để so cùng đơn vị.
# Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
# Flow: 1Gi → 1024 MiB; 64Mi → 64; quantity chưa hỗ trợ → CONFIG_INVALID.
# Kiến thức liên quan: Regex tách số và hậu tố; Gi dùng cơ số 1024, G dùng cơ số 1000.
def memory_mib(quantity):
    if not quantity:
        return 0
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(Ki|Mi|Gi|Ti|K|M|G|T)?", str(quantity))
    need(match, "CONFIG_INVALID", "S02", "memory", "Memory quantity không được hỗ trợ.")
    unit = match[2] or ""
    factor = {"": 1 / 1048576, "Ki": 1 / 1024, "Mi": 1, "Gi": 1024, "Ti": 1048576,
              "K": 1000 / 1048576, "M": 1000000 / 1048576, "G": 1000000000 / 1048576, "T": 1000000000000 / 1048576}[unit]
    return float(match[1]) * factor


# Purpose: Tính RAM tăng thêm theo rollout và concurrent sidecars một cách bảo thủ.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: Tính limit mỗi pod → max(init,app+sidecars)+admission → nhân replicas/surge hoặc node count.
# Kiến thức liên quan: Kubernetes request phục vụ scheduling, không giới hạn usage; math.ceil làm tròn maxSurge phần trăm lên.
def surge_mib(action, node_count):
    spec = action["desired"].get("spec", {})
    if action["kind"] in WORKLOADS:
        pod = spec["template"]["spec"]
        # Purpose: Không dùng request như cam kết pod chỉ tiêu thụ từng đó RAM.
        # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
        # Flow: Container có memory limit → memory_mib; thiếu limit → CAPACITY_UNKNOWN.
        # Kiến thức liên quan: memory limit là trần cấu hình; need dừng khi không chứng minh được budget.
        def budget(container):
            resources = container.get("resources", {})
            limit = resources.get("limits", {}).get("memory")
            need(limit, "CAPACITY_UNKNOWN", "S03", container.get("name", "container"),
                 "Thiếu memory limit; request không chứng minh đủ RAM cho rollout.")
            value = memory_mib(limit)
            need(value > 0, "CAPACITY_UNKNOWN", "S03", container.get("name", "container"), "Memory limit phải lớn hơn 0.")
            return value
        sidecars, initial = 0, 0
        for container in pod.get("initContainers", []):
            value = budget(container)
            if container.get("restartPolicy") == "Always":
                sidecars += value
                initial = max(initial, sidecars)
            else:
                initial = max(initial, sidecars + value)
        per_pod = max(initial, sidecars + sum(budget(c) for c in pod.get("containers", []))) + memory_mib(pod.get("overhead", {}).get("memory")) + action.get("admission_memory_mib", 0)
        replicas = spec.get("replicas", 1)
        if action["kind"] == "Deployment":
            strategy = spec.get("strategy", {})
            surge = 0 if strategy.get("type") == "Recreate" else strategy.get("rollingUpdate", {}).get("maxSurge", "25%")
            extra = math.ceil(replicas * int(surge[:-1]) / 100) if isinstance(surge, str) and surge.endswith("%") else int(surge)
            # Terminating old pods may coexist with all replacement pods; count
            # new replicas plus surge, not just the nominal extra pod.
            return per_pod * (replicas + extra)
        return per_pod * (node_count if action["kind"] == "DaemonSet" else replicas)
    if action["kind"] in ("Prometheus", "Alertmanager"):
        limit = spec.get("resources", {}).get("limits", {}).get("memory")
        need(limit, "CAPACITY_UNKNOWN", "S03", action.get("name", action["kind"]), "CR thiếu memory limit; chưa chứng minh budget operator rollout.")
        value = memory_mib(limit)
        need(value > 0, "CAPACITY_UNKNOWN", "S03", action.get("name", action["kind"]), "CR memory limit phải lớn hơn 0.")
        return (value + action.get("admission_memory_mib", 0)) * spec.get("replicas", 1)
    return 0


# Purpose: Chỉ nhận workload đã nhận spec mới và đủ replica cập nhật.
# Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
# Flow: observedGeneration cũ → False; StatefulSet revision lệch → False; đủ ready+updated → True.
# Kiến thức liên quan: generation là version spec; observedGeneration và revision cho biết controller đã xử lý rollout.
def ready(obj):
    spec, status = obj.get("spec", {}), obj.get("status", {})
    if status.get("observedGeneration", 0) < obj["metadata"].get("generation", 1):
        return False
    if obj["kind"] == "DaemonSet":
        wanted = status.get("desiredNumberScheduled", 0)
        return wanted > 0 and status.get("numberReady", 0) == wanted and status.get("updatedNumberScheduled", 0) == wanted
    wanted = spec.get("replicas", 1)
    if obj["kind"] == "StatefulSet" and status.get("currentRevision") != status.get("updateRevision"):
        return False
    return wanted > 0 and status.get("readyReplicas", 0) >= wanted and status.get("updatedReplicas", 0) >= wanted


# Purpose: So field manifest đã khai báo mà vẫn chấp nhận API default.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: live có thêm default → vẫn True; field khai báo khác hoặc list lệch → False.
# Kiến thức liên quan: Đệ quy dict/list; hàm này không phát hiện field đã xóa, desired_matches bổ sung ownership check.
def subset(live, desired):
    """API defaults may add fields; compare only declared manifest fields."""
    if isinstance(desired, dict):
        if not isinstance(live, dict):
            return False
        return all(key in live and subset(live[key], value) for key, value in desired.items())
    if isinstance(desired, list):
        return isinstance(live, list) and len(live) == len(desired) and all(subset(a, b) for a, b in zip(live, desired))
    return live == desired


# Purpose: Tìm đường dẫn field Argo từng quản lý để phát hiện xóa field.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt; raise ... from None ẩn exception gốc khỏi thông báo để tránh lộ dữ liệu.
# Flow: Đọc managedFields/last-applied → leaf paths spec/data/metadata → bỏ annotation quản lý của Argo.
# Kiến thức liên quan: FieldsV1 f: là field, k: là phần tử list theo key; last-applied là manifest cũ do client lưu.
def declarations(obj):
    paths = []
    # Purpose: Giải mã cây ownership FieldsV1 thành đường dẫn field.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: f:spec/f:replicas → [spec,replicas]; k:{name:app} → thêm selector phần tử list.
    # Kiến thức liên quan: Closure dùng paths của hàm ngoài; json.loads giải mã selector k:.
    def walk(fields, path):
        for key, child in fields.items():
            if key.startswith("f:"):
                next_path = path + [key[2:]]
            elif key.startswith("k:"):
                next_path = path + [json.loads(key[2:])]
            else:
                continue
            if child:
                walk(child, next_path)
            else:
                paths.append(next_path)
    managers = obj.get("metadata", {}).get("managedFields", [])
    modern = any("argocd" in f.get("manager", "").lower() and f.get("operation") == "Apply" for f in managers)
    legacy = any(f.get("manager") == "kubectl-client-side-apply" for f in managers)
    for field in managers:
        if "argocd" in field.get("manager", "").lower() or field.get("manager") == "kubectl-client-side-apply":
            walk(field.get("fieldsV1", {}), [])
    previous = obj.get("metadata", {}).get("annotations", {}).get("kubectl.kubernetes.io/last-applied-configuration")
    if previous and (not modern or legacy):
        try:
            declaration = json.loads(previous)
        except ValueError:
            raise Error("CONFIG_INVALID", "S02", "ownership", "Last-applied declaration không hợp lệ.") from None
        # Purpose: Lấy field khai báo từ manifest last-applied.
        # Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
        # Flow: Dict đi sâu; list giữ đường dẫn và phần tử có name; scalar → thêm leaf path.
        # Kiến thức liên quan: Đệ quy; named-list selector tránh nhầm container khi thứ tự danh sách thay đổi.
        def leaves(value, path):
            if isinstance(value, dict):
                for key, child in value.items():
                    leaves(child, path + [key])
            elif isinstance(value, list):
                paths.append(path)
                for child in value:
                    if isinstance(child, dict) and "name" in child:
                        leaves(child, path + [{"name": child["name"]}])
            else:
                paths.append(path)
        leaves(declaration, [])
    return [p for p in paths if p and (p[0] in ("spec", "data") or p[:2] in (["metadata", "labels"], ["metadata", "annotations"]))
            and not (len(p) > 2 and p[:2] == ["metadata", "annotations"] and
                     p[2] in ("argocd.argoproj.io/tracking-id", "kubectl.kubernetes.io/last-applied-configuration"))]


# Purpose: Kiểm live đã cập nhật và xóa đủ field của action.
# Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
# Flow: Đổi desired snapshot về shape resource → desired_matches; public scrape config so đúng toàn bộ.
# Kiến thức liên quan: managed tách field reversible; owned_paths ghi phạm vi declaration được Argo quản lý.
def action_matches(live, action):
    desired = action["desired"]
    if action["kind"] == "GeneratedScrapeConfig":
        return managed(live) == desired
    target = {"kind": action["kind"], "metadata": {}}
    for key, value in desired.items():
        if key.startswith("metadata_"):
            target["metadata"][key[len("metadata_"):]] = value
        else:
            target[key] = value
    owned = action.get("owned_paths", [])
    # API re-adds replicas=1 when SSA releases this declaration; a field still
    # owned by Argo is not a default-release proof. Other removals stay strict.
    modern = any("argocd" in f.get("manager", "").lower() and f.get("operation") == "Apply" for f in live["metadata"].get("managedFields", []))
    if modern and action["kind"] in ("Deployment", "StatefulSet", "Prometheus", "Alertmanager") and live.get("spec", {}).get("replicas") == 1 and "replicas" not in desired.get("spec", {}) and ["spec", "replicas"] not in declarations(live):
        owned = [p for p in owned if p != ["spec", "replicas"]]
    return desired_matches(live, target, owned)


# Purpose: Kiểm một field hoặc phần tử named-list còn tồn tại.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: [spec,containers,{name:app},args] → đi từng tầng; thiếu một tầng → False.
# Kiến thức liên quan: next(generator,None) chọn item đầu khớp selector; subset so selector trên dict.
def contains_path(obj, path):
    for segment in path:
        if isinstance(segment, dict):
            obj = next((item for item in obj if subset(item, segment)), None) if isinstance(obj, list) else None
        else:
            obj = obj.get(segment) if isinstance(obj, dict) else None
        if obj is None:
            return False
    return True


# Purpose: Phát hiện cả sửa giá trị và xóa field từng được quản lý.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: So declared fields → ConfigMap data → owned path bị xóa; API default ngoài ownership được giữ.
# Kiến thức liên quan: subset cho phép default; contains_path phát hiện removal; ConfigMap whitelist quản lý toàn bộ data.
def desired_matches(live, target, owned_paths=()):
    if not subset(managed(live), managed(target)):
        return False
    if live["kind"] == "ConfigMap" and live.get("data", {}) != target.get("data", {}):
        return False
    return not any(contains_path(live, path) and not contains_path(target, path) for path in owned_paths)


# Purpose: Chọn dữ liệu có thể restore an toàn vào journal.
# Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
# Flow: Resource thường → spec/data+labels/annotations; public scrape Secret → YAML decoded; secret auth/binary → lỗi.
# Kiến thức liên quan: deepcopy tách snapshot; YAML parser và safe_snapshot không cho credential lọt vào restore payload.
def managed(obj):
    if obj["kind"] == "Secret":
        # This chart stores PUBLIC scrape configuration in a Secret. Journal only
        # its decoded credential-free config, never a Secret manifest/base64 data.
        key = "additional-scrape-configs.yaml"
        need(set(obj.get("data", {})) == {key}, "SNAPSHOT_UNSAFE", "S03", obj["metadata"]["name"], "Scrape config Secret có key ngoài phạm vi public config.")
        text = base64.b64decode(obj["data"][key]).decode()
        parsed = yaml.safe_load(text)
        # Purpose: Chặn scrape job có cấu hình authentication inline.
        # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
        # Flow: Duyệt dict/list public scrape config → gặp basic_auth/oauth2/token/credentials → SNAPSHOT_UNSAFE.
        # Kiến thức liên quan: Đệ quy kiểm config, kể cả credential nằm sâu trong job list.
        def check_auth(value):
            if isinstance(value, dict):
                need(not set(value) & {"basic_auth", "authorization", "oauth2", "bearer_token", "bearer_token_file", "password", "credentials"},
                     "SNAPSHOT_UNSAFE", "S03", "scrape config", "Auth-bearing scrape config cần Secret-reference strategy riêng.")
                for child in value.values():
                    check_auth(child)
            elif isinstance(value, list):
                for child in value:
                    check_auth(child)
        need(isinstance(parsed, list), "CONFIG_INVALID", "S02", "scrape config", "Scrape config cần là job list.")
        check_auth(parsed)
        safe_snapshot(parsed)
        return {"scrape_config": text}
    key = "data" if obj["kind"] == "ConfigMap" else "spec"
    result = {key: copy.deepcopy(obj[key])} if key in obj else {}
    for field in ("labels", "annotations"):
        if field in obj["metadata"]:
            result["metadata_" + field] = copy.deepcopy(obj["metadata"][field])
    if obj["kind"] == "ConfigMap" and obj.get("binaryData"):
        raise Error("SNAPSHOT_UNSAFE", "S03", obj["metadata"]["name"], "ConfigMap binaryData chưa được hỗ trợ.")
    return result


# Purpose: Kiểm nền cluster/app/dependency/storage trước deploy hoặc sau restore.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt; *collection unpack phần tử vào lời gọi hoặc list.
# Flow: Node Ready → workload+pod+OTLP env → endpoints+PVC+mesh; mutation thêm RAM/RBAC → baseline.
# Kiến thức liên quan: Kubernetes conditions và UID là bằng chứng readiness/identity; endpoint chỉ chứng minh kết nối nền.
def inspect(config, kube, mutation=False):
    identity = kube.get("namespace", "kube-system")["metadata"]["uid"]
    nodes = kube.get("nodes")["items"]
    need(nodes, "CAPACITY_LOW", "S01", "nodes", "Cluster không có node.")
    for node in nodes:
        conditions = {c["type"]: c["status"] for c in node["status"]["conditions"]}
        need(conditions.get("Ready") == "True" and all(conditions.get(c) != "True" for c in ("MemoryPressure", "DiskPressure", "PIDPressure")),
             "CAPACITY_LOW", "S01", node["metadata"]["name"], "Node chưa Ready hoặc đang chịu pressure.")
    workload_rows = []
    sdk_services = {service for route in config["contract_data"]["routes"] if route.get("scope") != "mesh-http-only" for service in route["services"]}
    for ns, kind, name in config["workloads"]:
        obj = kube.get(kind, name, ns, optional=True)
        need(obj, "APP_MISSING", "S01", name, "Chưa có workload bắt buộc trong " + ns + ".")
        need(ready(obj), "BASELINE_UNHEALTHY", "S03", name, "Workload baseline chưa Ready.")
        if name in sdk_services:
            env = {}
            for container in obj["spec"]["template"]["spec"].get("containers", []):
                for source in container.get("envFrom", []):
                    if "configMapRef" in source:
                        env.update(kube.get("configmap", source["configMapRef"]["name"], ns).get("data", {}))
                env.update({e["name"]: e["value"] for e in container.get("env", []) if "value" in e})
            need(env.get("OTEL_SDK_DISABLED", "false").lower() != "true" and env.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
                 "OTEL_CONFIG_MISSING", "S04", name, "SDK bị tắt hoặc chưa có OTLP endpoint theo contract.")
        selector = ",".join(k + "=" + v for k, v in obj["spec"]["selector"]["matchLabels"].items())
        pods = kube.get("pods", namespace=ns)["items"]
        expected = obj["spec"]["selector"]["matchLabels"]
        selected = [p for p in pods if not p["metadata"].get("deletionTimestamp") and
                    all(p["metadata"].get("labels", {}).get(k) == v for k, v in expected.items())]
        need(selected, "BASELINE_UNHEALTHY", "S03", name, "Không có pod active cho workload.")
        images = []
        for pod in selected:
            need(pod.get("status", {}).get("phase") == "Running" and
                 any(c["type"] == "Ready" and c["status"] == "True" for c in pod.get("status", {}).get("conditions", [])),
                 "BASELINE_UNHEALTHY", "S03", name, "Pod baseline chưa Ready.")
            for init in pod.get("status", {}).get("initContainerStatuses", []):
                if init["name"] not in {c["name"] for c in pod["spec"].get("initContainers", []) if c.get("restartPolicy") == "Always"}:
                    need(init.get("state", {}).get("terminated", {}).get("exitCode") == 0,
                         "BASELINE_UNHEALTHY", "S03", name, "Init container chưa hoàn tất thành công.")
            statuses = pod.get("status", {}).get("containerStatuses", [])
            native = {c["name"] for c in pod["spec"].get("initContainers", []) if c.get("restartPolicy") == "Always"}
            statuses += [c for c in pod.get("status", {}).get("initContainerStatuses", []) if c["name"] in native]
            need(statuses and all(c.get("ready") for c in statuses), "BASELINE_UNHEALTHY", "S03", name,
                 "Container hoặc native sidecar chưa Ready.")
            images.extend({"name": c["name"], "image_id": c.get("imageID"), "restarts": c.get("restartCount", 0)} for c in statuses)
        workload_rows.append({"namespace": ns, "kind": kind, "name": name,
                              "uid": obj["metadata"]["uid"], "images": images})
    for ns, service in config["dependencies"]:
        svc = kube.get("service", service, ns, optional=True)
        eps = kube.get("endpoints", service, ns, optional=True)
        need(svc and eps and any(s.get("addresses") for s in eps.get("subsets", [])),
             "DEPENDENCY_UNREACHABLE", "S04", service, "Dependency không có endpoint Ready.")
    pvcs = []
    for ns in {config["obs_namespace"], *[x[0] for x in config["dependencies"]]}:
        for pvc in kube.get("pvc", namespace=ns)["items"]:
            need(pvc.get("status", {}).get("phase") == "Bound", "BASELINE_UNHEALTHY", "S03", pvc["metadata"]["name"], "PVC chưa Bound.")
            pvcs.append({"namespace": ns, "name": pvc["metadata"]["name"], "uid": pvc["metadata"]["uid"],
                         "volume": pvc["spec"].get("volumeName")})
    mesh_cfg = config["mesh"]
    mesh = yaml.safe_load(kube.get("configmap", mesh_cfg["configmap"], mesh_cfg["namespace"])["data"]["mesh"])
    providers = {p["name"]: p for p in mesh.get("extensionProviders", [])}
    need(mesh.get("enableTracing") and mesh_cfg["provider"] in providers and mesh_cfg["log_provider"] in providers,
         "MESH_PREREQUISITE_MISSING", "S04", "Istio", "Mesh thiếu tracing/log provider.",
         "Review configure-istio-tracing.py và cấu hình mesh trước khi deploy.")
    available_mib = None
    if mutation:
        text = kube.runner.run(config["vm_memory_command"])
        match = re.search(r"^MemAvailable:\s+(\d+)\s+kB", text, re.M)
        need(match and int(match[1]) >= config["min_memory_mib"] * 1024, "CAPACITY_LOW", "S01", "VM", "VM không đủ memory headroom.")
        available_mib = int(match[1]) // 1024
        for verb in ("get", "create", "patch", "delete"):
            need(kube.can(verb, "leases.coordination.k8s.io", config["obs_namespace"]), "RBAC_DENIED", "S01", "Lease", "Thiếu quyền lock/recovery.")
    return {"cluster_uid": identity, "workloads": workload_rows, "pvcs": pvc_identity(pvcs), "mesh_hash": digest(mesh),
            "node_count": len(nodes), "vm_free_memory_mib": available_mib}


# Purpose: Bảo đảm Argo không tranh ghi và render đúng nguồn được quản lý.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: Operation đang chạy/auto-sync bật/owner hoặc sources lệch/inline Helm override → dừng; hợp lệ trả app.
# Kiến thức liên quan: ApplicationSet có thể tái bật sync; selected sync chỉ an toàn khi nguồn quản lý giữ manual policy.
def source_app(config, kube, name):
    app = kube.get("application", name, config["argo_namespace"])
    need(not {str(option).lower() for option in app["spec"].get("syncPolicy", {}).get("syncOptions", [])} & {"replace=true", "force=true"},
         "CHANGE_UNSAFE", "S02", name, "Argo Replace/Force có thể tạo lại resource; không có rollback V1 an toàn.")
    migration = app["metadata"].get("annotations", {}).get("argocd.argoproj.io/client-side-apply-migration-manager")
    need(migration in (None, "argocd-controller", "kubectl-client-side-apply"), "CHANGE_UNSAFE", "S02", name, "Custom migration manager ngoài phạm vi ownership V1.")
    need(not app.get("operation"), "RUN_BUSY", "S01", name, "Argo đang có operation khác.")
    policy = app["spec"].get("syncPolicy", {}).get("automated")
    need(policy is None or policy.get("enabled") is False, "OWNER_CONFLICT", "S01", name, "Auto-sync chưa được pause tại nguồn quản lý.")
    sources = app["spec"].get("sources", [])
    need(len(sources) == 2, "CONFIG_INVALID", "S02", name, "Cần chart + values sources theo profile.")
    need(all(s.get("repoURL") == config["repo_url"] and s.get("targetRevision") == config["branch"] for s in sources),
         "OWNER_CONFLICT", "S02", name, "Argo source không khớp repo/branch cấu hình.")
    owners = app["metadata"].get("ownerReferences", [])
    for owner in owners:
        need(owner["kind"] == "ApplicationSet", "OWNER_CONFLICT", "S01", name, "Owner Argo chưa được hỗ trợ.")
        parent = kube.get("applicationset", owner["name"], config["argo_namespace"])
        automated = parent["spec"]["template"]["spec"].get("syncPolicy", {}).get("automated")
        need(automated is None or automated.get("enabled") is False, "OWNER_CONFLICT", "S01", name, "Parent có thể bật lại auto-sync.")
    helm = sources[0].get("helm", {})
    need(not any(helm.get(key) for key in ("parameters", "fileParameters", "values", "valuesObject")), "CONFIG_INVALID", "S02", name,
         "Helm overrides inline chưa hỗ trợ; tránh render sai source.")
    return app


# Purpose: Tạo danh sách thay đổi reversible từ đúng Git source và live baseline.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt; *collection unpack phần tử vào lời gọi hoặc list.
# Flow: Kiểm SHA remote → render Helm → ownership/diff → snapshots+image digest proofs/blockers → plan.
# Kiến thức liên quan: Server-side apply ownership phát hiện removal; Node image cache là bằng chứng giới hạn, thiếu proof thì block.
def build_plan(config, kube, baseline):
    repo = Path(config["repo_root"])
    git = ["git", "-C", str(repo)]
    sha = kube.runner.run(git + ["rev-parse", "HEAD"]).strip()
    remote = kube.runner.run(git + ["ls-remote", "--exit-code", "origin", "refs/heads/" + config["branch"]]).split()[0]
    need(sha == remote, "SOURCE_NOT_PUSHED", "S02", "Git", "HEAD khác remote branch.")
    apps, actions, dirty, blockers = [], [], [], []
    for entry in config["managed_apps"]:
        app = source_app(config, kube, entry["name"])
        need(kube.can("patch", "applications.argoproj.io", config["argo_namespace"]), "RBAC_DENIED", "S01", entry["name"], "Thiếu quyền điều khiển/terminate Argo operation.")
        chart_source = app["spec"]["sources"][0]
        chart = repo / chart_source["path"]
        values = [x.removeprefix("$values/") for x in chart_source["helm"]["valueFiles"]]
        paths = [chart_source["path"], *values, "gitops/control-plane"]
        changes = kube.runner.run(git + ["status", "--porcelain", "--"] + paths)
        if changes.strip():
            dirty.append(entry["name"])
        render_args = ["helm", "template", chart_source["helm"].get("releaseName", entry["name"]), str(chart),
                       "--namespace", app["spec"]["destination"]["namespace"]]
        for value in values:
            need((repo / value).is_file(), "CONFIG_MISSING", "S02", value, "Thiếu values file.")
            render_args += ["-f", str(repo / value)]
        objects = [o for o in yaml.safe_load_all(kube.runner.run(render_args, timeout=120)) if o]
        found = set()
        for target in objects:
            kind, meta = target["kind"], target["metadata"]
            if kind == "Secret" and "additional-scrape-configs.yaml" in target.get("data", {}):
                kind = "GeneratedScrapeConfig"
            if [kind, meta["name"]] not in entry["resources"]:
                continue
            found.add((kind, meta["name"]))
            need(kind in ALLOWED and not meta.get("annotations", {}).get("helm.sh/hook"), "CHANGE_UNSAFE", "S02", meta["name"], "Resource/hook ngoài phạm vi reversible.")
            ns = meta.get("namespace", app["spec"]["destination"]["namespace"])
            live = kube.get(kind, meta["name"], ns, optional=True)
            need(live, "PREREQUISITE_MISSING", "S02", meta["name"],
                 "V1 cần resource/prerequisite đã tồn tại; không bootstrap storage/CRDs/hooks.")
            for resource in (live, target):
                annotations = resource["metadata"].get("annotations", {})
                options = annotations.get("argocd.argoproj.io/sync-options", "")
                need(isinstance(options, str) and not {o.strip().lower() for o in options.split(",")} &
                     {"replace=true", "force=true", "serversideapply=false", "clientsideapplymigration=false"} and
                     not annotations.get("argocd.argoproj.io/hook"), "CHANGE_UNSAFE", "S02", meta["name"],
                     "Resource có hook/destructive apply hoặc override apply không hỗ trợ.")
            tracking = live["metadata"].get("annotations", {}).get("argocd.argoproj.io/tracking-id", "")
            need(tracking.startswith(entry["name"] + ":"), "OWNER_CONFLICT", "S02", meta["name"], "Resource không thuộc Argo app dự kiến.")
            before, desired = managed(live), managed(target)
            if kind == "StatefulSet":
                for immutable in ("volumeClaimTemplates", "serviceName", "selector"):
                    need(subset(before["spec"].get(immutable), desired["spec"].get(immutable)), "CHANGE_UNSAFE", "S02", meta["name"], "Không đổi storage/selector StatefulSet.")
            if kind == "Service":
                for field in ("clusterIP", "clusterIPs", "type"):
                    if field in desired["spec"]:
                        need(before["spec"].get(field) == desired["spec"][field], "CHANGE_UNSAFE", "S02", meta["name"], "Không đổi định danh/type Service.")
            owned_paths = declarations(live)
            if not desired_matches(live, target, owned_paths):
                safe_snapshot(before)
                safe_snapshot(desired)
                for verb in ("patch", "get"):
                    need(kube.can(verb, kind, ns), "RBAC_DENIED", "S02", meta["name"], "Thiếu quyền thay đổi/restore resource.")
                image_proofs, admission_memory = [], 0
                if kind in WORKLOADS:
                    old_pod, new_pod = before["spec"]["template"]["spec"], desired["spec"]["template"]["spec"]
                    nodes = kube.get("nodes")["items"]
                    image_proofs = []
                    declared_names = {c["name"] for c in new_pod.get("containers", []) + new_pod.get("initContainers", [])}
                    selector = live["spec"]["selector"]["matchLabels"]
                    selected_pods = [p for p in kube.get("pods", namespace=ns)["items"] if not p["metadata"].get("deletionTimestamp") and
                                     all(p["metadata"].get("labels", {}).get(k) == v for k, v in selector.items())]
                    need(selected_pods, "CAPACITY_UNKNOWN", "S02", meta["name"], "Thiếu pod baseline để tính admission sidecar budget.")
                    admission_memory = 0
                    for pod in selected_pods:
                        extra = [c for c in pod["spec"].get("containers", []) + pod["spec"].get("initContainers", []) if c["name"] not in declared_names]
                        need(all(memory_mib(c.get("resources", {}).get("limits", {}).get("memory")) > 0 for c in extra),
                             "CAPACITY_UNKNOWN", "S02", meta["name"], "Injected sidecar thiếu memory limit; cần cấu hình trước rollout.")
                        admission_memory = max(admission_memory, sum(memory_mib(c["resources"]["limits"]["memory"]) for c in extra))
                    image_proofs, image_blockers = cache_proofs(nodes, (old_pod, new_pod), meta["name"])
                    blockers.extend(image_blockers)
                elif kind in ("Prometheus", "Alertmanager"):
                    for field in ("containers", "initContainers"):
                        need(desired["spec"].get(field) == before["spec"].get(field), "CHANGE_UNSAFE", "S02", meta["name"],
                             "CR custom container/init thay đổi chưa có rollout model hỗ trợ.")
                    child = kube.get("StatefulSet", kind.lower() + "-" + meta["name"], ns)
                    need(any(o.get("uid") == live["metadata"]["uid"] for o in child["metadata"].get("ownerReferences", [])),
                         "OWNER_CONFLICT", "S02", meta["name"], "CR child StatefulSet không thuộc đúng operator resource.")
                    old_pod = child["spec"]["template"]["spec"]
                    new_pod = copy.deepcopy(old_pod)
                    for field in ("nodeSelector", "tolerations", "affinity"):
                        if field in desired["spec"]:
                            new_pod[field] = desired["spec"][field]
                        elif field in before["spec"]:
                            new_pod.pop(field, None)
                    if (desired["spec"].get("version") != before["spec"].get("version") or before["spec"].get("image")) and not desired["spec"].get("image"):
                        blockers.append({"code": "IMAGE_CACHE_UNKNOWN", "subject": meta["name"], "reason": "CR version/image removal needs explicit spec.image"})
                    for container in new_pod.get("containers", []):
                        if container["name"] == kind.lower() and desired["spec"].get("image"):
                            container["image"] = desired["spec"]["image"]
                    extras = [c for c in old_pod.get("containers", []) + old_pod.get("initContainers", []) if c["name"] != kind.lower()]
                    need(all(memory_mib(c.get("resources", {}).get("limits", {}).get("memory")) > 0 for c in extras), "CAPACITY_UNKNOWN", "S02", meta["name"], "Operator sidecar/init thiếu memory limit dương.")
                    admission_memory = sum(memory_mib(c["resources"]["limits"]["memory"]) for c in extras)
                    image_proofs, image_blockers = cache_proofs(kube.get("nodes")["items"], (old_pod, new_pod), meta["name"])
                    blockers.extend(image_blockers)
                actions.append({"app": entry["name"], "kind": kind, "name": meta["name"], "namespace": ns,
                                "apiVersion": target["apiVersion"], "uid": live["metadata"]["uid"],
                                "tracking_id": tracking,
                                "before": before, "desired": desired, "owned_paths": owned_paths,
                                "image_proofs": image_proofs, "admission_memory_mib": admission_memory, "state": "PLANNED"})
        need(all(tuple(r) in found for r in entry["resources"]), "CONTRACT_INCOMPLETE", "S02", entry["name"], "Whitelist có resource không xuất hiện trong render.")
        apps.append({"name": entry["name"], "spec_hash": digest(app["spec"]), "source_revision": sha})
    return {"revision": sha, "apps": apps, "actions": actions, "dirty_apps": sorted(set(dirty)), "blocking_reasons": blockers,
            "baseline": baseline, "created": time.time(), "state": "PLANNED"}


# Purpose: Chờ workload hoặc operator CR thực sự hoàn tất trước bước kế.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: Workload → ready; CR → Reconciled đúng generation + child StatefulSet owner/revision/ready; hết giờ → lỗi.
# Kiến thức liên quan: Prometheus Operator tạo StatefulSet con; observedGeneration tránh nhận status của spec cũ.
def wait_workload(kube, action, seconds):
    if action["kind"] not in WORKLOADS | {"Prometheus", "Alertmanager"}:
        return
    deadline = time.monotonic() + min(seconds, kube.runner.deadline.remaining(seconds))
    while time.monotonic() < deadline:
        obj = kube.get(action["kind"], action["name"], action["namespace"])
        if action["kind"] in ("Prometheus", "Alertmanager"):
            prefix = action["kind"].lower()
            child = kube.get("StatefulSet", prefix + "-" + action["name"], action["namespace"], optional=True)
            conditions = obj.get("status", {}).get("conditions", [])
            reconciled = any(c.get("type") == "Reconciled" and c.get("status") == "True" and
                             c.get("observedGeneration", 0) >= obj["metadata"].get("generation", 1) for c in conditions)
            owned = child and any(o.get("uid") == obj["metadata"].get("uid") for o in child["metadata"].get("ownerReferences", []))
            if reconciled and owned and ready(child):
                return
        elif ready(obj):
            return
        time.sleep(2)
    raise Error("ROLLOUT_TIMEOUT", "S07", action["name"], "Workload chưa Ready trước deadline.")
