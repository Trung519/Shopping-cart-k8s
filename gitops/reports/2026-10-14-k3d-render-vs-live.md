# Đối chiếu Helm chart (source) với cluster k3d — 2026-10-14

**Cluster:** `k3d-lab-k8s` (chỉ đọc, không thay đổi gì trên cluster)
**Source so sánh:**
- **Working tree** hiện tại (gồm WIP chưa commit và refactor `charts/` hôm nay).
- **HEAD `ad44793`**, cũng là revision Argo CD đang đọc trên nhánh `dev`.

## Cách làm

1. Render 11 release trong `gitops/control-plane/services.yaml` bằng `helm template --include-crds`, đúng thứ tự `valueFiles` của ApplicationSet. Thêm `gitops/control-plane/*` cho root Application. Tổng cộng **225 object**, gồm 215 object thường và 10 helm hook.
2. Lấy object live tương ứng, rồi so từng field:
   - **Labels, ConfigMap data, list có `name`** (env, volumes, containers…): so cả hai chiều. Field có trên live mà không có trong source cũng bị báo.
   - **Các field khác:** chỉ so field do source khai báo.
   - **Được coi là bằng nhau:** quantity (`1000m` = `1`), số/chuỗi, và `false`/`0` ở source so với field vắng trên live (server tự bỏ giá trị mặc định).
   - **Secret:** chỉ so bằng sha256, không in giá trị.
3. Kiểm kê **mọi namespace** và cluster scope:
   - Object mang `argocd.argoproj.io/tracking-id` của các app này nhưng không có trong source.
   - Object top-level trong các namespace `shopping-cart-*` không có owner và không có trong source.
4. Hai Helm release ngoài ApplicationSet là `vault` và `external-secrets` được so values với `config-secret-secure/values/local/0{1,2}-*.yaml`.

## Kết quả tổng quan

| Hạng mục | Kết quả |
|---|---|
| Object trong source nhưng **không có** trên cluster | **0** |
| Lệch thật giữa live và **Git HEAD** | **17 field** (order-service, payment-service, shopping-integration) |
| Lệch do source hiện tại **chưa deploy** (WIP + refactor hôm nay) | 35 field + chỉ nhãn/version/checksum |
| Release khớp hoàn toàn với HEAD (bỏ qua nhãn) | frontend, basket-service, product-catalog, commerce-bff, account-service, seller-service, shopping-cart-security, shopping-observability |
| Object trên cluster **không có trong source** | bộ Grafana cũ (8 object + PVC), 68 Secret lịch sử Helm |
| `vault`, `external-secrets` values | **Khớp 100%** |

---

## A. Live lệch khỏi Git (sai ngay cả khi so với HEAD) — cần quyết định

### A1. HTTPRoute `shopping-cart-apps/shopping-cart` thiếu 5 route
- **Source (HEAD và working tree):** 7 rule gồm `/api/v2`, `/api/products`, `/api/orders`, `/api/cart`, `/api/auth`, `/api/payments`, `/`.
- **Live:** chỉ có `/api/v2` và `/`.
- **Nguồn gốc:** sửa tay bằng `kubectl edit` ngày **2026-09-05** (theo managedFields). Object này chưa từng được Argo apply (không có tracking-id).
- **Rủi ro:** lần Sync `shopping-integration` tiếp theo sẽ **thêm lại 5 route cũ**, mở lại các API đi thẳng vào service mà không qua BFF.
- **Đề xuất:** nếu việc bỏ route là cố ý (mọi API đi qua BFF `/api/v2`), sửa source cho khớp: bỏ các route cũ trong `charts/platform/shopping-integration/templates/networking/nginx-gateway-httproute.yaml` và `values.yaml` (`gateway.routes`).

### A2. `order-service` và `payment-service`: live có volume `/tmp` mà source không có
- **Live:** `volumes[tmp] = emptyDir` và `volumeMounts[tmp] = /tmp`.
- **Source:** không có. Ở HEAD có trong chart default, nhưng `extraVolumes` trong file env ghi đè cả list. Working tree đã bỏ hẳn.
- **Nguồn gốc:** sót lại từ lần cài bằng Helm. Argo dùng client-side apply nên không gỡ field này.
- **Rủi ro:** container chạy `readOnlyRootFilesystem: true`. Nếu cài mới hoặc Sync kiểu Replace, Java app **mất `/tmp` ghi được** và có thể lỗi khi khởi động.
- **Đề xuất:** thêm `tmp` (emptyDir và mount `/tmp`) vào `extraVolumes`/`extraVolumeMounts` của `23-order-service.yaml` và `24-payment-service.yaml`.

### A3. pgpool: `replicas` 2 (source) và 1 (live)
- Áp dụng cho `shopping-cart-data/postgresql-orders-pgpool` và `postgresql-products-pgpool`.
- **Nguồn gốc:** live giữ giá trị từ lần Helm cài ngày 2026-08-01. Argo chưa từng apply hai Deployment này.
- **Đề xuất:** chọn 1 hoặc 2, rồi ghi rõ vào `10-shopping-integration.yaml`.

### A4. Đã deploy ngoài Git (live khớp working tree, không khớp HEAD)
- **order-service:** image `v1.1.2-request-log-20261004`, trong khi HEAD là `v1.1.1-tracing-errorfix-20261003`.
- **payment-service:** image `v0.1.3-request-log-20261004`, trong khi HEAD là `v0.1.2-tracing-rolefix-20261003`.
- **keycloak:** `KC_LOG_CONSOLE_FORMAT`, `quarkus.properties` và volume `request-logging` đã có trên live nhưng chưa có ở HEAD.
- **Đề xuất:** commit và push WIP. Nếu không, lần Sync tiếp theo của Argo sẽ **rollback** về image và config cũ.

---

## B. Source hiện tại đi trước live (chưa deploy) — dự kiến, sẽ áp dụng khi push và Sync

| Release | Object | Khác biệt |
|---|---|---|
| commerce-bff | ConfigMap `commerce-bff-config` | Source thêm `MOCK_API_ENABLED=true`, `MOCK_EVENT_INTERVAL_SECONDS=15`, `MOCK_PAYMENT_DELAY_SECONDS=5`, `MOCK_SHIPMENT_STEP_SECONDS=10` |
| shopping-observability | PrometheusRule `shopmon-shopping-alerts` → `MonitoringContainerNearMemoryLimit` | Live lọc `namespace="monitoring"`, một namespace không tồn tại, nên **alert này hiện không bao giờ bắn**. Source đã sửa thành `shopping-cart-observability`. |
| shopping-observability | ConfigMap `fluent-bit` | `Path`: live dùng `*_shopping-cart-*.log`, source liệt kê 5 namespace (thu hẹp lại). Loki host: live là `loki-gateway`, source là FQDN. |
| shopping-observability | ConfigMap `shopmon-grafana-datasource` | Query trace→log: live dùng regex `shopping-cart-(apps\|payment\|identity\|gateway)`, source liệt kê đủ tên. Hai cách tương đương. |
| shopping-observability | ConfigMap `otel-collector-config`, Secret `shopmon-prometheus-scrape-confg` | Chỉ khác quote và cách viết regex, **ngữ nghĩa giống nhau**. Nhưng `checksum/tracing` sẽ đổi nên otel-collector sẽ restart một lần. |
| shopping-cart-root | ApplicationSet `shopping-cart-services` | `chartPath` chuyển sang `charts/apps/*` và `charts/platform/*`. `valuesPath` của security/observability chuyển sang `11-`/`12-*.yaml`. Bỏ `00-global.yaml` khỏi `valueFiles`. |
| 8 app chart | Mọi object | Refactor library chart hôm nay: thêm nhãn chuẩn, đổi nhãn `helm.sh/chart` sang version mới, `checksum/config` đổi một lần (**8 app sẽ rolling restart một lần**). |

> ⚠️ **Thứ tự push:** WIP đã xoá `config-secret-secure/values/local/00-global.yaml`, nhưng ApplicationSet đang chạy vẫn tham chiếu file này. Phải push **cùng một commit** gồm việc xoá file và `services.yaml` mới, rồi Sync root trước. Nếu không, cả 11 app sẽ báo ComparisonError vì thiếu values file.

---

## C. Có trên cluster nhưng không có trong source (kiểm kê mọi namespace)

| Namespace | Object | Đánh giá |
|---|---|---|
| shopping-cart-observability | `Deployment/grafana` (replicas=0), `Service/grafana`, `ServiceAccount/grafana`, `Role`/`RoleBinding grafana`, `ConfigMap/grafana`, `Secret/grafana-admin`, `PVC/grafana` | **Mồ côi.** Do Helm cài ngày 2026-08-01 từ subchart grafana cũ, nay đã bị xoá khỏi source. Grafana hiện tại là `shopmon-grafana`. Argo không theo dõi nên sẽ không bao giờ prune. Đề xuất: backup PVC nếu cần dashboard cũ, rồi xoá. |
| shopping-cart-apps, -payment, -data, -observability | 68 Secret `sh.helm.release.v1.*` | Lịch sử Helm từ trước khi Argo quản lý. `helm list` đang sai lệch (release `frontend` rev 13 ở trạng thái **failed**, observability 0.2.0). Đề xuất: không chạy `helm upgrade` cho các release này nữa. Có thể dọn sau khi xác nhận Argo quản lý ổn định. |
| shopping-cart-observability | `Secret/shopmon-grafana-admin`, `shopmon-alertmanager-config`, `shopmon-telegram` | Bình thường: do script SRE tạo và được values tham chiếu qua existing secret. |
| shopping-cart-observability | `Secret/shopmon-admission` | Bình thường: cert webhook do hook job của kube-prometheus-stack tạo. |
| shopping-cart-* | 13 PVC | Bình thường: từ `volumeClaimTemplates` của StatefulSet. Riêng `PVC/grafana` thuộc bộ mồ côi ở trên. |
| shopping-cart-* | `ConfigMap/istio-ca-crl` | Do Istio quản lý. |
| Các namespace còn lại (argocd, kube-system, vault, external-secrets, istio-system, envoy-gateway-system, cattle-*, default, debug-workshop-ex01…) | — | Không có object nào mang tracking-id hoặc release của các app này nằm ngoài source. |

## D. Argo CD chưa thực sự quản lý nhiều object

Các object sau trùng tên và nội dung với source nhưng **không có `tracking-id`**, tức là do Helm tạo và Argo chưa từng apply:
- Service, ServiceAccount, ExternalSecret của 7 app.
- Gần như toàn bộ object của `shopping-integration`.
- AuthorizationPolicy của `shopping-cart-security` (Application này **chưa Sync lần nào**).
- 10 CRD monitoring, AppProject và ApplicationSet.

Hệ quả:
- Argo sẽ không prune các object này khi bạn xoá chúng khỏi Git.
- Các sửa tay kiểu A1 và A3 không được Argo phát hiện.

Trạng thái Argo hiện tại:
- **OutOfSync:** account-service, order-service, payment-service, seller-service, shopping-integration, shopping-cart-security, shopping-cart-root.
- **Synced:** các app còn lại.

## E. Helm hooks (shopping-observability)

Có 10 hook: admission webhook của kube-prometheus-stack và test của grafana. Trên cluster còn `ServiceAccount`, `ClusterRole`, `RoleBinding shopmon-admission`. Các Job và test pod đã bị xoá theo hook policy. Đây là hành vi bình thường.

## Đề xuất thứ tự xử lý

1. Quyết định A1 (route gateway) và A3 (số replica pgpool), rồi sửa source cho khớp với ý định.
2. Thêm `/tmp` cho order và payment (A2) vào values.
3. Commit WIP, refactor `charts/` và `services.yaml` trong **cùng một lần push**. Sync `shopping-cart-root` trước, sau đó Diff và Sync từng app.
4. Dọn bộ Grafana cũ (C), sau khi backup PVC nếu cần.
5. Không dùng `helm upgrade` cho các release đã chuyển sang Argo nữa.
