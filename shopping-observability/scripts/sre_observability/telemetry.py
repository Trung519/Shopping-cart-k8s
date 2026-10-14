"""Acceptance requires fresh signals and complete graphs, including late consumers."""
import base64
import json
import math
import re
import secrets
import time
import urllib.parse
import uuid

from .core import Error, HTTP, need, secret


# Purpose: Chuẩn hóa trace/span ID backend trả về.
# Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
# Flow: Hex 16/32 ký tự → lowercase; base64 hợp lệ → hex; không đọc được → chuỗi rỗng.
# Kiến thức liên quan: OTLP JSON có thể trả ID base64; regex tránh nhầm chuỗi thường với ID hex.
def ident(value):
    if not value:
        return ""
    if re.fullmatch(r"[a-fA-F0-9]{16}|[a-fA-F0-9]{32}", value):
        return value.lower()
    try:
        return base64.b64decode(value, validate=True).hex()
    except ValueError:
        return ""


# Purpose: Đổi danh sách OTLP attributes sang mapping dễ kiểm.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: [{key:service.name,value:{stringValue:app}}] → {service.name:app}.
# Kiến thức liên quan: OTLP AnyValue bọc giá trị theo kiểu; next(iter(...),None) lấy giá trị đầu trong wrapper.
def attributes(items):
    return {item["key"]: next(iter(item["value"].values()), None) for item in items}


# Purpose: Rút span từ Tempo/OTLP và kiểm privacy trước nghiệm thu.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: Duyệt resource/scope/spans → kiểm SQL/URL/exception đã lọc → records với ID/service/parent/links.
# Kiến thức liên quan: attributes giải mã OTLP; ident chuẩn ID; need từ chối trace còn dữ liệu nhạy cảm.
def flatten(payload):
    spans = []
    for batch in payload.get("batches", payload.get("resourceSpans", [])):
        resource = attributes(batch.get("resource", {}).get("attributes", []))
        for scope in batch.get("scopeSpans", batch.get("instrumentationLibrarySpans", [])):
            for span in scope.get("spans", []):
                attrs = attributes(span.get("attributes", []))
                need(not span.get("status", {}).get("message") and
                     not any(set(attributes(event.get("attributes", []))) & {"exception.message", "exception.stacktrace"}
                             for event in span.get("events", [])), "PRIVACY_FAILED", "S09", "Collector", "Exception details chưa được lọc.")
                need(not set(attrs) & {"db.statement", "db.query.text", "http.url", "http.target", "url.full", "url.query"},
                     "PRIVACY_FAILED", "S09", "Collector", "Trace vẫn chứa SQL hoặc URL đầy đủ.")
                spans.append({"service": resource.get("service.name"), "sdk": resource.get("telemetry.sdk.name"),
                              "id": ident(span.get("spanId", span.get("spanID"))),
                              "trace": ident(span.get("traceId", span.get("traceID"))),
                              "parent": ident(span.get("parentSpanId", span.get("parentSpanID"))),
                              "kind": span.get("kind"), "attrs": attrs,
                              "links": [(ident(link.get("traceId")), ident(link.get("spanId"))) for link in span.get("links", [])]})
    return spans


# Purpose: So vai trò span dù backend dùng số hoặc tên enum.
# Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
# Flow: name=CLIENT → chấp nhận 3 hoặc SPAN_KIND_CLIENT; trả bool.
# Kiến thức liên quan: OpenTelemetry SpanKind phân biệt SERVER/CLIENT/PRODUCER/CONSUMER.
def kind(span, name):
    return span["kind"] in {"SERVER": (2, "SPAN_KIND_SERVER"), "CLIENT": (3, "SPAN_KIND_CLIENT"),
                            "PRODUCER": (4, "SPAN_KIND_PRODUCER"), "CONSUMER": (5, "SPAN_KIND_CONSUMER")}[name]


# Purpose: Phát hiện service, DB hoặc quan hệ gọi còn thiếu trong trace mới.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: Kiểm SERVER đúng trace → DB CLIENT → HTTP ancestry/AMQP parent hoặc link → list gaps.
# Kiến thức liên quan: Parent nối cây span; span link hỗ trợ consumer khác trace chỉ khi contract khai báo link.
def graph_gaps(spans, contract, trace_id):
    # Cross-trace consumers are accepted only through an explicitly declared
    # span link; DB/HTTP proof must belong to the fresh probe trace.
    gaps = []
    by_id = {s["id"]: s for s in spans if s["trace"] == trace_id}
    for service in contract["services"]:
        if not any(s["service"] == service and kind(s, "SERVER") and s["trace"] == trace_id for s in spans):
            gaps.append("server:" + service)
    for database in contract.get("databases", []):
        if not any(s["trace"] == trace_id and s["service"] == database["service"] and kind(s, "CLIENT") and
                   s["attrs"].get("db.system.name", s["attrs"].get("db.system")) == database["system"] for s in spans):
            gaps.append("db:" + database["service"] + ":" + database["system"])
    for edge in contract.get("edges", []):
        callers = [s for s in spans if s["trace"] == trace_id and s["service"] == edge["from"] and kind(s, "PRODUCER" if edge["type"] == "rabbitmq" else "CLIENT")]
        receivers = [s for s in spans if (s["trace"] == trace_id or edge.get("relation") == "link") and s["service"] == edge["to"] and kind(s, "CONSUMER" if edge["type"] == "rabbitmq" else "SERVER")]
        matched = False
        for receiver in receivers:
            if edge.get("relation") == "link":
                matched |= any((c["trace"], c["id"]) in receiver["links"] for c in callers)
            elif edge.get("relation") == "exact_parent":
                matched |= any(receiver["parent"] == c["id"] for c in callers)
            else:
                ancestor, visited = receiver.get("parent"), set()
                while ancestor and ancestor not in visited:
                    visited.add(ancestor)
                    matched |= any(ancestor == c["id"] for c in callers)
                    ancestor = by_id.get(ancestor, {}).get("parent")
        if not matched:
            gaps.append("edge:" + edge["from"] + ":" + edge["to"])
    return gaps


# Purpose: Lấy trace_id/span_id từ log thường hoặc JSON escaped.
# Syntax: X if C else Y chọn X khi điều kiện C đúng, còn lại dùng Y (fallback).
# Flow: Log có ID đúng số ký tự → tuple IDs; thiếu → (None,None).
# Kiến thức liên quan: Regex nhận log lồng/escaped; log có ID còn phải đối chiếu với span exported trong logs().
def log_ids(line):
    trace = re.search(r"trace_id[^a-f0-9]+([a-f0-9]{32})", line)
    span = re.search(r"span_id[^a-f0-9]+([a-f0-9]{16})", line)
    return (trace[1] if trace else None, span[1] if span else None)


class Verify:
    # Purpose: Tạo client kiểm backend và Grafana qua tunnel dùng chung.
    # Syntax: a,b = ... unpack và gán nhiều giá trị theo thứ tự; số phần tử phải khớp.
    # Flow: Mở backend URLs → lấy Grafana Secret → Basic auth trong RAM → sẵn sàng query.
    # Kiến thức liên quan: Forwards cache giảm process; Secret chỉ được resolve khi dùng, không lưu auth header.
    def __init__(self, config, kube, forwards, journal):
        self.c, self.k, self.f, self.j = config, kube, forwards, journal
        self.http = HTTP(deadline=kube.runner.deadline)
        self.urls = {}
        for name, service in config["backends"].items():
            self.urls[name] = forwards.open(config["obs_namespace"], service["service"], service["port"])
        graf = config["grafana"]
        self.urls["grafana"] = forwards.open(config["obs_namespace"], graf["service"], graf["port"])
        credentials = secret(kube, config["obs_namespace"], graf["secret"], [graf["username_key"], graf["password_key"]])
        auth = credentials[graf["username_key"]] + ":" + credentials[graf["password_key"]]
        self.auth = {"Authorization": "Basic " + base64.b64encode(auth.encode()).decode()}

    # Purpose: Kiểm query backend qua đúng datasource Grafana người dùng sẽ xem.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: uid=tempo,path=/api/traces/ID → HTTP GET qua datasource proxy có Basic auth.
    # Kiến thức liên quan: Grafana datasource proxy kiểm luôn wiring Grafana→Tempo/Loki/Prometheus.
    def proxy(self, uid, path):
        return self.http.get(self.urls["grafana"] + "/api/datasources/proxy/uid/" + uid + path, self.auth)

    # Purpose: Gọi PromQL qua Grafana và yêu cầu query thành công.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Expression → urlencode query → proxy prometheus → result list; status lỗi → METRIC_MISSING.
    # Kiến thức liên quan: PromQL là ngôn ngữ query Prometheus; result trống khác với counter bằng 0.
    def prom(self, expression):
        payload = self.proxy("prometheus", "/api/v1/query?" + urllib.parse.urlencode({"query": expression}))
        need(payload.get("status") == "success", "METRIC_MISSING", "S09", "Prometheus", "Query thất bại.")
        return payload["data"]["result"]

    # Purpose: Đọc một giá trị metric hữu hạn, không biến missing thành zero.
    # Syntax: raise ... from None ẩn lỗi parsing gốc; and short-circuit chỉ kiểm timestamp khi finite.
    # Flow: Trống+optional → None; required/nhiều series/sai sample → lỗi; một sample hữu hạn, timestamp mới → float.
    # Kiến thức liên quan: math.isfinite loại NaN/Infinity; query timestamp chưa chứng minh scrape freshness, counter kiểm riêng.
    def scalar(self, expression, required=True):
        rows = self.prom(expression)
        if not rows:
            need(not required, "METRIC_MISSING", "S09", "Prometheus", "Không có metric yêu cầu.")
            return None
        need(len(rows) == 1, "METRIC_AMBIGUOUS", "S09", "Prometheus", "Query trả nhiều series; cần một giá trị tổng rõ ràng.")
        try:
            value = float(rows[0]["value"][1])
            stamp = float(rows[0]["value"][0])
        except (KeyError, IndexError, TypeError, ValueError):
            raise Error("METRIC_INVALID", "S09", "Prometheus", "Sample metric không đúng cấu trúc số/timestamp.") from None
        need(math.isfinite(value), "METRIC_MISSING", "S09", "Prometheus", "Metric không có giá trị hữu hạn.")
        need(math.isfinite(stamp) and abs(time.time() - stamp) < 90, "METRIC_STALE", "S09", "Prometheus", "Timestamp query quá cũ hoặc clock lệch lớn.")
        return value

    # Purpose: Đọc mesh request counter theo service/namespace và kiểm scrape freshness.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Chọn namespace → query tuổi sample qua timestamp(selector) → age<90 → sum counter.
    # Kiến thức liên quan: Istio counter là mesh metric tổng, có thể tăng do traffic khác; không phải app metric/per-trace proof.
    def counter(self, service):
        need(re.fullmatch(r"[a-zA-Z0-9_.-]+", service), "CONFIG_INVALID", "S00", "service", "Tên service không hợp lệ cho query.")
        safe = service
        namespace = self.service_namespace(service)
        need(re.fullmatch(r"[a-zA-Z0-9_.-]+", namespace), "CONFIG_INVALID", "S00", "namespace", "Namespace metric không hợp lệ.")
        selector = 'istio_requests_total{reporter="destination",destination_workload="' + safe + '",destination_workload_namespace="' + namespace + '"}'
        # Evaluation timestamps alone do not prove scrape freshness.
        age = self.scalar('time() - min(timestamp(' + selector + '))', required=False)
        if age is None:
            return None
        need(0 <= age < 90, "METRIC_STALE", "S09", service, "Scrape mesh counter quá cũ.")
        return self.scalar('sum(' + selector + ')', required=False)

    # Purpose: Không cộng metric của workload cùng tên ở namespace khác.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Tra workloads/mesh service → đúng một namespace → trả tên; mơ hồ → CONFIG_INVALID.
    # Kiến thức liên quan: Profile workloads ánh xạ workload→namespace; mesh service dùng service.namespace.
    def service_namespace(self, service):
        found = {ns for ns, _, name in self.c["workloads"] if name == service}
        found.update(s.split(".", 1)[1] for route in self.c["contract_data"]["routes"] if route.get("scope") == "mesh-http-only"
                     for s in route["services"] if s.startswith(service + "."))
        need(len(found) == 1, "CONFIG_INVALID", "S00", service, "Không xác định được namespace duy nhất cho mesh metric.")
        return next(iter(found))

    # Purpose: Đo counter trước request để so delta sau request.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt; raise ... from None ẩn exception gốc khỏi thông báo để tránh lộ dữ liệu.
    # Flow: Lấy mesh baseline từng service và app queries nếu khai báo; missing → dừng trước probe.
    # Kiến thức liên quan: Counter delta cần baseline thực; app metric chỉ được kiểm khi contract khai báo query.
    def metric_baseline(self, contract):
        before = {service.split(".")[0] if contract.get("scope") == "mesh-http-only" else service:
                  self.counter(service.split(".")[0] if contract.get("scope") == "mesh-http-only" else service)
                  for service in contract["services"]}
        for metric in contract.get("application_metrics", []):
            try:
                self.app_metric_fresh(metric)
                before["app:" + metric["service"]] = self.scalar(metric["query"])
            except Error as error:
                raise Error("APP_" + error.code, error.step, error.subject, error.message, error.action) from None
        need(all(value is not None for value in before.values()), "METRIC_MISSING", "S09", contract["id"], "Thiếu counter baseline; chưa thể đo delta.")
        return before

    # Purpose: Không nhận app counter từ scrape cũ làm bằng chứng mới.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: freshness_query trả tuổi scrape → age từ 0 đến dưới 90 giây mới đạt.
    # Kiến thức liên quan: PromQL time()-min(timestamp(selector)) đo tuổi scrape thật; timestamp của aggregate query không đủ.
    def app_metric_fresh(self, metric):
        age = self.scalar(metric["freshness_query"])
        need(0 <= age < 90, "METRIC_STALE", "S09", metric["service"], "Scrape app counter quá cũ.")

    # Purpose: Quan sát Collector nhận/gửi/từ chối/mất span trong cửa sổ test.
    # Syntax: and/or short-circuit chỉ tính vế sau khi cần; X if C else Y chọn query hoặc None theo tuổi scrape.
    # Flow: Query accepted/sent bắt buộc và loss/queue optional → dict; optional thiếu → None.
    # Kiến thức liên quan: Prometheus series có thể không tồn tại khi chưa từng lỗi; None là UNKNOWN, không phải zero loss.
    def losses(self):
        result = {}
        for signal in ("receiver_accepted_spans", "exporter_sent_spans", "receiver_refused_spans", "exporter_send_failed_spans", "exporter_enqueue_failed_spans", "exporter_queue_size"):
            required = signal in ("receiver_accepted_spans", "exporter_sent_spans")
            selector = 'otelcol_' + signal + ("" if signal.endswith("size") else "_total") + '{job="otel-collector"}'
            age = self.scalar('time() - min(timestamp(' + selector + '))', required=required)
            need(not required or (age is not None and 0 <= age < 90), "METRIC_STALE", "S09", signal, "Scrape Collector counter quá cũ.")
            result[signal] = self.scalar('sum(' + selector + ')', required=required) if age is not None and 0 <= age < 90 else None
        return result

    # Purpose: Kiểm các scrape job bắt buộc tồn tại và đang UP.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: required_jobs + Redis job nếu bật → so activeTargets → missing/down báo lỗi → counts.
    # Kiến thức liên quan: Prometheus activeTargets chứng minh scrape wiring; UP không chứng minh trace/log correlation.
    def targets(self):
        targets = self.http.get(self.urls["prometheus"] + "/api/v1/targets")["data"]["activeTargets"]
        jobs = set(self.c["required_jobs"])
        if self.c["redis_server_metrics_required"]:
            jobs.add(self.c["redis_job"])
        missing = jobs - {t["labels"].get("job") for t in targets}
        need(not missing, "METRIC_MISSING", "S09", ",".join(sorted(missing)), "Thiếu scrape job bắt buộc.")
        down = [t["labels"].get("job") for t in targets if t["labels"].get("job") in jobs and t.get("health") != "up"]
        need(not down, "METRIC_TARGET_DOWN", "S09", ",".join(sorted(set(down))), "Scrape target chưa UP.")
        return {"required_jobs": sorted(jobs), "targets_up": len([t for t in targets if t.get("health") == "up"])}

    # Purpose: Chờ trace mới đủ service/DB/consumer theo contract.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Query Tempo bằng trace ID → flatten → graph_gaps; đủ → spans; 404/gaps chờ đến deadline.
    # Kiến thức liên quan: HTTP 404 có thể do ingestion chậm; telemetry_wait chờ consumer đến muộn, không nhận trace cũ.
    def trace(self, tid, contract):
        deadline = time.monotonic() + min(self.c["telemetry_wait"], self.k.runner.deadline.remaining(self.c["telemetry_wait"]))
        gaps = ["trace"]
        while time.monotonic() < deadline:
            try:
                payload = self.proxy("tempo", "/api/traces/" + tid)
                spans = flatten(payload)
                gaps = graph_gaps(spans, contract, tid)
                if spans and not gaps:
                    return spans
            except Error as error:
                if error.code != "HTTP_STATUS" or "404" not in error.message:
                    raise
            time.sleep(2)
        raise Error("TRACE_MISSING" if any(g.startswith("server:") or g == "trace" for g in gaps) else "TRACE_EDGE_MISSING",
                    "S09", contract["id"], "Thiếu bằng chứng: " + ", ".join(gaps),
                    "Kiểm tra SDK, sampling, OTLP endpoint và dependency instrumentation của app này.")

    # Purpose: Chứng minh log mới trỏ đúng exported trace/span và Grafana link.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Query Loki bằng trace ID → phân biệt app/mesh logs → đối chiếu span service/ID → nguồn log đã đạt.
    # Kiến thức liên quan: DerivedFields tạo link Loki→Tempo; grace 30 giây cho lệch clock, ID mới ngăn lấy log cũ.
    def logs(self, tid, spans, contract, start):
        deadline = time.monotonic() + min(self.c["telemetry_wait"], self.k.runner.deadline.remaining(self.c["telemetry_wait"]))
        required = set(contract["logs"]) | set(contract.get("mesh_logs", []))
        matched, sources = set(), {}
        derived = self.http.get(self.urls["grafana"] + "/api/datasources/uid/loki", self.auth)
        regex = next((x["matcherRegex"] for x in derived.get("jsonData", {}).get("derivedFields", []) if x.get("datasourceUid") == "tempo"), None)
        need(regex, "LOG_CORRELATION_MISSING", "S09", "Grafana", "Loki chưa có link tới Tempo.")
        while time.monotonic() < deadline:
            query = '{job="fluent-bit"} |= "' + tid + '"'
            payload = self.proxy("loki", "/loki/api/v1/query_range?" + urllib.parse.urlencode({"query": query,
                                  # Docker/Fluent Bit timestamps and laptop clocks can
                                  # differ slightly; a unique new trace ID prevents old-log matches.
                                  "start": int((start - 30) * 1e9), "end": time.time_ns(), "limit": 1000}))
            for stream in payload["data"]["result"]:
                container = stream["stream"].get("kubernetes_container_name")
                pod = stream["stream"].get("kubernetes_pod_name", "")
                if container == "istio-proxy":
                    for service in contract.get("mesh_logs", []):
                        if pod.startswith(service + "-") and any(log_ids(line)[0] == tid for _, line in stream["values"]):
                            matched.add(service)
                            sources[service] = "mesh access log; browser/app SDK NOT claimed"
                if container not in required:
                    continue  # istio-proxy logs never substitute for application logs
                for stamp, line in stream["values"]:
                    trace_id, span_id = log_ids(line)
                    link = re.search(regex, line)
                    if trace_id == tid and span_id and any(s["id"] == span_id and s["service"] == container and s["trace"] == tid for s in spans) and link and link[1] == tid:
                        matched.add(container)
                        sources[container] = "application log with exported span_id"
            if required <= matched:
                return sources
            time.sleep(2)
        raise Error("LOG_CORRELATION_MISSING", "S09", ",".join(sorted(required - matched)),
                    "Chưa có app log mới với trace_id/span_id hợp lệ trong Loki.",
                    "Bổ sung logger lấy active context; proxy log không thay app log.")

    # Purpose: Kiểm riêng đường Collector→Tempo→Grafana và lọc privacy.
    # Syntax: a,b = ... unpack và gán nhiều giá trị theo thứ tự; số phần tử phải khớp.
    # Flow: Scrape/readiness → gửi synthetic OTLP span có db.statement → chờ trace đã lọc → query Loki.
    # Kiến thức liên quan: Synthetic backend probe không thay bằng chứng SDK/app; privacy processor phải bỏ SQL attribute.
    def backend_probe(self):
        self.targets()
        self.http.request(self.urls["prometheus"] + "/-/ready", raw=True)
        self.http.request(self.urls["tempo"] + "/ready", raw=True)
        self.http.get(self.urls["grafana"] + "/api/health")
        tid, sid = uuid.uuid4().hex, secrets.token_hex(8)
        now = time.time_ns()
        body = {"resourceSpans": [{"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "sre-backend-probe"}}]},
                  "scopeSpans": [{"scope": {"name": "sre-probe"}, "spans": [{"traceId": tid, "spanId": sid,
                  "name": "backend-only-not-application-proof", "kind": 2, "startTimeUnixNano": str(now), "endTimeUnixNano": str(now + 1000),
                  "attributes": [{"key": "db.statement", "value": {"stringValue": "SELECT synthetic_probe"}}]}]}]}]}
        self.http.request(self.urls["collector"] + "/v1/traces", "POST", body, expected=(200,))
        self.trace(tid, {"id": "backend", "services": ["sre-backend-probe"]})
        # Query actual log backend via Grafana; real app logs check Fluent Bit later.
        self.proxy("loki", "/loki/api/v1/labels")
        return {"trace_id": tid, "synthetic": True, "scope": "Collector→Tempo→Grafana only"}

    # Purpose: Kiểm queue RabbitMQ có consumer trước acceptance/deploy.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Secret refs → Basic auth trong RAM → management queue API → consumers>0 → inventory.
    # Kiến thức liên quan: Management API chỉ chứng minh consumer nền; AMQP trace edge mới chứng minh propagation của request.
    def rabbit(self):
        cfg = self.c["rabbitmq"]
        # Credentials resolved from existing app Secret if broker Secret key names differ.
        creds = secret(self.k, cfg["namespace"], cfg["secret"], [cfg["username_key"], cfg["password_key"]])
        auth = base64.b64encode((creds[cfg["username_key"]] + ":" + creds[cfg["password_key"]]).encode()).decode()
        base = self.f.open(cfg["namespace"], cfg["service"], cfg["port"])
        path = "/api/queues/" + urllib.parse.quote(cfg["vhost"], safe="") + "/" + urllib.parse.quote(cfg["required_queue"], safe="")
        queue = self.http.get(base + path, {"Authorization": "Basic " + auth})
        need(queue.get("consumers", 0) > 0, "CONSUMER_MISSING", "S04", cfg["required_queue"], "Không có consumer hoạt động.")
        return {"queue": cfg["required_queue"], "consumers": queue["consumers"]}

    # Purpose: Kiểm rule được nạp và evaluator/Alertmanager hoạt động.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Đủ required alerts + health=ok → Alertmanager status; notification_required → lỗi chưa hỗ trợ.
    # Kiến thức liên quan: Prometheus evaluator khác với receiver notification; không gửi alert test đến người thật.
    def alerts(self):
        payload = self.http.get(self.urls["prometheus"] + "/api/v1/rules?type=alert")
        rules = {r["name"]: r for group in payload["data"]["groups"] for r in group.get("rules", [])}
        need(set(self.c["required_alerts"]) <= set(rules), "ALERT_RULE_MISSING", "S10", "Prometheus", "Thiếu tracing alert rules.")
        for name in self.c["required_alerts"]:
            need(rules[name].get("health") == "ok", "ALERT_EVALUATION_FAILED", "S10", name, "Alert rule evaluation lỗi.")
        self.http.get(self.urls["alertmanager"] + "/api/v2/status")
        need(not self.c["notification_required"] or self.c["controlled_receiver_url"], "CONTRACT_INCOMPLETE", "S10", "receiver", "Thiếu receiver kiểm soát để test notification.")
        # Explicitly refuse an unimplemented notification gate rather than emit to humans.
        need(not self.c["notification_required"], "NOTIFICATION_NOT_SUPPORTED", "S03", "receiver",
             "V1 kiểm evaluator/Alertmanager; notification receiver chưa được nghiệm thu.")
        return {"rules": self.c["required_alerts"], "evaluation": "PASS", "notifications": "NOT_TESTED"}

    # Purpose: Đánh giá từng signal riêng cho request vừa gửi.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Trace graph → logs → mesh delta → app delta nếu khai báo; lưu PASS/FAIL theo signal và trả proof.
    # Kiến thức liên quan: Metric tổng không chứng minh riêng request; Redis/AMQP PASS chỉ đến từ DB/edge của contract.
    def verify_route(self, row, contract, before):
        proof = self.j.data.setdefault("signal_results", {}).setdefault(contract["id"], {})
        proof.update({"trace": "NOT_TESTED", "logs": "NOT_TESTED", "metrics": "NOT_TESTED", "application_metrics": "NOT_DECLARED", "scope": contract.get("scope", "application")})
        try:
            spans = self.trace(row["trace_id"], contract)
        except Error:
            proof["trace"] = "FAIL"
            self.j.save()
            raise
        proof.update({"trace": "PASS", "trace_id": row["trace_id"], "span_count": len(spans)})
        proof["rabbitmq"] = "PASS" if any(e["type"] == "rabbitmq" for e in contract.get("edges", [])) else "NOT_DECLARED"
        proof["redis"] = "PASS" if any(d["system"] == "redis" for d in contract.get("databases", [])) else "NOT_DECLARED"
        self.j.save()
        try:
            sources = self.logs(row["trace_id"], spans, contract, row["started"])
            proof["logs"] = "PASS"
        except Error:
            proof["logs"] = "FAIL"
            self.j.save()
            raise
        missing = {service.split(".")[0] if contract.get("scope") == "mesh-http-only" else service for service in contract["services"]}
        proof["metrics"] = "FAIL"
        self.j.save()
        end = time.monotonic() + min(90, self.k.runner.deadline.remaining(90))
        while time.monotonic() < end:
            for service in list(missing):
                value = self.counter(service)
                if value is not None and before.get(service) is not None:
                    need(value >= before[service], "METRIC_RESET", "S09", service, "Mesh counter reset trong acceptance.")
                if value is not None and value >= (before.get(service) or 0) + 1:
                    missing.remove(service)
            if not missing:
                break
            time.sleep(2)
        proof["metrics"] = "FAIL" if missing else "PASS"
        self.j.save()
        need(not missing, "METRIC_MISSING", "S09", ",".join(sorted(missing)), "Mesh counter chưa tăng sau probe.")
        proof["metrics"] = "PASS"
        proof["metric_scope"] = "mesh; aggregate delta is not exclusive to this probe"
        declared = contract.get("application_metrics", [])
        if declared:
            proof["application_metrics"] = "FAIL"
            self.j.save()
            end = time.monotonic() + min(90, self.k.runner.deadline.remaining(90))
            pending = list(declared)
            while pending and time.monotonic() < end:
                for metric in list(pending):
                    self.app_metric_fresh(metric)
                    value = self.scalar(metric["query"])
                    initial = before["app:" + metric["service"]]
                    need(value >= initial, "METRIC_RESET", "S09", metric["service"], "App counter reset trong acceptance.")
                    if value >= initial + 1:
                        pending.remove(metric)
                if pending:
                    time.sleep(2)
            need(not pending, "APP_METRIC_MISSING", "S09", contract["id"], "App counter chưa tăng sau probe.")
            proof["application_metrics"] = "PASS"
        self.j.save()
        return {"route": contract["id"], "trace_id": row["trace_id"], "span_count": len(spans),
                "services": sorted({s["service"] for s in spans}), "logs": sources, "metrics": "PASS_MESH",
                "application_metrics": proof["application_metrics"], "metric_scope": proof["metric_scope"], "scope": proof["scope"]}
