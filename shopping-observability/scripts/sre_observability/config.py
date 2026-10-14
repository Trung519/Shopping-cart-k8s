"""One YAML dependency; explicit validation gives useful operator errors."""
import copy
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from .core import Error, digest, need, safe_snapshot

try:
    import yaml
except ImportError:
    yaml = None

ENV = {"KUBE_CONTEXT": "context", "DEPLOY_TIMEOUT_SECONDS": "timeout",
       "STEP_TIMEOUT_SECONDS": "step_timeout", "TELEMETRY_WAIT_SECONDS": "telemetry_wait",
       "ROLLBACK_TIMEOUT_SECONDS": "rollback_timeout", "MIN_FREE_MEMORY_MIB": "min_memory_mib"}


# Purpose: Đọc YAML với lỗi rõ khi thiếu dependency hoặc file sai.
# Syntax: raise ... from None ẩn exception gốc khỏi thông báo để tránh lộ dữ liệu.
# Flow: Chưa có PyYAML → DEPENDENCY_MISSING; file đọc được → safe_load; lỗi → CONFIG_INVALID.
# Kiến thức liên quan: yaml.safe_load chỉ tạo kiểu dữ liệu cơ bản, không thực thi object YAML.
def load_yaml(path):
    need(yaml is not None, "DEPENDENCY_MISSING", "S00", "PyYAML", "Chưa cài PyYAML.",
         "Cài requirements.txt bằng Python dùng chạy script.")
    try:
        return yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError):
        raise Error("CONFIG_INVALID", "S00", Path(path).name, "Không đọc được YAML hợp lệ.") from None


# Purpose: Cho user override từng phần mà giữ default còn lại.
# Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
# Flow: base={a:1,b:2}, override={a:3} → {a:3,b:2}; dict con được merge đệ quy.
# Kiến thức liên quan: deepcopy tránh sửa base; merge đệ quy chỉ cho mapping, list được thay toàn bộ.
def merge(base, override):
    result = copy.deepcopy(base)
    for key, value in override.items():
        result[key] = merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
    return result


# Purpose: Không cho biến sai tên/kiểu âm thầm dùng fallback.
# Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
# Flow: Đối chiếu override với schema profile → sai field/kiểu/rỗng thì CONFIG_INVALID.
# Kiến thức liên quan: type(value) is type(base) phân biệt bool với int; đệ quy kiểm mapping và phần tử list.
def validate_override(base, value, path="config"):
    if base is None:
        need(value is None or isinstance(value, str), "CONFIG_INVALID", "S00", path, "Cần string hoặc null.")
    elif isinstance(base, dict):
        need(isinstance(value, dict), "CONFIG_INVALID", "S00", path, "Cần mapping YAML.")
        unknown = set(value) - set(base)
        need(not unknown, "CONFIG_INVALID", "S00", path, "Biến chưa hỗ trợ: " + ",".join(sorted(unknown)))
        for key, child in value.items():
            validate_override(base[key], child, path + "." + key)
    elif isinstance(base, list):
        need(isinstance(value, list) and (not base or bool(value)), "CONFIG_INVALID", "S00", path, "Cần list không rỗng.")
        for child in value:
            if base:
                validate_override(base[0], child, path + "[]")
    else:
        need(type(value) is type(base) and (not isinstance(value, str) or bool(value)), "CONFIG_INVALID", "S00", path, "Sai kiểu hoặc giá trị rỗng.")


# Purpose: Phát hiện contract thiếu bằng chứng trước khi tạo fixture.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: Kiểm route/checkout → ID duy nhất, HTTP/status, services/logs, DB/edge/metric hợp lệ → cho đi tiếp.
# Kiến thức liên quan: Contract là tiêu chí nghiệm thu; AMQP cần exact_parent/link, mesh log không thay app log.
def validate_contract(contract):
    need(isinstance(contract, dict) and isinstance(contract.get("routes"), list) and contract["routes"],
         "CONTRACT_INCOMPLETE", "S00", "routes", "Contract cần route list không rỗng.")
    need(not set(contract) - {"adapter", "routes", "checkout"}, "CONTRACT_INCOMPLETE", "S00", "contract", "Contract có field chưa hỗ trợ.")
    need(contract.get("adapter") == "shopping-cart" and isinstance(contract.get("checkout"), dict),
         "CONTRACT_INCOMPLETE", "S00", "checkout", "Adapter shopping-cart cần checkout contract.")
    fields = {"id", "method", "path", "expected", "authenticated", "services", "logs", "mesh_logs", "scope", "response", "edges", "databases", "application_metrics"}
    ids = set()
    for route in contract["routes"] + [contract["checkout"]]:
        need(isinstance(route, dict) and not set(route) - fields, "CONTRACT_INCOMPLETE", "S00", "route", "Route có field chưa hỗ trợ.")
        name = route.get("id")
        need(isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9_.-]+", name) and name not in ids,
             "CONTRACT_INCOMPLETE", "S00", "route.id", "Route ID phải hợp lệ và duy nhất.")
        ids.add(name)
        for key in ("services", "logs", "mesh_logs"):
            values = route.get(key, [] if key == "mesh_logs" else None)
            need(isinstance(values, list) and all(isinstance(v, str) and re.fullmatch(r"[a-zA-Z0-9_.-]+", v) for v in values) and len(set(values)) == len(values),
                 "CONTRACT_INCOMPLETE", "S00", name, key + " cần list tên service duy nhất.")
        need(route["services"], "CONTRACT_INCOMPLETE", "S00", name, "Thiếu service cần chứng minh trace.")
        scope = route.get("scope", "application")
        need(scope in ("application", "mesh-http-only"), "CONTRACT_INCOMPLETE", "S00", name, "Scope chưa được hỗ trợ.")
        services = set(route["services"])
        if scope == "application":
            need(set(route["logs"]) == services and not route.get("mesh_logs"), "CONTRACT_INCOMPLETE", "S00", name, "App scope cần app log cho từng service.")
        else:
            need(not route["logs"] and set(route.get("mesh_logs", [])) == {s.split(".")[0] for s in services},
                 "CONTRACT_INCOMPLETE", "S00", name, "Mesh scope cần mesh log tương ứng; không nhận là app SDK.")
        for key in ("edges", "databases", "application_metrics"):
            need(isinstance(route.get(key, []), list), "CONTRACT_INCOMPLETE", "S00", name, key + " phải là list.")
        for edge in route.get("edges", []):
            need(isinstance(edge, dict) and not set(edge) - {"from", "to", "type", "relation"} and
                 all(isinstance(edge.get(k), str) for k in ("from", "to", "type")) and isinstance(edge.get("relation", "ancestor"), str) and
                 edge.get("from") in services and edge.get("to") in services and
                 edge.get("type") in ("http", "rabbitmq") and edge.get("relation", "ancestor") in ("ancestor", "exact_parent", "link") and
                 (edge["type"] != "rabbitmq" or edge.get("relation") in ("exact_parent", "link")),
                 "CONTRACT_INCOMPLETE", "S00", name, "Edge cần service hợp lệ và quan hệ HTTP/AMQP rõ ràng.")
        for database in route.get("databases", []):
            need(isinstance(database, dict) and set(database) == {"service", "system"} and isinstance(database["service"], str) and database["service"] in services and
                 database["system"] in ("redis", "postgresql", "mysql", "mongodb"), "CONTRACT_INCOMPLETE", "S00", name, "Database proof không hợp lệ.")
        for metric in route.get("application_metrics", []):
            need(isinstance(metric, dict) and set(metric) == {"service", "query", "freshness_query"} and isinstance(metric["service"], str) and metric["service"] in services and
                 all(isinstance(metric[k], str) and bool(metric[k].strip()) for k in ("query", "freshness_query")),
                 "CONTRACT_INCOMPLETE", "S00", name, "App metric cần service, counter query và freshness_query (tuổi scrape giây).")
        metric_services = [metric["service"] for metric in route.get("application_metrics", [])]
        need(len(metric_services) == len(set(metric_services)), "CONTRACT_INCOMPLETE", "S00", name, "Chỉ khai báo một counter app cho mỗi service/route.")
        if route is not contract["checkout"]:
            need(route.get("method") == "GET" and isinstance(route.get("path"), str) and route["path"].startswith("/") and not route["path"].startswith("//"),
                 "CONTRACT_INCOMPLETE", "S00", name, "Route cần GET và path bắt đầu bằng /.")
            need(isinstance(route.get("expected"), list) and route["expected"] and all(type(code) is int and 100 <= code <= 599 for code in route["expected"]),
                 "CONTRACT_INCOMPLETE", "S00", name, "Expected cần list HTTP status hợp lệ.")
            need(type(route.get("authenticated")) is bool and route.get("response", "json") in ("json", "html"),
                 "CONTRACT_INCOMPLETE", "S00", name, "Thiếu authenticated hoặc response sai loại.")
        else:
            need(name == "checkout" and scope == "application" and not set(route) & {"method", "path", "expected", "authenticated", "response"},
                 "CONTRACT_INCOMPLETE", "S00", name, "Checkout dùng flow adapter cố định; chỉ khai báo các bằng chứng cần kiểm.")
    need(any(not r["authenticated"] and r.get("response") != "html" for r in contract["routes"]),
         "CONTRACT_INCOMPLETE", "S00", "baseline", "Cần public JSON route để kiểm baseline.")


# Purpose: Gom biến có default và kiểm cấu hình cuối cùng trước chạy.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt; raise ... from None ẩn exception gốc khỏi thông báo để tránh lộ dữ liệu.
# Flow: Profile → YAML override → environment → CLI → validate contract/port/Secret refs → config.
# Kiến thức liên quan: Path.resolve tạo đường dẫn tuyệt đối; safe_snapshot chặn credential inline; sources ghi nguồn từng biến.
def load(path=None, context=None, allow_writes=None):
    script_dir = Path(__file__).resolve().parents[1]
    default = script_dir / "config/profiles/shopping-cart-local.yaml"
    config = load_yaml(default)
    sources = {key: "profile" for key in config}
    if path:
        user = load_yaml(path)
        need(isinstance(user, dict), "CONFIG_INVALID", "S00", "config", "Config phải là mapping YAML.")
        unknown = set(user) - set(config)
        need(not unknown, "CONFIG_INVALID", "S00", "config", "Tên biến chưa được hỗ trợ: " + ",".join(sorted(unknown)))
        validate_override(config, user)
        config = merge(config, user)
        sources.update({key: "config" for key in user})
    for env, key in ENV.items():
        if env in os.environ:
            value = os.environ[env]
            need(value != "", "CONFIG_INVALID", "S00", env, "Biến được khai báo nhưng rỗng.")
            try:
                config[key] = value if key == "context" else int(value)
            except ValueError:
                raise Error("CONFIG_INVALID", "S00", env, "Biến này phải là số nguyên.") from None
            sources[key] = "environment"
    if context is not None:
        config["context"], sources["context"] = context, "CLI"
    if allow_writes is not None:
        config["allow_test_writes"], sources["allow_test_writes"] = allow_writes, "CLI"
    config["repo_root"] = str(script_dir.parents[1]) if config["repo_root"] == "auto" else str(Path(config["repo_root"]).resolve())
    config["log_dir"] = str(script_dir.parents[3] / "Log_agents")
    for key in ("context", "argo_namespace", "obs_namespace", "obs_app", "repo_root"):
        need(isinstance(config.get(key), str) and bool(config[key]), "CONFIG_MISSING", "S00", key, "Thiếu biến bắt buộc.")
    for key in ("timeout", "step_timeout", "telemetry_wait", "rollback_timeout", "min_memory_mib", "plan_ttl", "stability_seconds"):
        need(type(config.get(key)) is int and config[key] > 0, "CONFIG_INVALID", "S00", key, "Cần số nguyên dương.")
    need(type(config["allow_test_writes"]) is bool, "CONFIG_INVALID", "S00", "allow_test_writes", "Cần true hoặc false.")
    need(config["sync_mode"] == "selected", "CONFIG_INVALID", "S00", "sync_mode",
         "V1 chỉ reconcile resource đã liệt kê; prerequisites/hooks phải tồn tại.")
    try:
        gateway_url = urlsplit(config["gateway"]["base_url"])
        gateway_port = gateway_url.port or 80
    except ValueError:
        raise Error("CONFIG_INVALID", "S00", "base_url", "Gateway URL/port không hợp lệ.") from None
    need(isinstance(config["gateway"]["allowed_ports"], list) and config["gateway"]["allowed_ports"] and
         all(type(port) is int and 1 <= port <= 65535 for port in config["gateway"]["allowed_ports"]),
         "CONFIG_INVALID", "S00", "allowed_ports", "Allowlist cần các port số nguyên hợp lệ.")
    need(gateway_url.scheme == "http" and gateway_url.hostname in config["gateway"]["allowed_hosts"] and
         gateway_port in config["gateway"]["allowed_ports"] and not gateway_url.username and not gateway_url.password,
         "CONFIG_INVALID", "S00", "base_url", "Gateway V1 cần HTTP và host/port trong allowlist.")
    need(config["contract"] and config["managed_apps"], "CONTRACT_INCOMPLETE", "S00", "contract", "Thiếu contract/app scope.")
    contract_path = script_dir / config["contract"]
    contract = load_yaml(contract_path)
    validate_contract(contract)
    safe_snapshot(contract)
    for key in ("notification_required", "redis_server_metrics_required"):
        need(type(config[key]) is bool, "CONFIG_INVALID", "S00", key, "Cần true hoặc false.")
    for mapping in ("gateway", "auth", "grafana", "rabbitmq", "mesh", "backends"):
        need(isinstance(config[mapping], dict), "CONFIG_INVALID", "S00", mapping, "Cấu hình cần là mapping.")
    for service in [config["gateway"], config["auth"], config["grafana"], config["rabbitmq"], *config["backends"].values()]:
        need(type(service.get("port")) is int and 1 <= service["port"] <= 65535,
             "CONFIG_INVALID", "S00", "port", "Port phải trong 1..65535.")
    safe_snapshot(config)
    config["contract_data"] = contract
    config["sources"] = sources
    return config


# Purpose: Phát hiện config plan khác config deploy.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: Bỏ sources/log_dir khỏi dict → digest cấu hình thực thi còn lại.
# Kiến thức liên quan: digest chuẩn hóa JSON rồi hash; đường dẫn report không làm đổi nội dung triển khai.
def fingerprint(config):
    return digest({k: v for k, v in config.items() if k not in ("sources", "log_dir")})
