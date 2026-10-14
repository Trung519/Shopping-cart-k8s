"""Real gateway flow. Synthetic fixture IDs only; credentials never persisted."""
import base64
import http.client
import http.cookiejar
import json
import secrets
import socket
import time
import urllib.parse
import urllib.request
import uuid
from html.parser import HTMLParser

from .core import Error, HTTP, need, secret


class LoginForm(HTMLParser):
    # Purpose: Khởi tạo parser để lấy URL form login Keycloak.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: HTMLParser được khởi tạo; action=None cho tới khi gặp đúng form.
    # Kiến thức liên quan: HTMLParser gọi handle_starttag khi đọc HTML, không dùng regex để đoán form.
    def __init__(self):
        super().__init__()
        self.action = None

    # Purpose: Chọn action của đúng form đăng nhập.
    # Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
    # Flow: tag=form và id=kc-form-login → lưu action; các tag khác không thay kết quả.
    # Kiến thức liên quan: HTMLParser truyền attrs dạng cặp; dict(attrs) chuyển sang mapping để tra attribute.
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form" and values.get("id") == "kc-form-login":
            self.action = values.get("action")


class GatewayHandler(urllib.request.HTTPHandler, urllib.request.HTTPSHandler):
    # Purpose: Lưu endpoint tunnel và host/port được phép truy cập.
    # Syntax: a,b = ... unpack và gán nhiều giá trị theo thứ tự; số phần tử phải khớp.
    # Flow: target_port=12345, hosts=[shop,auth] → tập host và port để kiểm trước network.
    # Kiến thức liên quan: urllib Handler dùng do_open; allowlist không chứa credential.
    def __init__(self, target_port, allowed_hosts, allowed_ports=(80, 8080)):
        super().__init__()
        self.port, self.hosts = target_port, set(allowed_hosts)
        self.allowed_ports = set(allowed_ports)

    # Purpose: Chặn URL ngoài HTTP gateway trước khi gửi body hoặc credential.
    # Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
    # Flow: URL sai scheme/host/port hoặc có userinfo → AUTH_REDIRECT_INVALID; đúng → trả Request.
    # Kiến thức liên quan: urlsplit tách URL; urllib request processor chạy cả request đầu và redirect.
    def http_request(self, request):
        try:
            url = urllib.parse.urlsplit(request.full_url)
            port = url.port or 80
        except ValueError:
            raise Error("AUTH_REDIRECT_INVALID", "S08", "OIDC", "Gateway URL/port không hợp lệ.") from None
        need(url.scheme == "http" and url.hostname in self.hosts and
             port in self.allowed_ports and not url.username and not url.password,
             "AUTH_REDIRECT_INVALID", "S08", "OIDC", "URL ngoài gateway HTTP/host/port cho phép.")
        return request

    https_request = http_request

    # Purpose: Không cho default HTTPS handler mở đường bypass allowlist.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Bất kỳ HTTPS request tới handler này → lỗi rõ tunnel V1 chỉ hỗ trợ HTTP.
    # Kiến thức liên quan: HTTPHandler+HTTPSHandler thay cả hai default opener; https_request cũng dùng guard HTTP.
    def https_open(self, request):
        raise Error("AUTH_REDIRECT_INVALID", "S08", "OIDC", "Tunnel V1 chỉ hỗ trợ HTTP; HTTPS bị chặn.")

    # Purpose: Giữ Host gateway nhưng kết nối TCP vào tunnel local.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Guard URL → tạo Connection tùy biến → do_open; không resolve/connect hostname ra bên ngoài.
    # Kiến thức liên quan: do_open thực hiện HTTP trên Connection; lớp lồng dùng target từ closure.
    def http_open(self, request):
        self.http_request(request)
        target = self.port

        class Connection(http.client.HTTPConnection):
            # Purpose: Chuyển socket của HTTP connection vào port-forward sở hữu.
            # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
            # Flow: HTTP cần connect → socket tới 127.0.0.1:target với timeout hiện tại.
            # Kiến thức liên quan: socket.create_connection mở TCP; self.sock là socket mà HTTPConnection gửi request lên.
            def connect(self):
                self.sock = socket.create_connection(("127.0.0.1", target), self.timeout)

        return self.do_open(Connection, request)


class GatewayRedirect(urllib.request.HTTPRedirectHandler):
    # Purpose: Không mang Authorization/Cookie sang origin khác khi redirect.
    # Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
    # Flow: Tạo redirected Request; scheme/host/port đổi → bỏ header credential; trả request mới.
    # Kiến thức liên quan: super giữ logic redirect urllib; cookie processor chỉ gửi cookie đúng domain/path của cookie jar.
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        old, new = urllib.parse.urlsplit(request.full_url), urllib.parse.urlsplit(newurl)
        redirected = super().redirect_request(request, fp, code, msg, headers, newurl)
        if redirected and (old.scheme, old.hostname, old.port or 80) != (new.scheme, new.hostname, new.port or 80):
            for name in ("Authorization", "Cookie", "Proxy-authorization"):
                redirected.remove_header(name)
        return redirected


class Application:
    # Purpose: Gom client gateway, auth admin và fixture state cho một lượt test.
    # Syntax: a,b = ... unpack và gán nhiều giá trị theo thứ tự; số phần tử phải khớp.
    # Flow: Mở tunnel dùng chung → opener allowlist/cookies → clients → đọc hoặc tạo fixtures trong journal.
    # Kiến thức liên quan: CookieJar giữ session trong RAM; public_http không có session của user test.
    def __init__(self, config, kube, forwards, journal):
        self.c, self.k, self.f, self.j = config, kube, forwards, journal
        gw = config["gateway"]
        tunnel = forwards.open(gw["namespace"], gw["service"], gw["port"])
        self.cookies = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                             GatewayHandler(urllib.parse.urlsplit(tunnel).port, gw["allowed_hosts"], gw.get("allowed_ports", [80, 8080])),
                                             GatewayRedirect(),
                                             urllib.request.HTTPCookieProcessor(self.cookies))
        self.http, self.admin = HTTP(opener=opener, deadline=kube.runner.deadline), HTTP(deadline=kube.runner.deadline)
        anonymous = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                               GatewayHandler(urllib.parse.urlsplit(tunnel).port, gw["allowed_hosts"], gw.get("allowed_ports", [80, 8080])), GatewayRedirect())
        self.public_http = HTTP(opener=anonymous, deadline=kube.runner.deadline)
        self.base, self.auth_headers, self.admin_base = gw["base_url"].rstrip("/"), {}, None
        self.admin_deadline = 0
        self.fixture = journal.data.setdefault("fixtures", {"state": "NONE", "orders": []})

    # Purpose: Kiểm app còn phục vụ public business request.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Chọn public JSON route → HTTP đúng contract và list/dict → PASS; sai schema → lỗi.
    # Kiến thức liên quan: HTTP.request kiểm status; baseline không chứng minh đủ auth/trace/AMQP flows.
    def public_baseline(self):
        route = next(r for r in self.c["contract_data"]["routes"] if not r.get("authenticated") and r.get("response") != "html")
        result = self.public_http.request(self.base + route["path"], expected=tuple(route["expected"]))
        need(isinstance(result, (list, dict)), "BASELINE_UNHEALTHY", "S03", route["id"], "Business response sai schema.")
        return {"route": route["id"], "status": "PASS"}

    # Purpose: Lấy hoặc refresh admin token để cleanup không lỗi vì token hết hạn.
    # Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
    # Flow: Token còn TTL → dùng lại; hết → lấy Secret, POST token, lưu Authorization chỉ trong RAM.
    # Kiến thức liên quan: OAuth password grant dùng admin-cli của adapter; expires_in trừ grace 5 giây trước refresh.
    def admin_ready(self):
        if self.admin_base and time.monotonic() < self.admin_deadline:
            return
        auth = self.c["auth"]
        if not self.admin_base:
            self.admin_base = self.f.open(auth["namespace"], auth["service"], auth["port"])
        data = secret(self.k, auth["namespace"], auth["secret"], [auth["username_key"], auth["password_key"]])
        form = urllib.parse.urlencode({"grant_type": "password", "client_id": "admin-cli",
                                      "username": data[auth["username_key"]], "password": data[auth["password_key"]]})
        token = self.admin.request(self.admin_base + "/realms/master/protocol/openid-connect/token", "POST", form,
                                   {"Content-Type": "application/x-www-form-urlencoded"})
        self.auth_headers = {"Authorization": "Bearer " + token["access_token"]}
        self.admin_deadline = time.monotonic() + max(1, int(token.get("expires_in", 30)) - 5)
        self.realm = self.admin_base + "/admin/realms/" + urllib.parse.quote(auth["realm"], safe="")

    # Purpose: Gọi Keycloak Admin API với token còn hiệu lực.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: path=/users → admin_ready → HTTP request theo realm và expected status.
    # Kiến thức liên quan: admin_ready refresh credential từ Secret; API response/headers nhạy cảm không ghi journal.
    def api(self, path, method="GET", body=None, expected=(200,)):
        self.admin_ready()  # acceptance may outlive Keycloak's short admin token TTL
        return self.admin.request(self.realm + path, method, body, self.auth_headers, expected)

    # Purpose: Tìm đúng user test theo marker, không xóa user khác.
    # Syntax: X if C else Y chọn X khi điều kiện C đúng, còn lại dùng Y (fallback).
    # Flow: Không có username → None; exact username lookup → tối đa một ID; trùng marker → conflict.
    # Kiến thức liên quan: Keycloak exact=true giới hạn lookup; urlencode giữ query đúng khi marker có ký tự đặc biệt.
    def resolve_user(self):
        if not self.fixture.get("username"):
            return None
        self.admin_ready()
        users = self.api("/users?" + urllib.parse.urlencode({"username": self.fixture["username"], "exact": "true"}))
        need(len(users) <= 1, "CLEANUP_CONFLICT", "R01", "test user", "Có nhiều fixture trùng marker.")
        return users[0]["id"] if users else None

    # Purpose: Đăng nhập thật qua OIDC gateway để test auth flow.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Dọn session cũ → đọc form → POST user/password → cần shopcart_session cookie.
    # Kiến thức liên quan: LoginForm lấy form action; CookieJar giữ session; GatewayHandler kiểm URL trước gửi password.
    def login(self, password):
        if any(c.name == "shopcart_session" for c in self.cookies):
            self.http.request(self.base + "/api/v2/auth/logout", "POST", expected=(200, 401))
        self.cookies.clear()
        _, content, _ = self.http.request(self.base + "/api/v2/auth/login", raw=True)
        form = LoginForm()
        form.feed(content.decode())
        need(form.action, "AUTH_FAILED", "S08", "OIDC", "Không tìm thấy login form.")
        url = urllib.parse.urljoin(self.base, form.action)
        post = urllib.parse.urlencode({"username": self.fixture["username"], "password": password, "credentialId": ""})
        self.http.request(url, "POST", post, {"Content-Type": "application/x-www-form-urlencoded"}, raw=True)
        need(any(c.name == "shopcart_session" for c in self.cookies), "AUTH_FAILED", "S08", "OIDC", "Không có session sau login PKCE.")

    # Purpose: Tạo hoặc đăng nhập lại identity test riêng, có ý định cleanup bền vững.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Ghi USER_CREATE_PREPARED trước POST; tạo user/role/login; recover → reset password trong RAM rồi login.
    # Kiến thức liên quan: Marker gắn run_id; secrets.token_urlsafe tạo password mới, không lưu password vào journal.
    def authenticate(self):
        need(self.c["contract_data"].get("adapter") == "shopping-cart", "ADAPTER_NOT_SUPPORTED", "S03", "auth/checkout",
             "Write fixture adapter chỉ hỗ trợ shopping-cart.")
        need(self.c["allow_test_writes"], "TEST_WRITES_REQUIRED", "S03", "full contract",
             "Full test cần fixture riêng cho auth/checkout.", "Dùng --allow-test-writes để cho phép fixture và cleanup.")
        self.admin_ready()
        if self.fixture["state"] == "NONE":
            self.fixture.update({"state": "USER_CREATE_PREPARED", "username": "sre-probe-" + self.j.data["run_id"][:16]})
            self.j.save()
            password = secrets.token_urlsafe(24) + "Aa1!"
            self.api("/users", "POST", {"username": self.fixture["username"], "enabled": True,
                     "emailVerified": True, "firstName": "SRE", "lastName": "Probe",
                     "email": self.fixture["username"] + "@example.invalid", "attributes": {"country_id": ["VN"]},
                     "credentials": [{"type": "password", "value": password, "temporary": False}]}, expected=(201,))
            self.fixture["user_id"] = self.resolve_user()
            self.fixture["state"] = "USER_CREATED"
            self.j.save()
            role = self.api("/roles/" + urllib.parse.quote(self.c["auth"]["role"]))
            self.api("/users/" + self.fixture["user_id"] + "/role-mappings/realm", "POST", [role], expected=(204,))
        else:
            self.fixture["user_id"] = self.resolve_user()
            need(self.fixture.get("user_id"), "CLEANUP_FAILED", "R01", "test user", "Fixture user không còn để cleanup business data.")
            password = secrets.token_urlsafe(24) + "Aa1!"
            self.api("/users/" + self.fixture["user_id"] + "/reset-password", "PUT",
                     {"type": "password", "value": password, "temporary": False}, expected=(204,))
        self.login(password)

    # Purpose: Gửi request mới có trace ID riêng và lưu chỉ bằng chứng tối thiểu.
    # Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
    # Flow: Tạo traceparent → public/auth client → kiểm response → journal route/trace ID/timestamps → row,response.
    # Kiến thức liên quan: W3C traceparent mang trace/span parent/sampling; uuid/secrets tạo ID mới cho mỗi request.
    def call(self, route, method=None, path=None, body=None, expected=None):
        tid, started = uuid.uuid4().hex, time.time()
        url_path = path or route["path"].replace("{user_id}", self.fixture.get("user_id", ""))
        client = self.public_http if route.get("authenticated") is False else self.http
        response = client.request(self.base + url_path, method or route.get("method", "GET"), body,
                    {"traceparent": "00-" + tid + "-" + secrets.token_hex(8) + "-01"},
                    tuple(expected or route.get("expected", [200])), raw=route.get("response") == "html")
        if route.get("response") == "html":
            need(b"<html" in response[1].lower(), "RESPONSE_INVALID", "S08", route["id"], "Frontend không trả HTML.")
            response = {"html": True}
        row = {"route": route["id"], "trace_id": tid, "started": started, "completed": time.time()}
        self.j.data.setdefault("requests", []).append(row)
        self.j.save()
        return row, response

    # Purpose: Tạo checkout test riêng để chứng minh Redis và AMQP flow.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Chọn category → ghi product intent → tạo product/cart → ghi checkout intent → POST checkout → lưu order ID.
    # Kiến thức liên quan: Write-ahead journal giúp tìm lại record khi mất response; chỉ dùng identity test hiện tại.
    def checkout(self):
        # All records belong to the dedicated synthetic identity. Never use old user data.
        categories = self.http.get(self.base + "/api/v2/products/categories")
        category = next((c["slug"] for c in categories if c.get("is_active", True)), None)
        need(category, "TEST_FIXTURE_MISSING", "S08", "category", "Không có category cho sản phẩm test.")
        self.fixture.update({"sku": "sre-" + self.j.data["run_id"][:16], "state": "PRODUCT_CREATE_PREPARED"})
        self.j.save()
        _, product = self.call({"id": "fixture-product"}, "POST", "/api/v2/products",
                               {"sku": self.fixture["sku"], "name": "SRE isolated test", "price": 1,
                                "currency": "USD", "quantity": 3, "category": category}, expected=[201])
        self.fixture["product_id"], self.fixture["state"] = product["id"], "PRODUCT_CREATED"
        self.j.save()
        self.call({"id": "fixture-cart"}, "POST", "/api/v2/cart/items",
                  {"productId": product["id"], "quantity": 1}, expected=[201])
        self.fixture["state"] = "CHECKOUT_PREPARED"
        self.j.save()
        row, result = self.call({"id": "checkout"}, "POST", "/api/v2/cart/checkout",
                               {"shippingAddress": {"street": "Synthetic test", "city": "Test", "state": "Test",
                                                    "postalCode": "00000", "country": "VN"}})
        oid = result.get("data", result).get("orderId")
        need(oid, "TEST_RESPONSE_INVALID", "S08", "checkout", "Checkout không trả orderId.")
        self.fixture["orders"].append(oid)
        self.fixture["state"] = "CHECKOUT_CREATED"
        self.j.save()
        return row

    # Purpose: Dọn fixture an toàn và recover được khi process chết giữa các lệnh.
    # Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
    # Flow: Cancel và verify order → tìm/deactivate và verify product → lưu business_cleaned → xóa/verify user → CLEANED.
    # Kiến thức liên quan: Cleanup evidence được save trước xóa identity; mất response lần xóa user có thể recover mà không cần login.
    def cleanup(self):
        if self.fixture["state"] in ("NONE", "CLEANED"):
            return
        uid = self.resolve_user()
        if not uid:
            need(self.fixture.get("business_cleaned") or (not self.fixture.get("sku") and not self.fixture.get("orders")),
                 "CLEANUP_FAILED", "R01", "fixtures", "User mất nhưng chưa có bằng chứng business cleanup.")
            self.fixture["state"] = "CLEANED"
            self.j.save()
            return
        if self.fixture.get("business_cleaned"):
            self.api("/users/" + uid, "DELETE", expected=(204, 404))
            need(self.resolve_user() is None, "CLEANUP_FAILED", "R01", "test user", "User test chưa bị xóa.")
            self.fixture["state"] = "CLEANED"
            self.j.save()
            return
        self.authenticate()  # recover a crashed run without ever saving its password
        # POST response may have been lost: list orders ONLY for our fixture customer.
        if self.fixture["state"] in ("CHECKOUT_PREPARED", "CHECKOUT_CREATED", "CLEANUP_PREPARED"):
            orders = self.http.get(self.base + "/api/v2/orders?customerId=" + uid)
            rows = orders if isinstance(orders, list) else orders.get("content", orders.get("data", []))
            need(isinstance(rows, list), "CLEANUP_FAILED", "R01", "orders", "Không tìm được danh sách order của fixture.")
            for order in rows:
                oid = order.get("id") or order.get("orderId")
                need(order.get("customerId", uid) == uid, "CLEANUP_CONFLICT", "R01", "order", "Order không thuộc test identity.")
                if oid and oid not in self.fixture["orders"]:
                    self.fixture["orders"].append(oid)
            self.j.save()
        self.fixture["state"] = "CLEANUP_PREPARED"
        self.j.save()
        for oid in self.fixture["orders"]:
            order = self.http.get(self.base + "/api/v2/orders/" + oid)
            if order["status"] != "CANCELLED":
                self.http.request(self.base + "/api/v2/orders/" + oid + "/cancel", "POST", {"reason": "SRE isolated acceptance cleanup"})
            check = self.http.get(self.base + "/api/v2/orders/" + oid)
            need(check["status"] == "CANCELLED", "CLEANUP_FAILED", "R01", "order", "Order test chưa được cancel.")
            self.fixture.setdefault("cancelled_orders", [])
            if oid not in self.fixture["cancelled_orders"]:
                self.fixture["cancelled_orders"].append(oid)
            self.j.save()
        pid = self.fixture.get("product_id")
        if not pid and self.fixture.get("sku"):
            pid = self.find_product()
            self.fixture["product_id"] = pid
            self.j.save()
        if pid:
            self.http.request(self.base + "/api/v2/products/" + pid, "DELETE", expected=(204, 404))
            status, content, _ = self.http.request(self.base + "/api/v2/products/" + pid, expected=(200, 404), raw=True)
            need(status == 404 or json.loads(content).get("is_active") is False,
                 "CLEANUP_FAILED", "R01", "product", "Sản phẩm test chưa inactive hoặc chưa bị xóa.")
        self.fixture.update({"business_cleaned": True, "state": "USER_DELETE_PREPARED"})
        self.j.save()
        # Logout is not required for durable business cleanup; the isolated user
        # is removed and the local cookie jar disappears when the process exits.
        try:
            self.http.request(self.base + "/api/v2/auth/logout", "POST", expected=(200, 204, 401))
        except Error as error:
            self.fixture["logout_warning"] = error.code
            self.j.save()
        self.api("/users/" + uid, "DELETE", expected=(204, 404))
        need(self.resolve_user() is None, "CLEANUP_FAILED", "R01", "test user", "User test chưa bị xóa.")
        self.fixture["state"] = "CLEANED"
        self.j.save()

    # Purpose: Tìm product theo SKU marker khi POST response bị mất.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Search SKU qua từng page → lọc SKU bằng nhau → ID duy nhất hoặc None; thiếu pagination → lỗi.
    # Kiến thức liên quan: urlencode tạo query; pages/total chứng minh đã đọc hết kết quả trước khi kết luận vắng mặt.
    def find_product(self):
        page, matches = 1, []
        while True:
            query = urllib.parse.urlencode({"search": self.fixture["sku"], "page": page, "page_size": 100})
            payload = self.http.get(self.base + "/api/v2/products?" + query)
            rows = payload if isinstance(payload, list) else payload.get("items", payload.get("data", []))
            need(isinstance(rows, list), "CLEANUP_FAILED", "R01", "product", "Không đọc được kết quả tìm SKU test.")
            matches.extend(p["id"] for p in rows if p.get("sku") == self.fixture["sku"])
            need(len(set(matches)) <= 1, "CLEANUP_CONFLICT", "R01", "product", "Marker SKU không duy nhất.")
            if isinstance(payload, list):
                break
            pages = payload.get("pages", payload.get("total_pages"))
            if pages is None:
                total = payload.get("total")
                need(type(total) is int, "CLEANUP_FAILED", "R01", "product", "Thiếu thông tin phân trang; chưa chứng minh SKU vắng mặt.")
                pages = (total + 99) // 100
            need(type(pages) is int and 0 <= pages <= 10000, "CLEANUP_FAILED", "R01", "product", "Thông tin phân trang không hợp lệ.")
            if page >= pages:
                break
            page += 1
        return matches[0] if matches else None
