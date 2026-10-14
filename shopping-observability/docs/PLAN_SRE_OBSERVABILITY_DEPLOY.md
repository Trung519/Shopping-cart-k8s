---
title: Kế hoạch script triển khai và nghiệm thu toàn bộ observability
type: implementation-handoff
domain: kubernetes
status: implemented-runtime-verified-argo-rollout-untested
created: 2026-10-04
updated: 2026-10-04
source_reference: scripts/prometheus-grafana.py; docs/PLAN_FULL_SYSTEM_TRACING.md
trace_session: "20261004_075106"
---

# Mục tiêu và phạm vi bàn giao

Xây dựng một CLI Python để gắn hoặc cập nhật observability cho ứng dụng Kubernetes đã tồn tại: Prometheus, Alertmanager, Grafana, Fluent Bit, Loki, OTel Collector, Tempo; kiểm chứng instrumentation ứng dụng, Istio và dependencies Redis/PostgreSQL/RabbitMQ. Thành công phải dựa vào dữ liệu mới phát sinh từ request thật và khả năng truy vấn qua Grafana.

Phần review bên dưới ghi nhận thời điểm lập kế hoạch. Bộ script đã được triển khai và test ngày 2026-10-04; xem [kết quả thực thi](SRE_DEPLOY_TEST_RESULTS.md) và [cách dùng](../scripts/README.md). Sau sửa request logger, full application contract đã PASS trên request thật. Chưa thực hiện rollout Argo tổng quát vì source chưa commit/push và image cache toàn scope chưa được xác minh. Lần sửa logger có rollout riêng và journal trong lab. Không tự commit/push.

Bản sửa review tiếp theo đã xử lý 12 nhóm tồn đọng trong script, thêm regression tests và comment 4 phần cho toàn bộ 242 hàm Python/runtime/tests. 95 test tự động đạt; 8 flow thật đạt contract đã khai báo; test SSA ConfigMap thật xác nhận xóa field và phục hồi idempotent. Metric mesh/app, Collector loss UNKNOWN và giới hạn Argo integration được báo riêng; xem bảng đối chiếu review trong kết quả thực thi. Preflight dùng memory limits dương và digest proof; không dùng request RAM hoặc cache entry thiếu làm cam kết an toàn.

Ưu tiên profile `shopping-cart-local` dùng chart, namespace và Argo Applications sẵn có. Core phải nhận một application contract để dùng cho hệ thống khác, không rải tên shopping-cart trong logic. V1 dùng Argo CD; không chạy Helm install cạnh Argo trên cùng resource. Bootstrap cluster/Argo, DB migration, sửa business logic và nâng CRD/storage schema không thuộc giao dịch tự rollback của V1.

“Chuẩn SRE” ở đây là có phạm vi thay đổi, preflight, bằng chứng nghiệm thu, deadline, lỗi rõ, khôi phục có kiểm chứng. Không tuyên bố HA hay tuyệt đối không gián đoạn: stack hiện tại single replica/local storage; kiểm tra trước phải chặn thay đổi không có đường khôi phục an toàn.

# 1. Review script hiện tại

Đọc toàn bộ `scripts/prometheus-grafana.py` (394 dòng), chart/templates, cấu hình tracing/metrics, instrumentation Go/Python, kế hoạch full tracing và các helper liên quan trong `Artifacts/shopping-metrics-plan`.

Điểm giữ lại: subprocess argv; credentials Grafana chỉ trong bộ nhớ; không in render chứa Secret; kiểm tra remote SHA; render đúng values; UUID cho operation; optimistic concurrency bằng resourceVersion; prune=false; kiểm tra PVC; datasource proxy thật; port-forward ngẫu nhiên và chỉ dọn PID do script tạo.

| Mức | Vị trí | Vấn đề và hệ quả | Yêu cầu sửa |
|---|---|---|---|
| P1 | `prometheus-grafana.py:221`, `:261`, `:388` | Sync toàn Application; timeout/ngắt không dừng operation hay rollback. Cluster có thể tiếp tục đổi sau khi CLI báo lỗi. | Journal trước mutation; xác định đúng operation; termination có kiểm chứng; compensation theo resource. |
| P1 | `:265`, `:307`, `:384` | Chỉ nghiệm thu metrics/Grafana trong khi logs/traces cùng bị reconcile. Có thể báo thành công dù pipeline khác hỏng. | Acceptance theo mọi component bị thay đổi và toàn scope yêu cầu. |
| P1 | `:157` | Preflight thiếu baseline app, image availability, headroom rollout, kết nối dependency và recoverability. | Chặn trước mutation nếu không đủ điều kiện deploy/restore. |
| P1 | `:329` | Chỉ cần tồn tại time series HTTP, không tạo request và không ràng buộc thời gian. Metrics cũ hoặc proxy metrics có thể che thiếu instrumentation. | Request mới + trace/log correlation + metric delta có giới hạn thời gian. |
| P2 | `:315` | Required jobs không có Tempo/Collector; target biến mất hoàn toàn có thể lọt qua. `not down` lại làm target ngoài scope chặn deploy. | Expected target inventory theo profile, phát hiện cả absent/down; baseline và phạm vi rõ. |
| P2 | `:77`, `:273` | Timeout lặp cho từng workload; không có tổng ngân sách; stderr tới 1800 ký tự không được phân loại/redact. | Deadline tổng, timeout mỗi bước, retry có điều kiện, lỗi chuẩn và details đã lọc. |
| P2 | `:67`, `:158`, `:180`, `:205` | Namespace/repo/version/PV/tên workload cố định; regex YAML phụ thuộc format. | Config có schema, đọc YAML có cấu trúc, discovery có đối chiếu contract. |
| P2 | `:197`, `:214` | Bắt buộc Telegram cho mọi lần chạy nhưng rule RAM sai namespace chỉ cảnh báo. | Receiver theo profile; rule sai thuộc scope phải fail validate. |
| P2 | `:372` | Xử lý signal chỉ dọn process local, không có recovery khi crash/SIGKILL/reboot. | State bền vững, lock/lease, `recover` và resume có đối chiếu live state. |

Các điểm ngoài script cần làm cùng:

- `helmchart/files/alerts-spec.yaml:79` và `:81` lọc `namespace="monitoring"` trong khi stack dùng shopping-cart-observability. Sửa qua template values và kiểm thử rule, không chỉ đổi thông báo.
- `templates/_collector-config.tpl` cố định Tempo DNS; `templates/mesh-tracing.yaml` cố định 4 namespace và sampling 100%; datasource/scrape/Fluent Bit labels còn phụ thuộc môi trường.
- `values.yaml:278` pin Grafana PV hiện có. Profile lab giữ nguyên binding; profile mới không được mang UUID PV này sang cluster khác.
- Collector chỉ có **traces pipeline**. Logs hiện đi stdout → Fluent Bit → Loki; metrics đi scrape → Prometheus. Không bật OTLP logs/metrics theo thói quen.
- `configure-istio-tracing.py` merge mesh có resourceVersion nhưng chưa ghi snapshot/compensation; `assert` không phù hợp validation vận hành vì Python `-O` có thể loại bỏ.
- Helper cũ có logic nghiệm thu đáng tái sử dụng, nhưng hardcode paths/ports, dùng assert và evidence file từ lần trước. Không gọi nguyên xi như module production.
- `verify-full-tracing.py` ngừng chờ khi mới có bất kỳ span nào, có thể thiếu consumer đến muộn; kiểm logs tổng hợp có thể pass nhờ proxy dù một app không có log; metric failure absent được cho qua. Sửa theo contract bên dưới.
- Redis client spans đã có, nhưng additionalScrapeConfigs đang liệt kê RabbitMQ/Tempo/Collector/Istio, chưa thấy Redis exporter riêng trong phần cấu hình này. Phải discovery trước; nếu contract yêu cầu broker/cache metrics mà chưa có exporter, báo thiếu hoặc triển khai adapter được quản lý, không nhận client spans thay server metrics.

# 2. Kiến trúc và giao diện bàn giao

Một lệnh dùng chung, nhiều module nhỏ kiểm thử độc lập. Giữ `prometheus-grafana.py` thành compatibility wrapper sau khi core đạt nghiệm thu; thông báo rõ phạm vi triển khai, không thay đổi ngầm hành vi.

```text
scripts/
  observability.py                  # entrypoint, không mutation khi import
  requirements.txt                 # pin parser YAML + validator schema
  sre_observability/
    config.py, errors.py, runner.py
    inventory.py, preflight.py, plan.py
    journal.py, locks.py, rollback.py
    deploy/argocd.py, deploy/mesh.py
    verify/metrics.py, logs.py, traces.py, dependencies.py, alerts.py
    adapters/shopping_cart.py
  config/
    deploy.example.yaml            # tất cả input có comment
    deploy.schema.json
    profiles/shopping-cart-local.yaml
    contracts/shopping-cart.yaml
  tests/unit/, tests/integration/, tests/fixtures/
docs/
  SRE_DEPLOY_RUNBOOK.md
  APPLICATION_OBSERVABILITY_CONTRACT.md
  SRE_DEPLOY_VARIABLES.md
```

CLI đề xuất (chưa tồn tại): `plan`, `check`, `deploy --plan-id ID`, `verify --run-id ID`, `rollback --run-id ID`, `recover --run-id ID`, `status --run-id ID`.

- Không có subcommand: in help và thoát; không mặc định deploy.
- `plan/check`: read-only đối với cluster; render giữ trong bộ nhớ, không ghi Secret. `verify --read-only`: không tạo business data; báo NOT_TESTED cho flow cần mutation.
- Plan chứa SHA, config hash, contract hash, cluster identity fingerprint, danh sách resource/field sẽ đổi, mode sync, baseline hash, recovery strategy, TTL. Deploy từ chối plan stale/drift.
- `deploy` tự rollback mọi mutation đã ghi khi gate bắt buộc fail. Mọi bước cùng một transaction; không để những bước đầu trở thành “thành công vĩnh viễn”.
- Chỉ resume gate đã pass nếu bằng chứng còn mới, input hash đúng và live state chưa đổi. Không dùng evidence cũ để pass lần deploy mới.
- Log command/session vẫn qua trace trung tâm. Journal/report máy đọc đặt trong `Log_agents` với tên chứa run ID, ghi nguyên tử, quyền hạn chế; không thêm thư mục `.codex-trace`. Không lưu raw Secret, token, body, cookie, SQL hoặc manifest chứa dữ liệu nhạy cảm.

# 3. Input, fallback và kết nối

Ưu tiên: CLI rõ ràng > biến môi trường allowlist > config người dùng > profile > default an toàn. Discovery là nguồn fact; chỉ fill trường khai báo `auto` nếu có đúng một kết quả phù hợp. Không tự đổi cluster, namespace, credentials hay endpoint khi kết nối lỗi. In bảng effective config đã redact kèm nguồn từng giá trị trước deploy.

Phân biệt unset và empty; sai kiểu/range/URL thì fail, không fallback che lỗi. Input người dùng khai báo không hợp lệ không được âm thầm thay bằng default. Endpoint override phải thống nhất giữa producer và consumer, không chỉ sửa một chart.

## 3.1 Biến điều phối (tên đề xuất cho CLI)

| Biến/config | Default/fallback | Dùng ở bước | Ý nghĩa và nơi khai báo |
|---|---|---|---|
| `OBS_PROFILE` | shopping-cart-local | S00 | Chọn topology, namespace, contract; profile khác phải khai báo rõ. |
| `KUBE_CONTEXT` | k3d-lab-k8s trong profile lab; generic bắt buộc | S00–S12 | Truyền mọi kubectl; xác nhận fingerprint cluster, không chỉ tên context. |
| `ARGO_NAMESPACE`, `OBS_ARGO_APP` | argocd, shopping-observability | S01/S05 | Argo controller và existing Application owner. |
| `OBS_NAMESPACE`, `APP_NAMESPACES`, `DATA_NAMESPACE` | từ profile đã xác minh | S00/S01 | Obs: shopping-cart-observability; apps/payment/identity/gateway; data: shopping-cart-data. |
| `REPO_ROOT`, `CHART_PATH`, `VALUES_FILES` | path tương đối repo; lấy thứ tự từ Argo source đã đối chiếu | S02 | Render đúng cả global và service override; không bỏ local overrides. |
| `GIT_REVISION` | SHA đã review trong plan, không fallback HEAD mới | S02/S05 | Pin từng source; profile hiện dùng cùng SHA cho chart/values. |
| `REQUIRED_CAPABILITIES` | metrics,logs,traces,correlation,dependency_checks,alerts | S00/S09 | Full profile không hạ scope khi thất bại. Browser tracing khai báo riêng. |
| `DEPLOY_TIMEOUT_SECONDS` | 1800 | tất cả forward steps | Deadline toàn lượt; default đề xuất, chưa benchmark. |
| `STEP_TIMEOUT_SECONDS`, `TELEMETRY_WAIT_SECONDS` | 300,180 | S04–S10 | Bounded wait; telemetry phải chờ đủ graph, không chỉ span đầu. |
| `ROLLBACK_TIMEOUT_SECONDS` | 900 riêng | R00–R05 | Có ngân sách recovery kể cả forward deadline hết. |
| `HTTP_TIMEOUT_SECONDS`, `MAX_RETRIES` | 10,3 | verify | Backoff+jitter cho GET/timeout/429/5xx phù hợp; không retry blind POST. |
| `MAX_PARALLEL_ROLLOUTS` | 1 | S07 | Giảm rủi ro OOM, kiểm capacity trước mỗi app. |
| `MIN_FREE_MEMORY_MIB` | 1024 cho lab + kiểm surge thực tế | S01/S07 | Chặn nếu không đủ node/VM headroom; không coi ngưỡng đơn lẻ là sizing production. |
| `STORAGE_CLASS` | giữ class của PVC cũ; local-path chỉ profile lab | S01/S05 | PVC mới phải có class hợp lệ; không migrate PVC bằng fallback. |
| `TEST_BASE_URL`, `TEST_HOST` | bắt buộc từ contract/gateway discovery duy nhất | S04/S08 | Request qua route thật; không dùng /health làm business acceptance. |
| `TEST_AUTH_SECRET_REF` | không có credential default | S03/S08 | Secret reference hoặc credential provider; quyền test tối thiểu. |
| `ALLOW_TEST_WRITES` | false | S08 | Khi false không chạy checkout mutating; full contract cần flow đó thì BLOCKED trước deploy. |
| `ALERT_TEST_RECEIVER` | không default receiver ngoài | S10 | Webhook test trong cluster; gửi Telegram thật cần scope được cho phép riêng. |
| `PRUNE`, `ROLLBACK_ON_FAILURE` | false,true; không cho profile full vô hiệu rollback | S05/R00 | Compensation có ownership; prune=false không thay thế rollback. |

## 3.2 Biến ứng dụng và service observability

| Biến/cấu hình | Default/fallback | Dịch vụ và thao tác cần có |
|---|---|---|
| `OTEL_SERVICE_NAME` | service identity trong contract | Mỗi app riêng một tên; validate khớp span resource, không dùng unknown_service. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector.${OBS_NAMESPACE}.svc.${CLUSTER_DOMAIN}:4318` | Env app qua ConfigMap/chart; `CLUSTER_DOMAIN=cluster.local` trong lab, generic xác minh DNS. |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | http/protobuf | App → Collector HTTP 4318; grpc dùng 4317 nếu adapter hỗ trợ, không tự failover đổi protocol. |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | unset | Nếu dùng HTTP endpoint riêng thì phải đủ `/v1/traces`; ưu tiên signal-specific cần hiện rõ. |
| `OTEL_SDK_DISABLED` | false khi contract yêu cầu trace | False không chứng minh SDK có khởi tạo. Go/Python hiện bỏ tracing khi endpoint rỗng. |
| `OTEL_PROPAGATORS` | tracecontext | Inject/extract cả HTTP và message headers; không tự bật baggage chứa thông tin nhạy cảm. |
| `OTEL_RESOURCE_ATTRIBUTES` | service.namespace + deployment environment từ profile | Không nhét secrets hoặc user IDs; schema semantic convention theo phiên bản runtime. |
| `OTEL_TRACES_SAMPLER` | giữ cấu hình đã review; lab hiện always_on | Acceptance phải có cách thu trace xác định; production sampling cần explicit policy. |
| `OTEL_METRICS_EXPORTER`, `OTEL_LOGS_EXPORTER` | none,none cho stack hiện tại | Metrics scrape; logs stdout → Fluent Bit. Không gửi 2 signal này vào Collector traces-only. |
| `OTEL_BSP_MAX_QUEUE_SIZE`, `OTEL_BSP_MAX_EXPORT_BATCH_SIZE`, `OTEL_BSP_SCHEDULE_DELAY` | 512,128,1000ms theo adapter hiện có | Go/Python hiện hardcode một phần; đổi env không chắc có tác dụng. Adapter phải kiểm/chuẩn hóa code trước khi quảng bá biến này. |
| `JAVA_TOOL_OPTIONS` + agent initContainer/image | merge option agent, giữ JVM flags cũ | Order/payment/Keycloak: JAR tồn tại, hash đúng, non-root đọc được, image có trên node/registry. |
| `COLLECTOR_TEMPO_ENDPOINT` (chart input đề xuất) | `tempo.${OBS_NAMESPACE}.svc.${CLUSTER_DOMAIN}:4317` | Collector exporter; readiness + trace query end-to-end. |
| `LOKI_PUSH_URL` (chart input đề xuất) | `http://loki-gateway.${OBS_NAMESPACE}.svc.${CLUSTER_DOMAIN}/loki/api/v1/push` | Fluent Bit output; buffer/Tail DB, labels namespace đúng. |
| `PROMETHEUS_URL`, `LOKI_QUERY_URL`, `TEMPO_QUERY_URL` | service DNS derive, ports 9090/80/3200 | Grafana datasource provisioning; verifier dùng port-forward tạm riêng. |
| `GRAFANA_ADMIN_SECRET_REF` | shopmon-grafana-admin + key names hiện có | Grafana authentication; không reset password để vượt lỗi. |
| `ALERTMANAGER_CONFIG_SECRET_REF`, receiver refs | shopmon-alertmanager-config; shopmon-telegram nếu bật receiver này | Validate reference và routing; không in nội dung/token. |
| `MESH_TRACING_PROVIDER`, `MESH_LOG_PROVIDER` | shopping-otel,shopping-safe-logs | Kiểm mesh provider và effective proxy config; namespace Telemetry không đủ nếu provider chưa có. |

HTTP OTLP endpoint chung tự bổ sung `/v1/traces`; signal-specific URL được dùng trực tiếp. Hỗ trợ env khác nhau theo SDK: phải kiểm adapter runtime thực tế, không suy từ tên biến. [OTel exporter configuration](https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/), [OTLP specification](https://opentelemetry.io/docs/specs/otel/protocol/exporter/).

## 3.3 Redis, RabbitMQ, PostgreSQL và auth

| Kết nối | Biến/mapping hiện có | Default có điều kiện và kiểm chứng |
|---|---|---|
| BFF → Redis | `REDIS_ADDRESS`, `REDIS_DB`, `REDIS_PASSWORD` ref | Lab address redis-cart.shopping-cart-data.svc.cluster.local:6379; DB hiện 2. Preserve DB hiện có, không fallback DB0. |
| Basket → Redis | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` ref | Cùng service, port 6379; mapping DB theo runtime/config thực tế. Yêu cầu request cart tạo Redis client span. |
| App → RabbitMQ | `RABBITMQ_HOST/PORT/VHOST/USERNAME/PASSWORD` | Lab rabbitmq.shopping-cart-data.svc.cluster.local:5672, vhost `/`; credentials không default. |
| Java → RabbitMQ | `SPRING_RABBITMQ_HOST/PORT/VIRTUAL_HOST/USERNAME/PASSWORD` | Adapter ánh xạ cùng nguồn với RABBITMQ_*; lệch hai bộ thì fail trước rollout. |
| Prometheus → RabbitMQ | scrape host/port, TLS/auth refs nếu có | Lab rabbitmq-headless...:15692. AMQP 5672, metrics 15692, management API thường 15672 là ba mục đích khác nhau. |
| Rabbit consumer | exchange/routing key/queue/consumer service/required edge | Không đoán tên/khai báo queue; lab inventory.order-created có bằng chứng cũ, phải inventory lại. |
| Redis monitoring | exporter endpoint + Secret/TLS refs + expected series | Discover hiện có; absent thì báo MISSING_REDIS_METRICS nếu required. Không tự cài vào data stack ngoài plan. |
| App → PostgreSQL | `DB_HOST/PORT/NAME/USERNAME/PASSWORD` hoặc runtime-specific DSN refs | Port lab 5432; tên DB/service theo từng app. Không fallback mọi app sang cùng DB. |
| Auth BFF/payment/account → Keycloak | issuer, JWKS, audience, service port, role mapping từ adapter | Không tự thay issuer/auth policy. Chỉ validate URL/issuer/JWKS và test positive/negative được khai báo. |
| Dependency ngoài cluster | explicit DNS/port/TLS CA/serverName/credential refs | Giữ TLS verify; kiểm từ cùng network identity/policy với app, không lấy laptop TCP success làm bằng chứng. |

Secrets chỉ tham chiếu; không tự tạo username/password giả. Endpoint resolution/TCP chứng minh transport; auth handshake chứng minh quyền; request ứng dụng và span chứng minh app thật dùng dependency. Cần tách ba kết quả này trong report.

Mỗi input trong example phải có comment: **dùng ở step nào → đặt tại đâu → nối từ ai tới ai → default là gì → khi nào bắt buộc → thiếu thì mã lỗi nào**. Auto-generate bảng biến từ schema để tài liệu không lệch code.

# 4. Application contract: không đoán app đã instrument bằng thư viện

Contract mô tả workloads/container, runtime, service.name, namespace, chart/Argo owner, env mapping, expected log type, route probes, dependency edges và cleanup. Runtime detection hỗ trợ lựa chọn adapter; tiêu chuẩn pass là telemetry thật, không phải grep dependency file.

```yaml
# Ví dụ cấu trúc thiết kế; implement schema trước khi dùng.
routes:
  - id: products-read
    method: GET
    path: /api/v2/products
    expected_status: [200]
    writes: false
    required_services: [commerce-bff, product-catalog]
    required_edges:
      - {from: commerce-bff, to: product-catalog, transport: http}
      - {from: product-catalog, to: postgresql, transport: db}
    correlated_logs: [commerce-bff, product-catalog]
  - id: checkout
    writes: true
    requires: [isolated_test_identity, isolated_cart, cleanup_adapter]
    required_edges:
      - {from: order-service, to: product-catalog, transport: rabbitmq,
         queue: inventory.order-created, relation: exact_parent}
```

Paths/auth/body/cleanup phải đối chiếu router code khi implement. Ví dụ trên không cho phép tự tạo đơn thật hoặc tự nới role. Không có cách generic biết tất cả business flows bằng network probing; app khác cần contract mới.

| App/capability | Có gì trong repo | Code/config phải có nếu runtime probe thiếu |
|---|---|---|
| Go BFF/account/seller/basket | `internal/telemetry`; HTTP, Redis hooks/pgx theo service | Init trước phục vụ traffic, HTTP middleware/client transport, propagation, shutdown flush, log trong active context; instrument custom clients nếu thiếu. |
| FastAPI catalog | `src/product_catalog/telemetry.py`, SQLAlchemy/HTTPX/Pika | Instrument cả included routers, async clients và engine thật; inject/extract AMQP; Uvicorn access logger giữ trace/span IDs qua startup/concurrency. |
| Java order/payment/Keycloak | Agent/image config trong charts và integration | Agent được load vào JVM thật; preserve JVM flags; validate supported clients, log correlation app/mesh theo contract. Không sửa auth/business code trong deploy. |
| Frontend/Gateway | Mesh spans | Chứng minh HTTP qua proxy. Browser click/render tracing cần JS SDK + collection/CORS/privacy design riêng; không nhận proxy span thay browser span. |
| RabbitMQ background work | Producer/consumer instrumentation lịch sử | Publish headers đúng, extract trước tạo processing span, context kết thúc mỗi message; không đổi ack/retry semantics. |

Preflight phát hiện thiếu image/code/config rõ ràng thì dừng ngay, trước mutation. Không thể chắc chắn bằng static scan thì đánh dấu `UNVERIFIED`, thực hiện runtime gate sau deploy. Thiếu span chỉ cho phép kết luận **chưa có bằng chứng trace**, không kết luận chắc “thiếu thư viện”: nguyên nhân có thể sampler, exporter, network, service.name hoặc ingestion.

Sampling: probe tạo trace ID + parent ID ngẫu nhiên, W3C sampled flag. Nếu gateway reset context, phải có adapter thu ID/context mapping đáng tin cậy; không tự sửa trust boundary. Không tìm thấy trace không được chọn trace khác có sẵn. Nếu sampling policy không cho phép nghiệm thu xác định thì BLOCKED; không tự bật 100% toàn production.

# 5. Trình tự triển khai và gate dừng

| Step | Làm gì | Điều kiện qua / lỗi dừng | Hoàn tác nếu đã đổi |
|---|---|---|---|
| S00 Resolve | Đọc config/contract, validate, in effective inputs và scope | Thiếu biến bắt buộc → CONFIG_MISSING; scope full thiếu probe → CONTRACT_INCOMPLETE | Không mutation. |
| S01 Inventory | Context/fingerprint, RBAC, Argo owners, CRDs/versions, nodes/pressure/headroom, workload/image/PVC, services/Endpoints/NetworkPolicy | Cluster sai, owner xung đột, app required absent, thiếu recovery permission → BLOCKED | Chỉ giải phóng lock do run sở hữu. |
| S02 Render/plan | Parse dependency lock/version/digest; render đúng values/overrides; semantic diff resource/field | Mutable image, image cũ không phục hồi được, đổi PVC/CRD/schema không reversible → BLOCKED | Không mutation. |
| S03 Baseline/recovery gate | Business read probes; app health; dependencies; source desired vs live; lưu before state và inverse plan | Baseline app đã lỗi hoặc unknown drift không thuộc exception có bằng chứng → BASELINE_UNHEALTHY | Không mutation. |
| S04 Network/prerequisite | Kiểm app/dependency transport+auth; mesh provider; consumer topology; read-only telemetry baseline nếu có stack | DNS/TLS/auth sai; required consumer absent; thiếu image/instrumentation xác định → lỗi cụ thể | Dọn probe resources của run. |
| S05 Backend deploy | Resource plan cho Prometheus/Alertmanager/Grafana/Loki/Tempo rồi Collector/Fluent Bit theo DAG thực tế | Argo đúng operation/revisions; StatefulSet/Deployment/DaemonSet/PVC/endpoint sẵn sàng | Restore changed config/workloads; PVC giữ. |
| S06 Backend acceptance | Probe hạ tầng riêng có marker: OTLP trace, log transport; query backend/Grafana; targets/rules | Phân biệt lỗi pipeline và app; synthetic OTLP không chứng minh app instrument | Rollback S05. |
| S07 App/mesh attach | Mesh merge nếu thực sự cần; lần lượt config/instrumented image từng app; checksum rollout | observedGeneration, desired imageID/digest, available replicas, native sidecars, business readiness | Đảo ngược app changes trước backend changes. |
| S08 Real flows | Products, auth/account, seller, cart/Redis, order/payment read; checkout/AMQP bằng fixtures được cho phép | HTTP status/schema đúng, async completion trong deadline; cleanup đã đăng ký trước test | Business compensation rồi rollback workload/config. |
| S09 Telemetry graph | Query Tempo/Loki/Prometheus và Grafana theo marker/time window | Required service/span/log/metric/edge thiếu → fail cụ thể, không chấp nhận trace một phần | Rollback toàn transaction. |
| S10 Alert & regressions | Rules parse/load/evaluate; test receiver nội bộ; baseline request, error ratio/latency/restarts/pressure | Alert path hoặc app regression fail; ngoài receiver chưa test phải ghi rõ | Xóa rule/probe tạm do run tạo, rollback. |
| S11 Cleanup/stability | Cleanup fixture/session/probe/PID; cửa sổ ổn định đề xuất 120s; recheck app/dependencies | Cleanup thất bại → FAILED_CLEANUP; không SUCCESS | Giữ journal cleanup còn nợ; rollback nếu gate bắt buộc fail. |
| S12 Commit result | Ghi report redacted, coverage, revisions/imageIDs, status từng step; release lock | Chỉ full SUCCESS nếu toàn bộ required gates pass | Không tự Git commit/push. |

Thiếu app/consumer prerequisite biết được ở S01/S04 thì **không cài tiếp**. Nếu mất app sau S07 hoặc S09 mới phát hiện code chưa tạo spans thì dừng ngay và hoàn tác các bước đã làm.

Pre-existing ExternalSecret degradation: allowlist chính xác resource/condition có baseline; không blanket-ignore Application Degraded. Lỗi mới hoặc lỗi ảnh hưởng credentials/readiness phải fail. Selected sync success không đồng nghĩa toàn Application Synced/Healthy; báo riêng.

Capacity phải gồm surge replicas, Java agent init image, storage headroom và VM memory khi chạy lab. Không tự bật swap hoặc đổi limits để làm check xanh. Native sidecar có thể nằm trong initContainers với restartPolicy Always.

Argo full sync dùng khi plan toàn Application đã được review và hooks/dependencies cần thiết. Selected resources chỉ dùng khi prerequisites tồn tại và graph đã đủ: **hooks không chạy trong selective sync, thao tác không được ghi history để rollback kiểu thông thường**. Cần journal/compensation riêng. [Argo selective sync](https://argo-cd.readthedocs.io/en/release-3.1/user-guide/selective_sync/), [sync phases](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/).

# 6. Nghiệm thu telemetry: tiêu chí chống báo xanh giả

Mỗi probe lưu run ID, route ID, thời gian bắt đầu/kết thúc, status, trace/span IDs và metadata allowlist. Không lưu response body, cookies, token, credentials hay business records. Lấy baseline counter trước probe; dùng deadline monotonic, query window theo clock hệ thống đã kiểm tra lệch.

| Signal | Điều kiện PASS | Không đủ để PASS |
|---|---|---|
| HTTP/business | Request mới qua gateway đúng status + assertion contract, các service/dependency cần thiết thực sự được gọi | /health200; TCP connect; HTTP200 của mock/route sai. |
| Traces | Trace đúng marker; required app server/client spans, resource service.name đúng; graph parent-child đúng; dependency client spans đúng runtime | Trace chỉ có Envoy; span giả gửi trực tiếp Collector; bất kỳ trace cũ. |
| Logs | Log mới của **từng app required** trong Loki; trace_id đúng; span_id tồn tại trong trace đó nếu contract yêu cầu; kiểm log type cụ thể như access/completion | Một stream proxy có trace ID; log local chưa tới Loki; IDs tự bịa. |
| Metrics | Expected targets đủ, UP và fresh; series theo workload/route đúng; request counter tăng phù hợp giữa before/after, đủ scrape cycles | Job tồn tại nhưng thiếu replica required; một time series cũ; có vector nhưng value không hợp lệ. |
| PostgreSQL/Redis | Route kích hoạt operation thật; client span đúng app/dependency; kết quả app thành công; server metrics nếu contract yêu cầu | Database server span không tồn tại; Redis PING từ máy deploy thay cart/session request. |
| RabbitMQ | Publish thực và consumer thực xử lý fixture; correlation đúng parent/link; queue/consumer topology đáp ứng contract | Metrics broker UP, producer-only, queue không có consumer nhưng báo full. |
| Collector/Fluent Bit | Counter deltas/queue/backlog theo cửa sổ, restart/reset được xử lý; không có loss/refusal ngoài policy | So cumulative accepted==sent tức thời; metric missing được biến thành 0. |
| Grafana | Query qua từng datasource proxy, cùng trace/log/metric marker; derived-field regex/trace-to-logs query đúng | Datasource config tồn tại, dashboard có tên đúng nhưng không có dữ liệu. |
| Alertmanager | Rule đúng namespace/label, evaluator chạy, alert test tới receiver kiểm soát và resolved/cleanup | Rule loaded được gọi là đã gửi Telegram thành công. |

Rabbit generic contract hỗ trợ parent hoặc span links theo SDK/semantic convention; không ép mọi hệ thống phải chung trace ID. Riêng flow Java order → Python catalog hiện có regression contract `exact_parent`. Nếu dùng links, truy vấn được cả trace đích và kiểm liên kết thực. [OTel messaging spans](https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans/).

Coverage profile shopping-cart phải gồm BFF, account, seller, basket, catalog, order, payment, Keycloak; Gateway/frontend mesh riêng. Queue lịch sử không có consumer (inventory.order-cancelled, inventory.order-paid, audit.cart-events, audit.inventory-events) phải được inventory lại. Required consumer thiếu → BLOCKED; producer-only edge được contract khai báo trước thì ghi đúng phạm vi, không nâng thành full producer-consumer coverage.

Trạng thái gate: PASS / FAIL / BLOCKED / NOT_TESTED / NOT_APPLICABLE. Capability required không được NOT_TESTED. Optional capability không có phải giải thích. “Đầy đủ” là đầy đủ contract công khai; không phải lời hứa mọi endpoint/background job đều được bao phủ.

# 7. Rollback theo giao dịch có bù trừ

Không dùng `helm rollback` cho resource Argo render, không dùng blanket `kubectl rollout undo`, không xóa namespace hoặc `helm uninstall` stack cũ. Restore configuration/workload và business health trong scope; không hứa đảo ngược dữ liệu business đã phát sinh hoặc phục hồi storage bằng rollback YAML.

## 7.1 Trước mutation

1. Local lock + cluster Lease theo cluster/namespace/scope, run UUID; kiểm operation Argo khác và owner ApplicationSet. Nếu không thể tạo lease theo RBAC thì fail mutation mode.
2. Snapshot **các field được phép đổi**: UID/resourceVersion/generation, before values, field absence, image digest, source revisions, config fingerprints. Secret chỉ lưu reference/version; resource có inline secret → loại khỏi scope hoặc yêu cầu cơ chế bảo vệ được thiết kế, không dump snapshot.
3. Giải quyết drift: previous Git revision chỉ dùng restore khi render thật khớp baseline selected resources. Nếu live có thay đổi ngoài Git, phải có inverse patch hợp lệ hoặc BLOCKED.
4. Ghi journal `PREPARED` bền vững trước API write; sau write lưu `APPLIED` và observed identity/hash. Nếu mất response, query ownership/hash/operation UUID để biết đã apply hay chưa; không apply/revert mù.
5. Kiểm quyền và availability cho inverse operations, old images, old ConfigMap content. Cấm change có schema downgrade/PVC mutation không đảo được. Storage sinh mới mặc định retain.

## 7.2 Khi forward gate lỗi

- R00: đóng gate mới; chốt failed step/cause. Nếu Argo operation chính run còn chạy, terminate qua API/CLI được hỗ trợ và chờ terminal state. Không xóa `.operation` rồi giả định controller đã ngừng; không terminate operation của người khác.
- R01: hoàn tác test business bằng adapter idempotent, resource marker rõ; cancel/deactivate/logout theo API. Không purge database, queue hoặc lịch sử giao dịch. Side effects không thể đảo hết phải ghi residuals.
- R02: restore app image/config và mesh fields theo thứ tự phụ thuộc ngược. Giữ backend tới khi app phục hồi và flush xong; không tắt Collector trước app.
- R03: restore changed observability resources. New stateless owned resources có thể xóa nếu UID/ownership trùng; new PVC/PV, CRD, namespace mặc định giữ và ghi retained resources. Không xóa object pre-existing.
- R04: verify baseline configuration fields, imageIDs, rollout và business probes; xác nhận Secrets refs/PVC identity/binding không đổi, dependencies healthy, không có operation trôi.
- R05: cleanup probes/locks đúng ownership; lưu `ROLLED_BACK` hoặc `ROLLBACK_INCOMPLETE`, original failure và residual actions. Không bao giờ in SUCCESS sau forward failure dù rollback thành công.

Compensation phải idempotent, write-ahead như forward. Trước restore so UID + field hiện tại với after-state; người khác đã đổi thì không overwrite. ResourceVersion toàn object có thể đổi vì controller status: refresh và so đúng field, không ghi lại status/managedFields nguyên khối.

Crash/SIGKILL: lần `recover` đọc journal, xác định operation còn chạy và các PREPARED không rõ outcome, đối chiếu live state, tiếp tục compensation mặc định; không chạy lại business POST. SIGINT/SIGTERM chuyển sang recovery có deadline; second interrupt ghi incomplete; SIGKILL không bắt được nên cần journal.

Argo/ApplicationSet reconciliation: inventory cả parent/controller có thể sửa child. Với profile manual hiện tại, không cần tự tắt auto-sync. Profile auto-sync hoặc parent có thể đưa revision xấu trở lại phải **BLOCKED trước mutation** nếu chưa có chiến lược pause/pin ở nguồn quản lý thực sự và rollback nó. Không coi patch child Application là bền vững. Restore live baseline nhưng Git desired còn revision lỗi phải báo OutOfSync/reconciliation pending; chuẩn bị diff sửa desired state, không báo đã khôi phục GitOps hoàn toàn.

Nếu API server mất kết nối, lock mất, hoặc có người sửa field khi rollback: dừng phần xung đột, thực hiện những compensation độc lập còn an toàn, báo ROLLBACK_INCOMPLETE. Không thể đảm bảo phục hồi cụm bằng lời hứa khi control plane không truy cập được.

# 8. Lỗi ngắn, rõ và hữu ích

Tối đa 4–5 dòng mặc định: **mã + step + đối tượng + điều biết chắc → hành động → trạng thái rollback → report**. Không dump traceback/raw API body; `--debug` chỉ mở diagnostics đã redact. Icon thông dụng có text tương đương và `--no-color/--ascii` cho CI.

```text
❌ [TRACE_MISSING] S09 · product-catalog: chưa thấy server span sau 180s.
→ Kiểm tra SDK đang chạy, OTLP endpoint và sampling. Xem report mục catalog.
↩ Rollback: hoàn tất 4/4 thay đổi; request baseline trả 200.
📄 Report: <sanitized-report-path>

❌ [CONSUMER_MISSING] S04 · inventory.order-created: không có consumer hoạt động.
→ Khởi chạy consumer product-catalog rồi chạy check lại.
ℹ Cluster chưa bị thay đổi.

❌ [ROLLBACK_CONFLICT] R02 · commerce-bff: cấu hình đã bị thay bởi tác nhân khác.
→ Chưa khôi phục 1 resource. Xem report mục recovery; không chạy deploy lại.
ℹ Lỗi ban đầu: LOG_CORRELATION_MISSING tại S09.
```

Mã tối thiểu: CONFIG_MISSING, CONFIG_INVALID, CONTEXT_MISMATCH, RBAC_DENIED, OWNER_CONFLICT, BASELINE_UNHEALTHY, CAPACITY_LOW, APP_MISSING, CONSUMER_MISSING, IMAGE_UNAVAILABLE, DNS_FAILED, TLS_FAILED, AUTH_FAILED, DEPENDENCY_UNREACHABLE, ARGO_SYNC_FAILED, ROLLOUT_TIMEOUT, TRACE_MISSING, TRACE_EDGE_MISSING, LOG_MISSING, LOG_CORRELATION_MISSING, METRIC_MISSING, TELEMETRY_DROPPED, ALERT_TEST_FAILED, CLEANUP_FAILED, ROLLBACK_CONFLICT, ROLLBACK_INCOMPLETE.

Exit codes ổn định: 0=required gates pass; 2=config; 3=preflight blocked/no deploy mutation; 4=forward failed và restore hoàn tất; 5=recovery/cleanup incomplete; 6=verify-only failed; 130=user interrupt sau khi cleanup/restore hoàn tất. Nếu interrupt nhưng restore fail dùng 5. JSON report giữ original error, rollback result và interrupted flag riêng.

Retry chỉ cho lỗi có thể tạm thời; 401/403, sai schema, thiếu consumer không retry tới hết 15 phút. Timeout có step/object/elapsed/deadline. Lỗi raw không được khẳng định nguyên nhân “SDK thiếu” khi chưa có bằng chứng.

# 9. Các gói công việc cho người triển khai

| Thứ tự | Deliverable | Điều kiện nghiệm thu |
|---|---|---|
| P0 | Inventory adapter + config schema + example/comments + contract shopping-cart | `plan/check` không mutation, liệt kê input thiếu và scope cụ thể; đối chiếu mọi values override. |
| P1 | Command runner redaction/deadline + error catalog + durable journal/lock | Test log không có secret; crash giữa write và response có thể recover. |
| P2 | Argo deploy/restore engine, snapshot/inverse plan, ownership/CAS | Dry fixture + cluster test: lỗi step giữa rollback đúng baseline; giữ PVC/Secret. |
| P3 | Parameterize chart DNS/namespace/scrape/mesh + sửa rule RAM | Helm render lab giữ topology hiện có; profile namespace khác không còn references lab ngoài allowlist. |
| P4 | Backend verification metrics/logs/traces/Grafana/alerts | Cố ý chặn Collector→Tempo và Fluent Bit→Loki phải fail đúng mã; synthetic probe không pass app gate. |
| P5 | Real application probe adapters + dependency/async graph + cleanup | Products/Redis/SQL/RabbitMQ có bằng chứng mới theo contract, service-level log correlation. |
| P6 | Rollout app integration và instrumentation gap report | Có thể tái dùng code hiện tại; thiếu runtime code → báo cần sửa gì ở file nào, không tự sửa business. |
| P7 | Failure injection suite + runbook + compatibility wrapper | Toàn bộ bắt buộc bên dưới pass; operator dùng một entrypoint, report đầy đủ. |

Không bắt đầu deploy thật bằng cách mở rộng script 394 dòng rồi bổ sung rollback sau. Hoàn tất engine recovery/test trước khi bật mutation mode.

Tests bắt buộc:

1. Config precedence, unset/empty, invalid endpoint, thiếu Secret ref, không fallback credentials/TLS/context; snapshot/redaction không leak.
2. Required app absent và Rabbit consumer=0: chặn trước S05; optional producer-only có report chính xác.
3. Trace có proxy nhưng thiếu app span; đúng services nhưng parent sai; consumer tới muộn; trace ID hex/base64; messaging link contract.
4. App log có trace_id nhưng sai span_id, chỉ proxy logs, log cũ, concurrent requests lẫn context: đều không được pass.
5. Metrics cũ/empty/NaN/missing job/target mất; Collector metric absent và reset; queue tăng/exports fail có bounded wait.
6. Fault sau từng mutation S05/S07: DNS/NetworkPolicy/TLS sai, image pull/init JAR không đọc được, readiness timeout. Restore old image/config; baseline route phục hồi; PVC UID giữ.
7. SIGINT, SIGTERM, crash/SIGKILL, timeout giữa API write/response, Argo operation bị thay, lock mất, resume stale, concurrent operator update.
8. Rollback cũng fail: API outage, old image unavailable, field ownership conflict. Phải exit5, journal và action rõ, không ghi SUCCESS.
9. Test checkout fixture cleanup cả nhánh success/fail; retry không tạo đơn trùng; broker messages lịch sử không bị purge.
10. Full sync cần hooks và selected sync không hooks; ApplicationSet ownership; old operation Succeeded không pass operation mới; native sidecar readiness.
11. Chạy lần hai khi input không đổi: không restart workload không cần thiết; verify vẫn tạo bằng chứng mới; `rollback` gọi lần hai an toàn.
12. Telemetry backend outage không làm application mất readiness hoặc business request hỏng ngoài policy đã định; exporter timeout/queue bounded; capacity gates đủ surge.

Unit tests dùng recorded sanitized fixtures/fake clients. Integration/fault injection chạy cluster test biệt lập trước; không thử phá Collector/network trên lab đang phục vụ người dùng như bước review. Runtime acceptance thật chỉ sau khi plan triển khai được cho phép.

# 10. Definition of Done và bàn giao

- Một CLI, config schema/example có comment đầy đủ; profile lab + ví dụ app generic; biến app/backend/dependencies có mapping rõ.
- Mọi bước mutation có before-state, journal và inverse action được test; failure ở cuối rollback cả bước đầu trong scope.
- Required coverage đủ metrics/logs/traces/correlation, dependency edges và alerts; bằng chứng mới, không dùng file evidence lịch sử.
- Report có matrix từng service/flow/signal; changed/restored/retained/conflicted resources; rollback outcome; business health trước/sau; limitation rõ.
- Không deploy Grafana thứ hai; không tạo namespace monitoring thay namespace cũ; không đổi PVC binding hay credentials; không sync rộng data/security/root app.
- Không đánh đồng consumer chưa triển khai với lỗi observability. Không che thiếu code bằng synthetic spans. Không gọi mọi workload Ready là hệ thống đã observable.
- Chạy thành công + ít nhất các failure injection bắt buộc; kiểm privacy và recoverability. Chưa qua thì chưa gọi production-ready.
- Cập nhật README hiện có để bỏ đoạn scope tracing cũ mâu thuẫn với phần full-system ở cuối; giữ phần lịch sử có nhãn.

Giả định để người sau tiếp tục: ưu tiên stack shopping-cart hiện có; logs qua Fluent Bit; metrics scrape; traces OTLP; giữ Argo manual; business write probes opt-in; HA/browser RUM và migration độc lập. Nếu người dùng đổi các giả định này, cập nhật contract và scope trước, không tự suy diễn fallback.

Tham chiếu nội bộ: `docs/PLAN_FULL_SYSTEM_TRACING.md`, `docs/PLAN_TEMPO_OTEL.md`, `docs/PLAN_FLUENTBIT_LOKI.md`, `Memory/30_Runbooks/shopping-cart-tracing-acceptance.md`; helper ngoài repo chỉ dùng làm nguồn logic, chuyển phần cần thiết vào module và test trước khi sử dụng lâu dài.
