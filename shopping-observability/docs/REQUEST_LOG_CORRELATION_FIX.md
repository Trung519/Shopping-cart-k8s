---
title: Request log correlation fixes for Java applications
type: implementation-validation
domain: kubernetes
status: runtime-verified-git-reconciliation-pending
created: 2026-10-04
updated: 2026-10-04
trace_session: "20261004_075106"
---

# Nguyên nhân và cách sửa

Order/payment đã có agent và console format `trace_id`/`span_id`, nhưng route GET không ghi request log. Thêm `RequestCompletionLoggingFilter`: ghi method, status, outcome và duration khi request kết thúc, lúc application span còn active. Không đọc/log headers, query, body hoặc nội dung exception. Không lấy ID từ header để giả correlation. Agent bổ sung ID vào logging event MDC; không thêm thư viện runtime.

Keycloak chạy **24.0.5**, không có các access-log option mới của Keycloak 26. Bật Quarkus access logger qua `conf/quarkus.properties`; format message chỉ method/status. `KC_LOG_CONSOLE_FORMAT` xuất `trace_id`/`span_id` từ JBoss MDC. Thêm checksum config vào Helm template để lần thay config sau có rollout. Cấu hình mặc định và local image tags đã cập nhật trong source.

Tham khảo: [OpenTelemetry logging MDC](https://github.com/open-telemetry/opentelemetry-java-instrumentation/blob/main/docs/logger-mdc-instrumentation.md), [JBoss MDC instrumentation](https://opentelemetry.io/docs/zero-code/java/agent/disable/), [Keycloak Quarkus configuration](https://www.keycloak.org/server/configuration). Cách dùng ở đây đã kiểm tra trên bản Keycloak 24 đang chạy; không áp option mới dựa riêng vào tài liệu phiên bản mới.

## Test và rollout lab

- Compiler/test harness sử dụng đúng libs của image baseline: success/exception, exception giữ nguyên, mỗi request một log, không đọc dữ liệu riêng và không sửa response — PASS cho cả order/payment.
- Bộ **48/48 test script** (thêm test mount/checksum Keycloak) — PASS. Helm lint/render của ba chart — PASS.
- Hai image chỉ bổ sung class logger vào baseline; **không phải full Maven rebuild hoặc toàn bộ business tests**.
- Image mới: `shopping-cart-order:v1.1.2-request-log-20261004`, `shopping-cart-payment:v0.1.3-request-log-20261004`, ARM64; đã import vào ba node lab.
- Rollout tuần tự với maxSurge=0 do RAM thấp; chiến lược gốc đã phục hồi khi Ready. Không sửa Secret/PVC/DB schema.

Journals tại `Agent_setup/Log_agents`:

| Service | Journal |
|---|---|
| Order | `obs-request-log-fix-c25926cd25e346bea35f36ed515ec527.json` |
| Payment | `obs-request-log-fix-58af7f3c20144697a7f7e2376514e1e7.json` |
| Keycloak | `obs-request-log-fix-18426e0c2fac4e4298db1695a437184b.json` |

Lượt nghiệm thu mới: `obs-run-24f1f7f3bac241d285967b9711cce378.json` — **exit 0, VERIFIED**, không có acceptance failure. Cả tám flow frontend HTTP, products, accounts, seller, cart, orders, payment và checkout PASS. Accounts/Keycloak, orders và payment đều có app log chứa trace_id/span_id tồn tại trong trace mới. Metrics/logs/traces/RabbitMQ/Redis PASS; alerts chỉ PASS evaluator, chưa gửi notification ngoài. Frontend vẫn là mesh HTTP, không tuyên bố browser tracing.

Cleanup PASS, fixtures CLEANED. Cả 14 PVC giữ nguyên UID/volume so với baseline trước sửa. Ba journal hotfix đã ghi VERIFIED và reference report; after-state/UID vẫn khớp, Lease đã nhả.

## Đồng bộ Git và hoàn tác

Đây là sửa/test trực tiếp có journal trong lab; **chưa commit/push**, Argo auto-sync đang tắt. Sync revision cũ có thể đưa image/config cũ trở lại. Review rồi commit/push source trước lần GitOps sync tiếp.

Helper giới hạn cho lần sửa này ở `Agent_setup/Artifacts/observability-request-log-fix/apply_fix.py`. Nếu cần hoàn tác, chạy qua `run_logged.sh`: Python trong `.venv` của script, helper `rollback /absolute/path/to/journal.json`. Helper kiểm cluster UID, resource UID/after-state và dùng Lease; conflict sẽ dừng, không overwrite thay đổi của người khác. Đây không phải entry point deploy tổng quát.
