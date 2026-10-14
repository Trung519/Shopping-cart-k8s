import subprocess
import unittest
from pathlib import Path
import yaml

CHART = Path(__file__).resolve().parents[3] / "charts/platform/shopping-integration"


# Purpose: Render chart integration và lấy Keycloak Deployment/ConfigMap.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
# Flow: Override properties nếu có → Helm → YAML resources → chọn đúng hai resource → tuple.
# Kiến thức liên quan: next(generator) chọn resource theo kind/name; properties="" khác None vì cần test tắt mount.
def render(properties=None):
    args = ["helm", "template", "integration", str(CHART)]
    if properties is not None:
        args += ["--set-string", "keycloak.requestLoggingProperties=" + properties]
    result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError("Integration render failed; output withheld")
    objects = list(yaml.safe_load_all(result.stdout))
    deployment = next(o for o in objects if o and o["kind"] == "Deployment" and o["metadata"]["name"] == "keycloak")
    config = next(o for o in objects if o and o["kind"] == "ConfigMap" and o["metadata"]["name"] == "keycloak-config")
    return deployment, config


class KeycloakLoggingTests(unittest.TestCase):
    # Purpose: Kiểm Keycloak mount logging config, có MDC IDs và checksum đổi khi config đổi.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Dựng input/fault riêng → render; kỳ vọng '/opt/keycloak/conf/quarkus.properties'.
    # Kiến thức liên quan: assertEqual so hai giá trị; assertIn kiểm phần tử tồn tại.
    def test_access_log_mount_format_and_config_rollout(self):
        deployment, config = render()
        pod = deployment["spec"]["template"]
        container = next(c for c in pod["spec"]["containers"] if c["name"] == "keycloak")
        mount = next(m for m in container["volumeMounts"] if m["name"] == "request-logging")
        self.assertEqual(mount["mountPath"], "/opt/keycloak/conf/quarkus.properties")
        self.assertIn("trace_id=%X{trace_id} span_id=%X{span_id}", config["data"]["KC_LOG_CONSOLE_FORMAT"])
        self.assertEqual(config["data"]["quarkus.properties"].splitlines(), [
            "quarkus.http.access-log.enabled=true", "quarkus.http.access-log.pattern=http_request_completed method=%m status=%s"])
        changed, _ = render("quarkus.http.access-log.enabled=false")
        self.assertNotEqual(pod["metadata"]["annotations"]["checksum/config"],
                            changed["spec"]["template"]["metadata"]["annotations"]["checksum/config"])

    # Purpose: Kiểm tắt logging properties không mount key ConfigMap không tồn tại.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Dựng input/fault riêng → render; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertNotIn yêu cầu không tồn tại phần tử.
    def test_disabled_properties_do_not_mount_missing_key(self):
        deployment, config = render("")
        pod = deployment["spec"]["template"]["spec"]
        self.assertNotIn("quarkus.properties", config["data"])
        self.assertNotIn("request-logging", [v["name"] for v in pod["volumes"]])


if __name__ == "__main__":
    unittest.main()
