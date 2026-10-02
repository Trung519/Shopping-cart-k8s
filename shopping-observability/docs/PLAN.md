---
title: Shopping Cart Observability Plan
type: execution-plan
status: completed-current-stages
created: 2026-10-02
updated: 2026-10-02
domain: kubernetes
---

# Observability — kế hoạch đã sửa theo chart hiện có

## Cấu trúc đúng

- Namespace duy nhất cho bộ giám sát: `shopping-cart-observability`.
- Argo CD Application hiện có: `shopping-observability`.
- Git: https://github.com/Trung519/Shopping-cart-k8s.git, branch `dev`.
- Helm chart hiện có: `shopping-observability/helmchart`, version 0.4.0.
- Metrics là dependency `metrics` (kube-prometheus-stack 91.8.2) trong chart này.
- Không dùng namespace `monitoring`, không tạo application `shopping-metrics`.
- Loki/Fluent Bit đã bật lại qua chart/Argo; chi tiết thực thi, lỗi/sửa và bằng chứng ở [PLAN_FLUENTBIT_LOKI.md](PLAN_FLUENTBIT_LOKI.md).
- Grafana riêng của chart cũ tắt; Grafana trong metrics dùng lại dữ liệu hiện tại.

## Nhật ký sửa sai — 2026-10-02

1. Người dùng sửa yêu cầu: hủy xóa namespace cũ, chuyển toàn bộ bộ metrics về namespace đúng.
2. Xác minh namespace cũ còn nguyên, không có pod chạy. Chưa có lệnh xóa namespace cũ.
3. Sửa chart/project/ApplicationSet hiện có; lint/render thành công. Không tạo chart/application mới.
4. Commit `de6d0cc` đã push `dev`: values, rules, dashboard, Telegram template và dependency đã nằm trong Git.
5. Sao chép ba Secrets cluster-to-cluster trong bộ nhớ, không ghi token/chat ID/password ra file/log/Git.
6. Ba PV được đổi Retain; dừng writers, uninstall release `shopmon` tại `monitoring`, chuyển claimRef sang namespace đúng.
7. Cả ba PVC mới Bound vào đúng PV gốc; không tạo storage trắng. PVC Grafana lịch sử `grafana` 2Gi vẫn nguyên.
8. Apply project/ApplicationSet đã cập nhật và sync riêng application `shopping-observability`, không prune.
9. Đã hoàn tất kiểm tra sau sync; kết quả và lỗi đã xử lý ghi bên dưới.

### Kết quả và lỗi đã xử lý

- Lần sync đầu bị giới hạn annotation CRD 262144 bytes. Sync bằng SSA rõ ràng; Argo CD 3.5 dùng `ClientSideApplyMigration=false`.
- `syncStrategy.apply` bỏ qua Helm hooks, dẫn tới thiếu Secret chứng chỉ `shopmon-admission`; chuyển sang strategy hook và tạo chứng chỉ thành công.
- Dependency Grafana đổi tên theo release lúc chuyển. Đã cố định fullname `shopmon-grafana`, quay về đúng PVC/PV gốc.
- PVC Bound không được đổi volumeName về rỗng. Đã khai báo đúng PV Grafana trong values; không xóa/recreate PVC chứa dữ liệu.
- Đã dọn đúng các resources/PVC trống `shopping-observability-grafana` tạo trong lần sync lỗi. Không xóa PVC lịch sử `grafana`.
- Argo: `shopping-observability` Synced / Healthy / Succeeded tại revision `b083c3d`; Git clean sau push.
- 8 pods Ready, 0 restarts sau migration. Ba PVC metrics Bound vào PV gốc, Retain; PVC Grafana lịch sử 2Gi còn nguyên.
- Grafana authenticated API xác nhận dashboard 8 panels; ba port-forward mới trỏ về namespace đúng.
- Prometheus truy vấn được 11 pod series lịch sử của namespace monitoring trong cửa sổ 2h, xác nhận lịch sử metrics được giữ.
- Telegram: đã thấy tin ShoppingNotificationTest mới trên UI khoảng 21:01; receiver reload successful=1, telegram notifications_total=1 và mọi failure reason=0. Đã xóa rule thử.
- `/login` và API products trả HTTP 200. Traffic được tạo bằng GET thật, không mock metrics: 180/180 requests trả HTTP 200, không network error.
- Sau dọn resources tạm: 33/33 targets UP (11 Istio; thêm frontend đã phục hồi). RPS product-catalog ~0.604, commerce-bff ~0.656; p95 ~27.3ms / 37.7ms, p99 ~58.3ms / 82.1ms. Snapshot, không phải benchmark.
- Rule thử đã xóa, ALERTS test Firing không còn trong Prometheus. Alertmanager có thể giữ trạng thái đến expiresAt và gửi resolved; không có rule phát sinh test mới.
- Commit tài liệu cuối `7e0ecc3` đã push dev; không thay đổi render so với revision deploy thành công `b083c3d`.
- Kiểm tra cuối sau hard refresh: Argo Synced / Healthy / Succeeded, cả hai source revisions là `7e0ecc32a106ec9628ffaf20f7b92bd3804e965d`. Grafana datasource proxy thực thi PromQL thành công, xác nhận 33 targets UP qua chính datasource dashboard.
- Đã kiểm kê toàn bộ namespaced API resources của monitoring, không có lỗi inventory; chỉ còn cấu hình của lần cài nhầm, không còn pod/PVC. Đã xóa đúng namespace monitoring; namespace shopping-cart-observability còn nguyên.
- Log: `Log_agents/command_logs_20261002_174737.log` và `Log_agents/session_logs_20261002_174737.log`.

## Quản lý bằng Argo CD

Sửa chart hiện có trong Git → lint/render → commit/push `dev` → Refresh/Diff/Sync application `shopping-observability`.
ApplicationSet giữ manual sync, bật ServerSideApply riêng cho observability. Không sync cả root/services để thử một thay đổi metrics.
Sync options hiện có: `CreateNamespace=true`, `ServerSideApply=true`, `ClientSideApplyMigration=false` (Argo CD 3.5).
Sync phải chạy hooks để tạo/cập nhật chứng chỉ admission; khi dùng operation qua Kubernetes, chọn `syncStrategy.hook`, không chọn `apply`.
Không chạy Helm install/upgrade riêng cho dependency metrics. Sau bàn giao, Argo là bộ quản lý resource.
Giữ prune tắt đến khi kiểm tra rõ PVC và resources lịch sử; không xóa cascade application.

Ví dụ lệnh terminal (mọi lệnh phải qua run_logged.sh):

```sh
TRACE=/Users/phamquangtrung/Documents/Agent_setup/System/tools/run_logged.sh
REPO=/Users/phamquangtrung/Documents/Agent_setup/Artifacts/shopping-cart-k8s-publish
$TRACE helm lint "$REPO/shopping-observability/helmchart"
$TRACE kubectl --context k3d-lab-k8s -n argocd annotate application shopping-observability argocd.argoproj.io/refresh=hard --overwrite
# Review Diff in Argo CD, then Sync only shopping-observability.
$TRACE kubectl --context k3d-lab-k8s -n shopping-cart-observability get pods,pvc
```

## Mở UI trên Mac

UI hiện được mở bằng `kubectl port-forward`, bind mặc định vào loopback của Mac. Không có NodePort/Ingress/Istio Gateway cho các UI này.

```text
Mac 127.0.0.1:3000 → Service shopmon-grafana:80 → Pod Grafana:3000
Mac 127.0.0.1:9090 → Service shopmon-prometheus:9090 → Pod Prometheus:9090
Mac 127.0.0.1:9093 → Service shopmon-alertmanager:9093 → Pod Alertmanager:9093
```

Chạy từng port-forward trong terminal riêng; khai báo TRACE trong mỗi terminal mới:

```sh
TRACE=/Users/phamquangtrung/Documents/Agent_setup/System/tools/run_logged.sh
$TRACE kubectl --context k3d-lab-k8s -n shopping-cart-observability port-forward svc/shopmon-grafana 3000:80
$TRACE kubectl --context k3d-lab-k8s -n shopping-cart-observability port-forward svc/shopmon-prometheus 9090:9090
$TRACE kubectl --context k3d-lab-k8s -n shopping-cart-observability port-forward svc/shopmon-alertmanager 9093:9093
```

Dashboard: http://127.0.0.1:3000/d/shopcart-live
Prometheus: http://127.0.0.1:9090
Alertmanager: http://127.0.0.1:9093

Port-forward cần tiến trình terminal còn chạy. Sau rollout/pod restart, nếu forward mất kết nối thì mở lại.
Các link Telegram dùng loopback, chỉ truy cập đúng trên Mac đang giữ các forward; điện thoại/máy khác không trỏ về Mac.
Argo CD quản lý resources trong cluster, không tự mở lại port-forward trên máy cá nhân.

Template Telegram có trong chart. Cấu hình receiver/token/chat ID ở Secrets, không commit.
`bootstrap.py` và manifest application mới đã được chuyển thành `.legacy`, không thực thi.
Các artifacts standalone values/alerts/dashboard chỉ là bản tham khảo lịch sử; cấu hình chính thức nằm trong chart Git.
Test rules chỉ dùng tạm, phải xóa sau khi xác minh. Source là query điều kiện cảnh báo, không phải exception log.

## Dữ liệu và rollback

### Retention và tự dọn dữ liệu — đã kiểm tra runtime 2026-10-02

- Prometheus: CR khai báo retention `3d`, retentionSize `3GB`; effective runtime config `/api/v1/status/config` là storage.tsdb.retention `{time: 3d, size: 3GiB}`. Cơ chế retention tích hợp tự loại bỏ block cũ khi điều kiện thời gian hoặc dung lượng đến trước, không cần CronJob riêng. PVC 5Gi dành thêm chỗ cho WAL/head; 3GiB không phải hard cap toàn thư mục hay giới hạn RAM.
- Logs stdout/stderr của container: kubelet configz trên cả ba node xác nhận containerLogMaxSize `10Mi`, containerLogMaxFiles `5`, monitor interval `10s`. Kubelet tự xoay log theo dung lượng; đây không phải retention Loki hoặc chính sách giữ log theo ngày. File do ứng dụng tự ghi vào volume cần cơ chế riêng.
- Loki: đã bật lại1replica; mounted config retention_period `48h`, compactor.retention_enabled true, retention_delete_delay `15m`. Disk-pressure-cleaner chạy kiểm tra mỗi5phút, khi đạt90% ngân sách8Gi yêu cầu xóa cửa sổ4h, cooldown4h. Chưa time-test xóa sau48h hoặc kích hoạt cleanup theo áp lực disk; xem plan logging riêng.
- Alertmanager: CR runtime retention `120h` (5 ngày) cho dữ liệu state notification log/silences; không phải kho lưu lịch sử mọi sự cố.
- Grafana: lưu dashboard/users/settings trong database, metrics được truy vấn từ Prometheus. Không có lịch tự xóa dashboard/user database.
- Retention metrics chủ yếu quản lý disk. Giảm RAM cần kiểm soát số series, scrape scope và tải query; không suy ra giữ ít ngày sẽ giảm ngay RAM.

Ba PV dữ liệu metrics vẫn là PV gốc, dùng Retain. Mapping ở `volume-migration-map.json` không chứa credentials.
Không xóa PV/PVC khi rollback. Revert commit Git rồi review/sync; không tự downgrade CRDs.
`PLAN-before-namespace-correction.md` là lịch sử đã superseded, không phải hướng dẫn chạy hiện tại.
Logs tập trung ở `Log_agents`, không xuất Secrets. Chưa promote thành durable memory.

## Sửa frontend trước đó

Deployment/Service frontend bị Missing từ trước lần cài metrics. Đã sync riêng Argo frontend,
không prune, theo revision `31a545c`; frontend 1/1, route resolved, /login và API products trả HTTP 200.
Không thay đổi frontend trong lần chuyển namespace này.

## Kết quả khôi phục Fluent Bit + Loki

Chart0.4.0, commit5632202 đã push/sync dev, app shopping-observability Synced/Healthy/Succeeded.
Logging Ready: Loki2/2, gateway1/1, FluentBit3/3. Grafana thêm datasource Loki UIDloki và một
panel Live Logs trong dashboard cũ (9panels). Marker request thật obs-loki-20261002T143804Z-c5d5f0f1
HTTP200 tìm thấy ở stdout/frontend, Loki và Grafana proxy. Không mock.
FluentBit dùng stat watcher do inotifyerrno24, labels runtime có prefixkubernetes_.
Grafana được cấp limit640Mi sau hai exit137 gần ngưỡng512Mi, nguyên nhân không khẳng định OOM.
RAM logging snapshot116Mi, CPU~25m; scope chỉShoppingCart, offsets persistent, buffer50M.
Loki PVC8Gi Bound, PVRetain; metricsPVC nguyên trạng. Chi tiết: PLAN_FLUENTBIT_LOKI.md.


## Giai đoạn 3 — Tempo + Collector + OTel đã nghiệm thu

Chart hiện tại0.5.0, vẫn namespace shopping-cart-observability và existing Argo shopping-observability. Runtime commit `0f7d73f17ce47c8d2b13b6e4e45c12c327e25356` trên dev.

- [x] Tempo PVC5Gi/Retain/retention48h; Collector OTLP + privacy/batch/queue/retry.
- [x] Instrument Go BFF HTTP server/client + FastAPI/SQLAlchemy catalog; W3C xuyên service.
- [x] GET products thật HTTP200; trace `c4963fc6dbca43f1ac760d6990e9b2ff`,9spans/2services + PostgreSQL dependency,62.107ms BFF server.
- [x] Grafana datasource + waterfall thực tế, logs↔trace hai chiều, live dashboard link.
- [x] Prometheus35/35targetsUP; tracing alert rules loaded; exporter failed0 tại snapshot.
- [x] App final tags Ready, native Istio proxy Ready; Argo stack Synced/Healthy, app Synced/Degraded do ExternalSecret provider lỗi có từ trước.
- [x] Ghi sự cố thiếu RAM/OOM và recovery đúng container/Pgpool; giữ PVC/database, swapVMtạm1GiB còn bật.

Plan chi tiết: [PLAN_TEMPO_OTEL.md](PLAN_TEMPO_OTEL.md). Logging cập nhật: [PLAN_FLUENTBIT_LOKI.md](PLAN_FLUENTBIT_LOKI.md). Chưa chứng minh checkout/payment/RabbitMQ hoặc HA toàn stack; chưa chạy soak test dài hạn/đợi retention48h.


## Full-system tracing completion (2026-10-03)

The subsequent full-system stage is completed:30 real tagged HTTP requests,666 verified spans across8 SDK services plus frontend/gateway mesh, exact Java RabbitMQ producer→Python consumer parent, SQL/Redis dependencies and Loki correlation. See [PLAN_FULL_SYSTEM_TRACING.md](PLAN_FULL_SYSTEM_TRACING.md) for final tags, corrections, commands, selective Argo procedure, capacity and limitations. Original stage results above remain historical.
