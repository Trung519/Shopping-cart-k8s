"""Safe I/O. No subprocess output or credentials enter diagnostics by default."""
import base64
import copy
import fcntl
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class Error(Exception):
    # Purpose: Gom lỗi thành mã, bước, đối tượng và cách xử lý ngắn gọn.
    # Syntax: a,b = ... unpack và gán nhiều giá trị theo thứ tự; số phần tử phải khớp.
    # Flow: Ví dụ HTTP_STATUS/S09/orders → lưu thuộc tính và message cho report.
    # Kiến thức liên quan: Exception là kiểu lỗi gốc; super().__init__ đăng ký thông điệp lỗi.
    def __init__(self, code, step, subject, message, action="Xem report và sửa điều kiện bị thiếu."):
        super().__init__(message)
        self.code, self.step, self.subject = code, step, subject
        self.message, self.action = message, action

    # Purpose: Chuyển lỗi sang dữ liệu có thể ghi report.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Lấy code/step/subject/message/action từ đối tượng → dict, không thêm stdout/stderr.
    # Kiến thức liên quan: getattr(obj, tên) đọc thuộc tính bằng tên; Journal lưu dict này.
    def record(self):
        return {k: getattr(self, k) for k in ("code", "step", "subject", "message", "action")}


# Purpose: Dừng đúng bước khi điều kiện bắt buộc chưa đạt.
# Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
# Flow: condition=True → đi tiếp; False → raise Error với mã/bước và action mặc định.
# Kiến thức liên quan: Error giữ lỗi có cấu trúc; caller quyết định rollback, hàm này chỉ phát lỗi.
def need(condition, code, step, subject, message, action=None):
    if not condition:
        raise Error(code, step, subject, message, action or "Sửa điều kiện trên rồi chạy check lại.")


# Purpose: Tạo dấu vân tay để phát hiện cấu hình thay đổi sau plan.
# Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
# Flow: Dict cùng nội dung → JSON sắp xếp key → SHA-256 giống nhau dù thứ tự key khác.
# Kiến thức liên quan: json.dumps chuẩn hóa dữ liệu; hashlib.sha256 tạo hash, không phải mã hóa bí mật.
def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# Purpose: Ghi journal bền vững, tránh file JSON bị ghi dở khi process chết.
# Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi; finally luôn chạy để cleanup, dù nhánh try return hay phát lỗi.
# Flow: Tạo file tạm quyền 0600 → ghi và fsync → thay file đích → fsync thư mục; luôn dọn file tạm.
# Kiến thức liên quan: mkstemp tạo file riêng; os.replace thay file nguyên tử; fsync yêu cầu lưu xuống đĩa.
def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


# Purpose: Chặn credential inline trước khi dữ liệu đi vào journal.
# Syntax: raise ... from None ẩn exception gốc khỏi thông báo để tránh lộ dữ liệu.
# Flow: Duyệt dict/list và config JSON/YAML lồng nhau → gặp secret literal thì lỗi; hợp lệ trả bản sao.
# Kiến thức liên quan: Đệ quy kiểm từng tầng; regex chỉ là guard theo schema, không bảo đảm nhận diện mọi bí mật tùy ý.
def safe_snapshot(value):
    """Refuse secret-bearing objects instead of persisting a 'redacted' restore."""
    if isinstance(value, dict):
        if value.get("kind") == "Secret":
            raise Error("SNAPSHOT_UNSAFE", "S03", "Secret", "Không ghi nội dung Secret vào journal.")
        for key, item in value.items():
            # Secret refs/keys are safe; literal password/token fields are not.
            if re.search(r"(?i)(password|token|credential|private.?key|api.?key|client.?secret|authorization)$", str(key)) and item and not isinstance(item, dict):
                raise Error("SNAPSHOT_UNSAFE", "S03", "resource", "Resource chứa giá trị nhạy cảm inline.")
            if key == "name" and re.search(r"(?i)(password|token|secret|api.?key|credential|private.?key|authorization)", str(item)) and value.get("value"):
                raise Error("SNAPSHOT_UNSAFE", "S03", "env", "Env nhạy cảm phải dùng Secret reference.")
            safe_snapshot(item)
    elif isinstance(value, list):
        for item in value:
            safe_snapshot(item)
    elif isinstance(value, str):
        if value.lstrip().startswith(("{", "[")):
            try:
                safe_snapshot(json.loads(value))
            except ValueError:
                pass
        if re.search(r"://[^/\s:]+:[^/\s@]+@|-----BEGIN .*PRIVATE KEY|Bearer\s+\S+", value):
            raise Error("SNAPSHOT_UNSAFE", "S03", "resource", "Không snapshot credential trong URL/config.")
        if re.search(r"(?i)[?&](access_token|api_key|password|authorization)=[^&\s]+", value):
            raise Error("SNAPSHOT_UNSAFE", "S03", "URL", "Credential không được đặt trong query string.")
        # ConfigMap text may encode YAML credentials.
        if re.search(r"(?im)^\s*[\"']?(?:password|bot_token|access_token|client_secret|api_key|private_key|authorization)[\"']?\s*[:=]\s*\S+", value):
            raise Error("SNAPSHOT_UNSAFE", "S03", "config", "Config có credential inline.")
        if re.search(r"(?i)(password|token|secret|api.?key|credential|authorization)[\"']?\s*:", value):
            import yaml
            try:
                parsed = yaml.safe_load(value)
            except yaml.YAMLError:
                raise Error("SNAPSHOT_UNSAFE", "S03", "config", "Không phân tích được config có field nhạy cảm.") from None
            if isinstance(parsed, (dict, list)):
                safe_snapshot(parsed)
    return copy.deepcopy(value)


class Deadline:
    # Purpose: Tạo thời hạn chung cho một giai đoạn làm việc.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: seconds=30 → lưu mốc monotonic hiện tại + 30 giây.
    # Kiến thức liên quan: time.monotonic là đồng hồ thời lượng, không bị đổi giờ hệ thống.
    def __init__(self, seconds):
        self.end = time.monotonic() + seconds

    # Purpose: Giới hạn thời gian từng lệnh theo ngân sách còn lại.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Còn 8 giây, maximum=30 → trả 8; hết ngân sách → DEADLINE_EXCEEDED.
    # Kiến thức liên quan: need phát lỗi có cấu trúc; min tránh cho lệnh vượt deadline chung.
    def remaining(self, maximum=30):
        left = self.end - time.monotonic()
        need(left > 0, "DEADLINE_EXCEEDED", "runtime", "run", "Đã hết thời gian cho bước hiện tại.")
        return min(left, maximum)


class Runner:
    # Purpose: Cho các lệnh dùng chung một ngân sách thời gian.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: seconds=1800 → tạo Deadline cho toàn lượt chạy.
    # Kiến thức liên quan: Deadline.remaining được run dùng để giới hạn timeout subprocess.
    def __init__(self, seconds=1800):
        self.deadline = Deadline(seconds)

    # Purpose: Chạy công cụ và trả lỗi hữu ích mà không lộ output nhạy cảm.
    # Syntax: raise ... from None ẩn exception gốc khỏi thông báo để tránh lộ dữ liệu.
    # Flow: argv → subprocess có timeout; exit được phép → stdout; lỗi → phân loại hoặc COMMAND_FAILED.
    # Kiến thức liên quan: subprocess.run nhận argv riêng và stdin; capture_output giữ stderr kín; chỉ xuất thông điệp cố định.
    def run(self, argv, data=None, timeout=45, allowed=(0,)):
        try:
            result = subprocess.run(argv, input=data, text=True, capture_output=True,
                                    timeout=self.deadline.remaining(timeout))
        except subprocess.TimeoutExpired:
            raise Error("COMMAND_TIMEOUT", "runtime", Path(argv[0]).name, "Lệnh chưa hoàn tất trước deadline.") from None
        except OSError:
            raise Error("TOOL_MISSING", "S00", Path(argv[0]).name, "Không chạy được công cụ yêu cầu.") from None
        if result.returncode not in allowed:
            categories = (("forbidden", "RBAC_DENIED", "Thiếu quyền thực hiện lệnh."),
                          ("unauthorized", "AUTH_FAILED", "Thông tin xác thực không hợp lệ."),
                          ("connection refused", "DEPENDENCY_UNREACHABLE", "Dịch vụ chưa nhận kết nối."),
                          ("notfound", "RESOURCE_MISSING", "Không tìm thấy resource yêu cầu."),
                          ("conflict", "RESOURCE_CONFLICT", "Resource đã đổi; kiểm tra lại plan."))
            code, message = "COMMAND_FAILED", "Lệnh thất bại (exit " + str(result.returncode) + "); xem bước trong report."
            for pattern, candidate, summary in categories:
                if pattern in result.stderr.lower():
                    code, message = candidate, summary
                    break
            raise Error(code, "runtime", Path(argv[0]).name, message)
        return result.stdout


class Kube:
    # Purpose: Khóa mọi thao tác Kubernetes vào context được chọn.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: context=test → tạo prefix kubectl --context test và request-timeout=15s.
    # Kiến thức liên quan: Runner kiểm deadline; context xác định cluster, không tự fallback sang cluster khác.
    def __init__(self, context, runner):
        self.prefix = ["kubectl", "--context", context, "--request-timeout=15s"]
        self.runner = runner

    # Purpose: Cổng chung cho lệnh Kubernetes có kiểm deadline.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: args=[get,pods] → ghép prefix context → Runner.run → stdout.
    # Kiến thức liên quan: Runner.run chịu trách nhiệm timeout và lỗi đã lọc.
    def cmd(self, args, data=None, timeout=45):
        return self.runner.run(self.prefix + args, data, timeout)

    # Purpose: Đọc resource Kubernetes dưới dạng dict, có chế độ cho phép chưa tồn tại.
    # Syntax: X if C else Y chọn X khi điều kiện C đúng, còn lại dùng Y (fallback).
    # Flow: GeneratedScrapeConfig → đọc Secret; optional=True thêm ignore-not-found; output rỗng → None.
    # Kiến thức liên quan: json.loads giải mã JSON; optional chỉ bỏ qua resource thiếu, không bỏ qua lỗi quyền/kết nối.
    def get(self, kind, name=None, namespace=None, optional=False):
        kind = "Secret" if kind == "GeneratedScrapeConfig" else kind
        args = (["-n", namespace] if namespace else []) + ["get", kind]
        if name:
            args.append(name)
        if optional:
            args.append("--ignore-not-found")
        result = self.cmd(args + ["-o", "json", "--show-managed-fields=true"])
        return json.loads(result) if result.strip() else None

    # Purpose: Gửi JSON Patch mà không đưa payload vào argv.
    # Syntax: X if C else Y chọn X khi điều kiện C đúng, còn lại dùng Y (fallback).
    # Flow: Danh sách test/add/remove → JSON trên stdin → kubectl patch resource.
    # Kiến thức liên quan: JSON Patch kiểm resourceVersion trước ghi; manager giữ attribution cho restore resource Argo; public scrape dùng kind Secret ở API.
    def patch(self, kind, name, namespace, patch, manager=None):
        kind = "Secret" if kind == "GeneratedScrapeConfig" else kind
        args = ["-n", namespace, "patch", kind, name, "--type=json", "--patch-file=/dev/stdin"]
        if manager:
            args.append("--field-manager=" + manager)
        return self.cmd(args, json.dumps(patch))

    # Purpose: Kiểm quyền trước khi deploy hoặc restore.
    # Syntax: X if C else Y chọn X khi điều kiện C đúng, còn lại dùng Y (fallback).
    # Flow: verb=patch, kind=Deployment → auth can-i → chỉ yes mới trả True.
    # Kiến thức liên quan: RBAC quyết định quyền; exit 1 của can-i có thể là kết quả no hợp lệ.
    def can(self, verb, kind, namespace):
        kind = "Secret" if kind == "GeneratedScrapeConfig" else kind
        return self.runner.run(self.prefix + ["auth", "can-i", verb, kind, "-n", namespace], allowed=(0, 1)).strip() == "yes"


class Journal:
    # Purpose: Mở journal cũ để recover hoặc tạo journal mới.
    # Syntax: X if C else Y chọn X khi điều kiện C đúng, còn lại dùng Y (fallback).
    # Flow: initial có dữ liệu → kiểm dict và save; không có → đọc JSON từ path.
    # Kiến thức liên quan: Journal là nhật ký ý định và tiến độ phục hồi, không phải log raw command.
    def __init__(self, path, initial=None):
        self.path = Path(path)
        self.data = initial if initial is not None else json.loads(self.path.read_text())
        need(isinstance(self.data, dict), "JOURNAL_INVALID", "S00", "journal", "Journal không có cấu trúc hợp lệ.")
        if initial is not None:
            self.save()

    # Purpose: Chặn dữ liệu nhạy cảm rồi ghi journal an toàn.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: self.data → safe_snapshot → atomic; guard lỗi thì chưa ghi file.
    # Kiến thức liên quan: safe_snapshot kiểm payload; atomic đảm bảo thay file và fsync.
    def save(self):
        safe_snapshot(self.data)
        atomic(self.path, self.data)

    # Purpose: Ghi kết quả một bước để biết lượt chạy đã tới đâu.
    # Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
    # Flow: S04/PASS/details → thêm timestamp vào steps → save.
    # Kiến thức liên quan: setdefault tạo list khi chưa có; time.time là thời gian dùng trong report.
    def step(self, name, state="PASS", details=None):
        self.data.setdefault("steps", []).append({"step": name, "state": state,
                                                 "time": time.time(), "details": details or {}})
        self.save()


class LocalLock:
    # Purpose: Chặn hai process cùng thao tác một scope trên máy này.
    # Syntax: raise ... from None ẩn exception gốc khỏi thông báo để tránh lộ dữ liệu.
    # Flow: Mở lock file → flock không chờ; đã có owner → RUN_BUSY.
    # Kiến thức liên quan: fcntl.flock là lock của hệ điều hành; Kubernetes Lease bổ sung khóa giữa các máy.
    def __init__(self, path):
        self.file = open(path, "a+")
        try:
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.file.close()
            raise Error("RUN_BUSY", "S01", "lock", "Một lượt khác đang chạy cùng scope.") from None

    # Purpose: Nhả lock local khi kết thúc lượt chạy.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Đóng file descriptor → hệ điều hành nhả flock.
    # Kiến thức liên quan: Lock gắn với file descriptor; file lock còn tồn tại không có nghĩa đang bị khóa.
    def close(self):
        self.file.close()


class Forwards:
    # Purpose: Theo dõi tunnel do lượt chạy sở hữu và cache để tái sử dụng.
    # Syntax: a,b = ... unpack và gán nhiều giá trị theo thứ tự; số phần tử phải khớp.
    # Flow: Lưu kube/log_dir; owned=[] chứa process, cache={} chứa URL theo service.
    # Kiến thức liên quan: Chỉ process trong owned mới được close dừng.
    def __init__(self, kube, log_dir):
        self.kube, self.log_dir, self.owned = kube, log_dir, []
        self.cache = {}

    # Purpose: Mở hoặc tái dùng kết nối local tới Service để test.
    # Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
    # Flow: (ns,service,80) đã có process sống → dùng URL cũ; chưa có → mở random port, chờ ready.
    # Kiến thức liên quan: Popen chạy port-forward; TemporaryFile giữ output riêng; poll kiểm process còn sống.
    def open(self, namespace, service, port):
        key = (namespace, service, port)
        cached = self.cache.get(key)
        if cached and cached[0].poll() is None:
            return cached[1]
        log = tempfile.TemporaryFile(dir=self.log_dir)
        process = subprocess.Popen(self.kube.prefix + ["-n", namespace, "port-forward",
                                   "svc/" + service, ":" + str(port), "--address=127.0.0.1"],
                                   stdout=log, stderr=subprocess.STDOUT)
        self.owned.append((process, log))
        end = time.monotonic() + min(30, self.kube.runner.deadline.remaining(30))
        while time.monotonic() < end:
            need(process.poll() is None, "PORT_FORWARD_FAILED", "verify", service, "Không mở được kết nối kiểm tra.")
            log.seek(0)
            match = re.search(rb"Forwarding from 127\.0\.0\.1:(\d+)", log.read())
            if match:
                url = "http://127.0.0.1:" + match[1].decode()
                self.cache[key] = (process, url)
                return url
            time.sleep(.2)
        raise Error("PORT_FORWARD_TIMEOUT", "verify", service, "Hết thời gian mở kết nối kiểm tra.")

    # Purpose: Dọn hết tunnel thuộc lượt chạy.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: Duyệt owned ngược → terminate, quá 3 giây thì kill → đóng log → xóa cache.
    # Kiến thức liên quan: terminate gửi yêu cầu dừng; kill là fallback khi process không kết thúc.
    def close(self):
        for process, log in reversed(self.owned):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            log.close()
        self.owned.clear()
        self.cache.clear()


class BackendRedirect(urllib.request.HTTPRedirectHandler):
    # Purpose: Không cho backend redirect mang auth header/body sang origin khác.
    # Syntax: lambda url: (...) tạo hàm trả origin; super() gọi handler cha sau khi guard đạt.
    # Flow: So scheme/host/port URL cũ và mới → khác origin/userinfo thì dừng; cùng origin mới tạo request.
    # Kiến thức liên quan: Origin gồm scheme, hostname, port; Keycloak/Grafana admin dùng handler này mặc định.
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        old, new = urllib.parse.urlsplit(request.full_url), urllib.parse.urlsplit(newurl)
        origin = lambda url: (url.scheme, url.hostname, url.port or (443 if url.scheme == "https" else 80))
        need(origin(old) == origin(new) and not new.username and not new.password,
             "HTTP_REDIRECT_INVALID", "verify", "endpoint", "Backend redirect sang origin khác; đã chặn.")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class HTTP:
    # Purpose: Cấu hình client HTTP dùng timeout và opener phù hợp.
    # Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
    # Flow: Có opener → dùng nó; không có → client bỏ proxy hệ thống; lưu deadline nếu được cấp.
    # Kiến thức liên quan: urllib opener ghép các handler; GatewayHandler định tuyến request qua tunnel.
    def __init__(self, timeout=10, opener=None, deadline=None):
        self.timeout = timeout
        self.deadline = deadline
        self.opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), BackendRedirect())

    # Purpose: Gọi HTTP, kiểm status/schema và tránh retry mù các lệnh ghi.
    # Syntax: with giữ context rồi tự thoát/đóng hoặc nhả patch, kể cả khi có lỗi; raise ... from None ẩn exception gốc khỏi thông báo để tránh lộ dữ liệu.
    # Flow: Dict body → JSON; GET tối đa 3 lần; POST 1 lần; status đúng → JSON hoặc raw tuple.
    # Kiến thức liên quan: urllib.HTTPError vẫn có status/body; raw trả (status,bytes,headers); Deadline giới hạn từng lần gọi.
    def request(self, url, method="GET", body=None, headers=None, expected=(200,), raw=False):
        headers = dict(headers or {})
        if body is not None:
            if isinstance(body, dict) or isinstance(body, list):
                body = json.dumps(body).encode()
                headers.setdefault("Content-Type", "application/json")
            elif isinstance(body, str):
                body = body.encode()
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        attempts = 3 if method == "GET" else 1  # never retry writes with uncertain outcomes
        for attempt in range(attempts):
            timeout = self.deadline.remaining(self.timeout) if self.deadline else self.timeout
            try:
                response = self.opener.open(req, timeout=timeout)
            except urllib.error.HTTPError as error:
                response = error
            except (OSError, urllib.error.URLError):
                if attempt + 1 < attempts:
                    time.sleep(.2 * (attempt + 1))
                    continue
                raise Error("HTTP_UNREACHABLE", "verify", "endpoint", "Không kết nối được endpoint kiểm tra.") from None
            with response:
                status, content, result_headers = response.code, response.read(), response.headers
            if status in (429, 502, 503, 504) and attempt + 1 < attempts:
                time.sleep(.2 * (attempt + 1))
                continue
            break
        code = "AUTH_FAILED" if status in (401, 403) else "HTTP_STATUS"
        route = re.sub(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", "{id}", urllib.parse.urlsplit(url).path)
        need(status in expected, code, "verify", route, "HTTP " + str(status) + "; khác contract.")
        if raw:
            return status, content, result_headers
        try:
            return json.loads(content) if content else None
        except ValueError:
            raise Error("RESPONSE_INVALID", "verify", "endpoint", "Endpoint không trả JSON hợp lệ.") from None

    # Purpose: Viết gọn request GET trả JSON.
    # Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
    # Flow: url và headers → request dùng method mặc định GET → dữ liệu JSON.
    # Kiến thức liên quan: HTTP.request quản lý status, retry đọc và timeout.
    def get(self, url, headers=None):
        return self.request(url, headers=headers)


# Purpose: Lấy credential cần dùng trong RAM từ Secret có sẵn.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: Thiếu key → SECRET_MISSING; đủ key → base64 decode thành dict chỉ giữ trong RAM.
# Kiến thức liên quan: Base64 là định dạng của Kubernetes Secret, không phải mã hóa; không ghi kết quả vào journal.
def secret(kube, namespace, name, keys):
    data = (kube.get("secret", name, namespace).get("data") or {})
    need(all(data.get(k) for k in keys), "SECRET_MISSING", "S03", name, "Secret thiếu key bắt buộc.")
    return {key: base64.b64decode(data[key]).decode() for key in keys}


# Purpose: Biến tín hiệu dừng thành nhánh phục hồi của caller.
# Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
# Flow: SIGINT/SIGTERM → raise KeyboardInterrupt để thoát qua cleanup/rollback.
# Kiến thức liên quan: KeyboardInterrupt thuộc BaseException; caller phải bắt riêng cùng Exception.
def interrupt(signum, frame):
    raise KeyboardInterrupt()


# Purpose: Cho Ctrl+C và yêu cầu terminate đi qua luồng phục hồi.
# Syntax: không có cú pháp nâng cao; trọng tâm là input/output và hàm được gọi bên dưới.
# Flow: Đăng ký interrupt làm handler của SIGINT và SIGTERM.
# Kiến thức liên quan: signal.signal thay handler process; không xử lý được SIGKILL nên cần recover bằng journal.
def install_signals():
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
