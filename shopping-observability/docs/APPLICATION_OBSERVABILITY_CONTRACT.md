---
title: Application observability contract
type: implementation-reference
domain: kubernetes
status: implemented
created: 2026-10-04
updated: 2026-10-04
---

# Khi nào ứng dụng được coi là đã kết nối observability?

Contract ở `scripts/config/contracts/shopping-cart.yaml` khai báo route, status, services, logs và dependency edges cần có. Một request mới phải tạo trace đúng ID, đủ app spans và parent-child; logs từng app có trace_id/span_id tồn tại trong trace; counter mesh tăng sau scrape mới. Proxy log không thay app log. Frontend được khai báo riêng là mesh HTTP, không nhận browser tracing.

Counter Istio là **mesh metric tổng**, có thể tăng do traffic khác; không chứng minh metric của app hoặc riêng probe. Profile hiện tại báo `metrics: MESH_ONLY`, `application_metrics: NOT_DECLARED`. Thiếu Collector loss series báo `UNKNOWN`, không nhận là zero loss.

Để yêu cầu app metric, thêm vào **route tương ứng** (tên metric bên dưới là ví dụ; thay bằng counter app thực sự export):

```yaml
application_metrics:
  - service: product-catalog
    query: 'sum(app_requests_total{service="product-catalog"})'
    freshness_query: 'time() - min(timestamp(app_requests_total{service="product-catalog"}))'
```

`query` cần trả đúng một counter tổng; `freshness_query` trả tuổi scrape của series gốc bằng giây. Script yêu cầu scrape dưới 90 giây, counter tăng sau request và không reset. Query được khai báo sẽ trở thành gate bắt buộc; metric thiếu sẽ FAIL riêng, không làm logs đã đạt biến thành FAIL. `application_metric_services` trong coverage ghi phạm vi app metric đã yêu cầu.

Contract được kiểm trước fixture: ID duy nhất, kiểu field, checkout adapter, services/logs tương ứng, DB/HTTP/AMQP relations hợp lệ. Redis/RabbitMQ chỉ PASS nếu route khai báo và trace mới có DB/producer-consumer proof tương ứng.

| Signal thiếu | App cần bổ sung | Nơi kiểm trong repo |
|---|---|---|
| Go HTTP trace/log | SDK init, HTTP middleware/client transport, log từ active span context | `commerce-bff/internal/telemetry`, các service `internal/telemetry` tương ứng |
| FastAPI/SQL trace/log | Instrument included routers, SQLAlchemy engine, HTTPX; logger/access formatter lấy context đúng | `shopping-cart-product-catalog/src/product_catalog/telemetry.py` |
| Java HTTP/JDBC trace | Agent được load vào JVM, JAR non-root đọc được, env endpoint/sampler đúng | order/payment deployment charts; Keycloak integration chart |
| Java request log correlation | Emit request/access completion log có trace_id và span_id của active app span; chỉ có agent không đảm bảo có log | cấu hình logger/request filter của order/payment/Keycloak; không dùng log startup thay request log |
| Redis spans | Hook đúng Redis client/pipeline và truyền context từ request | BFF/basket `internal/telemetry/redis.go` |
| RabbitMQ edge | Inject producer context vào headers, extract ở consumer; không đổi ack/retry | Java producer và Python Pika adapter |

Tên `OTEL_SERVICE_NAME` phải khớp contract. Go/Python hiện bỏ tracing nếu endpoint rỗng. Stack hiện gửi logs stdout → Fluent Bit → Loki, metrics scrape → Prometheus, traces OTLP → Collector → Tempo; `OTEL_LOGS_EXPORTER`/`OTEL_METRICS_EXPORTER` giữ `none` theo cấu hình hiện có.

Trace thiếu chỉ chứng minh chưa có telemetry yêu cầu, không đủ kết luận thư viện chưa cài. Kiểm sampling, endpoint, exporter và route thật trước. Consumer chưa triển khai là prerequisite thiếu, script không tự tạo business consumer.

Contract custom được đọc từ YAML; generic route probes hiện hỗ trợ GET. Fixture auth/checkout chỉ có adapter shopping-cart. Cần adapter/cleanup riêng trước khi áp dụng write tests cho application khác.
