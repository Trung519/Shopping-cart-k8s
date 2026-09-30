# Nhập dữ liệu sản phẩm demo

Script `scripts/import-online-products.py` lấy và chuẩn hóa đúng 400 sản phẩm khác nhau từ ba API công khai:

- DummyJSON Products
- Platzi Fake Store API
- Open Food Facts, lọc sản phẩm tại Việt Nam

Dữ liệu được loại trùng theo tên đã chuẩn hóa. SKU có tiền tố `WEB-<SOURCE>-`, giá demo được đổi sang VND theo quy tắc cố định, và các bản ghi thiếu tên hoặc URL ảnh hợp lệ bị bỏ qua. Category từ nguồn không được giữ nguyên mà luôn được ánh xạ vào taxonomy do admin quản lý.

## Kiểm tra dữ liệu trước khi nhập

```bash
python3 scripts/import-online-products.py --format summary
```

## Nhập vào catalog local

Luôn chỉ rõ context để không ghi nhầm cluster:

```bash
python3 scripts/import-online-products.py --format sql | \
  kubectl --context k3d-lab-k8s -n shopping-cart-data exec -i postgresql-products-0 -- \
  sh -lc 'PGPASSWORD="$POSTGRESQL_PASSWORD" /opt/bitnami/postgresql/bin/psql -v ON_ERROR_STOP=1 -U postgres -d products'
```

Script có thể chạy lại. Mỗi lượt chỉ xóa nhóm seed có SKU `WEB-*`, không đụng sản phẩm thật, rồi ghi lại đúng 400 bản ghi sạch.

Nếu API công khai tạm thời giới hạn truy cập, có thể dùng snapshot JSON đã xuất trước đó với `--input-json <path>`. Snapshot local phải nằm trong `.local/`, là thư mục đã gitignore.

## Xác minh

```bash
kubectl --context k3d-lab-k8s -n shopping-cart-data exec postgresql-products-0 -- \
  sh -lc 'PGPASSWORD="$POSTGRESQL_PASSWORD" /opt/bitnami/postgresql/bin/psql -U postgres -d products -c \
  "SELECT count(*) AS imported, count(DISTINCT lower(name)) AS unique_names FROM products WHERE sku LIKE '\''WEB-%'\'';"'

curl -fsS 'http://shopping-cart.localhost:8080/api/v2/products?page=1&page_size=20'
```

Các URL ảnh được giữ ở nguồn công khai; môi trường cần Internet để trình duyệt tải ảnh.
