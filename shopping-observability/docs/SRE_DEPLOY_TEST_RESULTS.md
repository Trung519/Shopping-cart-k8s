---
title: Observability SRE script test results
type: validation-artifact
domain: kubernetes
status: application-contract-verified-argo-rollout-untested
created: 2026-10-04
updated: 2026-10-04
trace_session: "20261004_075106"
---

# Kết quả ngày 2026-10-04

## Bản sửa bám sát review và plan

**95/95 test tự động PASS**, gồm 47 regression cases thêm sau review. **242/242 hàm** trong Python scripts và tests có comment đủ Purpose, Syntax, Flow, Kiến thức liên quan; audit xác nhận chỉnh comment không đổi AST thực thi. Không thêm thư viện; vẫn chỉ PyYAML 6.0.3.

| Review cần sửa | Bản sửa | Kiểm chứng |
|---|---|---|
| 1. PVC lệch thứ tự gây lỗi giả | Chuẩn hóa namespace/name/UID/volume cho plan, deploy và journal cũ khi recover | Đổi thứ tự đạt; đổi UID/volume bị chặn |
| 2. Recover nhả Lease trước khi kiểm đủ | Chỉ `ROLLED_BACK` sau resource, cleanup, HTTP anonymous, readiness và PVC; lỗi/ngắt lúc nhả Lease → INCOMPLETE/exit 5 | CLI giữ Lease khi baseline lỗi; session test không che lỗi public baseline; lease release bị ngắt không báo thành công |
| 3. Cleanup lỗi chặn restore | Dừng Argo → restore configs/workloads → retry cleanup → verify baseline | Kiểm thứ tự; deploy cleanup lỗi rồi recover đủ trả exit 4 và nhả Lease |
| 4. Fixture crash/mất response | Tìm SKU chính xác có phân trang; verify order cancelled/product inactive; save business evidence trước xóa user | Product ở page sau, thiếu pagination, product chưa inactive, logout/user-delete mất response |
| 5. Readiness bỏ sót | Restore idempotent vẫn wait; CR cần Reconciled đúng generation và child owner/revision/Ready | Operator chậm, child cũ/unready/sai owner không đạt |
| 6. Không thấy field bị xóa | Đọc managedFields/last-applied, so removal theo ownership; ConfigMap data quản lý toàn bộ; verify sau apply; xử lý replica default đã nhả ownership; compensation giữ Argo attribution | ConfigMap/spec/annotation/named-list removal; API defaults; restore không làm field bị bỏ qua ở plan sau; SSA xóa key và rollback thật khôi phục key |
| 7. Ước lượng RAM thiếu surge/sidecar | Dùng limits dương; tính replicas/maxSurge/terminating overlap, native init sidecar, admission và operator companion budget | Percentage/integer/Recreate, init chạy đồng thời, injected budget; thiếu/zero limit dừng rõ |
| 8. HTTPS/redirect bypass | Guard scheme/host/port trước request/form POST và mỗi redirect; chặn HTTPS V1; strip credential cross-origin OIDC; backend redirect phải cùng origin | Host/port/scheme/userinfo sai không gửi mạng; auth header không theo redirect ra ngoài |
| 9. Credential lọt journal | Schema + recursive JSON/YAML/env/annotation guard cho API_KEY/client_secret và các tên nhạy cảm; Secret refs giữ nguyên | Refused trước tạo file; stderr phân loại không chứa fake sensitive value |
| 10. Cache image không đủ bằng chứng | Chuẩn Docker Hub/library/digest; eligible nodes; lưu digest proof, revalidate trước deploy; unknown khác nonexistent; Always yêu cầu digest | Cache thiếu/digest conflict chặn; latest ngầm bị loại; alias tag+digest chuẩn hóa đúng |
| 11. Metrics/loss báo quá phạm vi | Tách mesh/app metrics; app counter+freshness query optional nhưng đã khai báo là required; kiểm scrape age/reset/ambiguous sample; missing loss series → UNKNOWN; counter chưa có thì gửi một GET khởi động và chờ scrape trước đo baseline | Metric lỗi giữ trace/log đã đạt; mesh không nhận là app metric; reset/loss/missing có evidence riêng; không phát lại request POST/checkout để khởi động counter |
| 12. Contract/report thiếu validation | Validate routes/checkout/ID/types/relations; coverage theo proof từng signal; Redis/Rabbit chỉ từ declared DB/edge | Contract sai bị chặn trước fixture; không bịa dependency PASS; log cùng service/span ID nhưng trace khác không đạt |

Argo vẫn là writer khi deploy. Bản sửa bật `ClientSideApplyMigration=true` cùng SSA để chuyển ownership legacy, và chặn Replace/Force/hook/override apply không hỗ trợ; đối chiếu [tài liệu Argo CD về migration và sync options](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/#client-side-apply-migration). API `managedFields` được đọc rõ bằng `--show-managed-fields=true`. **Migration/rollout của controller Argo thật chưa được nghiệm thu**; test API giả và SSA Kubernetes thật không thay phần này.

Port-forward được tái sử dụng theo namespace/service/port; thông báo command dùng mã lỗi và thông điệp cố định, không đưa raw stdout/stderr vào report.

## Kiểm chứng trên cluster thật

Lượt cuối `obs-run-c6142c424dc44115b841913623c12f23.json`: **8 flow đạt, exit 0, state VERIFIED, fixture CLEANED**. Trace/log correlation của accounts/Keycloak, orders và payment đều đạt. Coverage: traces/logs/Redis/RabbitMQ PASS; mesh_metrics PASS; metrics MESH_ONLY; application_metrics NOT_DECLARED; alerts PASS_EVALUATOR_ONLY. Collector thiếu `exporter_enqueue_failed_spans` nên loss_evidence UNKNOWN. Lượt trước `obs-run-6b245a95231c467ca109ffb171244aba.json` cũng đạt cùng 8 flow.

Rollback mới `obs-live-rollback-2e72bad5f0644ff68e4aa285bfb1c799.json`: SSA thật sửa endpoint và xóa key obsolete → đọc journal PREPARED → restore đầy đủ data/UID → rollback lần hai an toàn → ConfigMap test được xóa. State `RESOURCES_RESTORED` đúng phạm vi test resource; không tuyên bố full app recovery. `test_cleanup` và `field_removal` đều PASS.

Audit comment: `Log_agents/observability-final-comment-audit-20261004.json`. Nhật ký lệnh và reports nằm trong `Agent_setup/Log_agents`, không chứa credential literal.

Kiểm baseline cuối `Log_agents/observability-final-baseline-20261004.json`: workloads/dependencies/storage Ready, **14 PVC giữ nguyên UID/volume**, và managedFields đọc được từ API thật.

**Chưa nghiệm thu rollout/rollback Argo tổng quát**, browser tracing, app metric chưa khai báo hoặc gửi notification ra ngoài. Source còn thay đổi chưa commit/push; script giữ guard này. Cần memory limits, explicit CR image khi đổi version và image digest/cache proof đủ trước khi tạo plan deploy mới. Không tự commit/push, không thay source guard để chạy test.

## Bằng chứng trước bản sửa review

Lượt nghiệm thu sau sửa logger trước đó đạt contract đang cấu hình, exit 0; fixtures CLEANED. [Chi tiết logger](REQUEST_LOG_CORRELATION_FIX.md). Lượt `obs-run-24f1f7f3bac241d285967b9711cce378.json` có tám flow PASS và 48/48 test tự động PASS; lần sửa logger có rollout riêng với journal trong lab.

Bảng dưới ghi nhận lượt test **trước khi sửa logger**, để giữ bằng chứng script phát hiện lỗi đúng và không dùng log proxy thay app log.

| Kiểm tra | Kết quả |
|---|---|
| 46 test offline/API giả lập/Helm render | PASS |
| Rollback ConfigMap riêng trên cluster thật; khôi phục UID/data, chạy lại an toàn, xóa fixture | PASS |
| Request frontend HTTP qua mesh | PASS; chưa kiểm browser clicks |
| Products, seller, cart, checkout | PASS: traces/spans và log correlation theo contract |
| Checkout RabbitMQ producer → consumer, Redis/SQL | PASS |
| Accounts / Keycloak | FAIL: `LOG_CORRELATION_MISSING` |
| Orders / order-service | FAIL: `LOG_CORRELATION_MISSING` |
| Payment / payment-service | FAIL: `LOG_CORRELATION_MISSING` |
| Cleanup lượt full verify cuối | PASS; user test xóa, product deactive, order cancel |
| Rule evaluator + Alertmanager health | PASS; chưa gửi notification ra ngoài |
| Deploy với source chưa commit/push | Chặn tại S02, exit 3; chưa mutation |
| Rollout và rollback Argo thật | CHƯA TEST; source/image prerequisites chưa đạt |

46 test bao gồm crash/lost-response recovery, rollback conflict/UID/resourceVersion, restore config trước workload, operation cũ/khác run, secret redaction, token hết hạn khi cleanup, trace/log giả hoặc proxy-only và template chart. `git diff --check` đạt.

## Bằng chứng

Report nằm ở `Agent_setup/Log_agents`:

- Full verify: `obs-run-f357c9c2a83747f0a978846da6267779.json` — exit 6, `S11_CLEANUP` PASS, fixture `CLEANED`.
- Live rollback kiểm tra cuối: `obs-live-rollback-d4b02026042042d2a4b03619235a4c9a.json` — PASS, ConfigMap đã xóa.
- Preflight deploy: `obs-run-2f75ff4343ec40718cd9d4b43d47f1c0.json` — `SOURCE_NOT_COMMITTED`, chưa thao tác resource.

Metric Collector không xuất series được giữ là unknown, không suy ra bằng 0. Lịch sử đơn/message test được giữ có chủ đích. Các fixture lỗi từ lượt thử trước đã recover và cleanup.

## Các bước tiếp theo

1. Logger cho ba flow đã sửa và test PASS; xem [bản sửa](REQUEST_LOG_CORRELATION_FIX.md). Không cần hạ yêu cầu nghiệm thu.
2. Commit/push chart đúng Argo revision, xác minh image deploy/rollback trên node, tạo plan mới.
3. Lượt `verify --allow-test-writes --collect-errors` mới đã PASS. Sau khi source/image prerequisites đủ, mới thử deploy và fault injection Argo trong môi trường thử nghiệm.

Python chỉ cần **PyYAML 6.0.3** để đọc YAML config/contract/Helm manifest. Không thêm SDK Kubernetes, requests hay jsonschema; HTTP/CLI/journal dùng thư viện chuẩn. V1 quản lý stack sẵn có, không bootstrap cluster trắng, migrate storage hay tự sửa business code.
