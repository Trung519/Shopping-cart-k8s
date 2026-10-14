---
title: SRE observability deployment gates and recovery
type: runbook-artifact
domain: kubernetes
status: implemented-with-explicit-scope
created: 2026-10-04
updated: 2026-10-04
---

# Các gate vận hành

1. Validate input/contract, đúng context và cluster UID.
2. Workloads/pods/native sidecars Ready, PVC Bound, dependency endpoints có địa chỉ, Istio providers tồn tại.
3. Render đúng Argo chart/values; đối chiếu remote SHA, whitelist resource và ownership. Không snapshot Secret/credentials inline.
4. Public business baseline thành công; RabbitMQ required queue có consumer; full test có credential refs/role và cleanup adapter.
5. Với deploy: plan chưa stale, source đã push, image deploy/restore có trên node, đủ VM headroom; local lock và cluster Lease.
6. Journal PREPARED trước API write; pin revisions, prune=false, selected resources; operation UUID đúng; live manifest/generation/rollout khớp.
7. Backend OTLP privacy probe; request thật qua từng route, đủ graph/log/metric delta; async consumer phải đến trước deadline.
8. Rule evaluation + Alertmanager health; cleanup fixture; business ổn định; báo final state/report.

Full verify có `--collect-errors` để tìm mọi khoảng thiếu, nhưng deploy luôn fail ngay khi một gate bắt buộc lỗi. Report không biến counter absent thành 0. Gửi notification ra ngoài chưa được test; bật `notification_required` sẽ bị chặn trước mutation.

# Recovery

- Terminate đúng Argo operation của run và chờ controller xác nhận terminal state; không xóa `.operation`.
- Reverse actions theo thứ tự ngược; compare UID và after-state. Nếu response API bị mất, đọc live fields để xác định outcome. Không overwrite thay đổi của operator khác.
- Restore spec/data/metadata fields và field absence; chờ rollout; verify baseline HTTP và PVC identity. Giữ journal nếu recovery chưa hoàn tất.
- `recover` đọc config từ journal và kiểm cluster UID; synthetic user credentials được tạo lại qua admin flow, không lưu password/token. Admin token TTL được làm mới trong memory khi cần.
- Direct compensation không sửa Git remote; report `reconciliation_pending` khi đã sync. Review desired state trước sync tiếp để tránh đưa cấu hình lỗi trở lại.

V1 chỉ thao tác resource đang tồn tại, trong whitelist. Storage/schema/CRDs/hooks và unmanaged mesh là prerequisites; không tự bootstrap hoặc migrate. Lease có heartbeat; crash giữ ownership cho recover, không tự cướp lock của run khác.
