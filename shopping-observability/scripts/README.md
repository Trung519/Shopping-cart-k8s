# Dùng script observability

Script quản lý stack hiện có qua Argo CD, kiểm tra request thật và tự rollback khi deploy lỗi. Cần Python 3.9+, `kubectl`, `helm`, `git`; Python chỉ thêm **PyYAML**.

## 1. Chuẩn bị một lần

```sh
ROOT=/Users/phamquangtrung/Documents/Agent_setup
RUN="$ROOT/System/tools/run_logged.sh"
SCRIPTS="$ROOT/Artifacts/shopping-cart-k8s-publish/shopping-observability/scripts"
"$ROOT/System/tools/trace_session_init.sh" --new
"$RUN" python3 -m venv "$SCRIPTS/.venv"
PY="$SCRIPTS/.venv/bin/python"
OBS="$SCRIPTS/observability.py"
"$RUN" "$PY" -m pip install -r "$SCRIPTS/requirements.txt"
```

Khởi tạo trace mới một lần cho mỗi phiên làm việc; các lệnh sau dùng chung trace đó.

## 2. Kiểm tra và tạo plan

```sh
"$RUN" "$PY" "$OBS" check
"$RUN" "$PY" "$OBS" plan --allow-test-writes
```

Hai lệnh này đọc/render và mở kết nối kiểm tra, **chưa deploy, chưa tạo đơn test**. `plan` in **Plan ID** và danh sách thay đổi trong report. Source phải commit/push đúng revision; image cũ/mới phải có bằng chứng cache **và digest trên node có thể chạy workload**. Có blocker thì xử lý trước và tạo plan mới.

Workload, init và sidecar cần `resources.limits.memory` **lớn hơn 0** để tính RAM rollout; chỉ có `requests` sẽ báo `CAPACITY_UNKNOWN`. Không dùng image `latest` hoặc thiếu tag; `imagePullPolicy: Always` cần digest. Đổi version Prometheus/Alertmanager cần khai báo `spec.image` rõ. Script dừng khi không chứng minh được đường deploy/rollback an toàn.

## 3. Deploy

```sh
"$RUN" "$PY" "$OBS" deploy --plan-id PLAN_ID --allow-test-writes
```

Thay `PLAN_ID` bằng ID vừa tạo. Script triển khai tuần tự, kiểm trace/log/metric đã khai báo và RabbitMQ/Redis/SQL; lỗi thì hoàn tác thay đổi đã ghi. `--allow-test-writes` cho phép user/product/cart/order **test riêng**, sau đó cancel order, ẩn product (`inactive`) và xóa user. Lịch sử order/message được giữ; không thực hiện thanh toán bên ngoài.

## 4. Chỉ kiểm chứng hệ thống đang chạy

```sh
"$RUN" "$PY" "$OBS" verify --allow-test-writes --collect-errors
```

Không deploy; kiểm đủ flows và liệt kê gate chưa đạt. Muốn không tạo dữ liệu test, dùng `verify --read-only`; kết quả chỉ là kiểm public routes và sẽ báo chưa đủ full contract.

Đọc `coverage` trong report: `mesh_metrics: PASS` là counter Istio; `application_metrics: NOT_DECLARED` nghĩa chưa yêu cầu app metric, **không phải app metric đã đạt**. Muốn kiểm app metric, thêm counter query và freshness query theo [mẫu contract](../docs/APPLICATION_OBSERVABILITY_CONTRACT.md). Collector `loss_evidence: UNKNOWN` nghĩa thiếu series, chưa kết luận không mất span.

Counter chưa xuất hiện thì script gửi một GET khởi động, chờ scrape rồi mới đo baseline. Vẫn thiếu sẽ báo lỗi tại flow đó; không phát lại POST/checkout để khởi động counter.

## 5. Khi một lượt chưa phục hồi xong

```sh
"$RUN" "$PY" "$OBS" status --run-id RUN_ID
"$RUN" "$PY" "$OBS" recover --run-id RUN_ID
```

Thay `RUN_ID` bằng ID của lượt lỗi. Không chạy deploy mới khi state còn `ROLLBACK_INCOMPLETE` hoặc `CLEANUP_INCOMPLETE`. Recovery dừng Argo writes → phục hồi config/workload → cleanup → kiểm HTTP, readiness và UID/volume PVC; **chỉ đủ các gate mới nhả Lease**. `RESOURCES_RESTORED` chỉ nói resource đã restore, chưa kết luận toàn recovery xong.

`rollback --run-id RUN_ID` dùng để hoàn tác lượt deploy đã hoàn tất. Script giữ PVC và credential Secret; chỉ quản lý Secret scrape config công khai đã kiểm tra không chứa credentials. Field do người khác sửa sẽ báo conflict. Sau rollback, Git desired có thể còn cần sửa trước lần sync tiếp.

## Đổi biến và đọc lỗi

Copy [deploy.example.yaml](config/deploy.example.yaml), sửa biến cần thiết rồi thêm `--config /path/to/config.yaml` vào lệnh. Biến đầy đủ và comment nằm trong [profile](config/profiles/shopping-cart-local.yaml). Thiếu/sai biến sẽ dừng; credentials chỉ dùng Secret reference, không có password default.

Gateway V1 dùng tunnel HTTP nội bộ: `base_url`, `allowed_hosts`, `allowed_ports` phải khớp. URL/redirect ngoài allowlist bị chặn trước gửi credential; V1 chưa hỗ trợ gateway HTTPS qua tunnel này.

`❌ [MÃ_LỖI] STEP · đối tượng` cho biết lỗi ở đâu; dòng `→` chỉ cách xử lý. Report/journal ở `Agent_setup/Log_agents`, chứa bằng chứng và state recovery đã lọc. Exit: `0` đạt yêu cầu; `3` bị chặn trước deploy; `4` deploy lỗi nhưng rollback xong; `5` recovery/cleanup chưa xong; `6` nghiệm thu chưa đạt; `2` sai config.

V1 dùng stack/Argo/prerequisites sẵn có; chưa bootstrap cluster trắng hoặc migrate storage. Frontend kiểm HTTP qua mesh, chưa kiểm browser clicks. Redis client spans được yêu cầu; Redis server exporter và gửi notification ra ngoài là phạm vi riêng, không được báo là đã test.

## Chạy test script

```sh
"$RUN" "$PY" -m unittest discover -s "$SCRIPTS/tests" -v
"$RUN" "$PY" "$SCRIPTS/tests/live_rollback.py"
```

Lệnh thứ hai chỉ tạo/đổi/khôi phục/xóa một ConfigMap test riêng. [Kết quả test](../docs/SRE_DEPLOY_TEST_RESULTS.md) ghi rõ phần đã qua và khoảng thiếu của ứng dụng hiện tại.

## Đọc code Python

Trên mỗi hàm đều có 4 dòng: **Purpose** (tác dụng), **Syntax** (cú pháp cần hiểu), **Flow** (input → xử lý → output/lỗi), **Kiến thức liên quan** (hàm/khái niệm được gọi). Bắt đầu từ `cli.main`, rồi đọc các hàm nó gọi; helper và test cũng dùng cùng định dạng.
