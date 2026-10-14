import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sre_observability.config import yaml

CHART = Path(__file__).resolve().parents[3] / "charts/platform/shopping-observability"


# Purpose: Render chart offline để kiểm manifest thực tế.
# Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt; *collection unpack phần tử vào lời gọi hoặc list.
# Flow: Helm template + extra overrides → safe_load_all → list resource; exit lỗi → RuntimeError kín output.
# Kiến thức liên quan: subprocess capture_output giữ output riêng; PyYAML giải mã multi-document YAML.
def render(extra=()):
    result = subprocess.run(["helm", "template", "shopping-observability", str(CHART), "--namespace", "shopping-cart-observability", *extra],
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError("Helm render failed (output withheld)")
    return [obj for obj in yaml.safe_load_all(result.stdout) if obj]


class ChartTests(unittest.TestCase):
    # Purpose: Render chart một lần dùng chung các test không thay đổi manifest.
    # Syntax: @classmethod nhận class cls, không phải instance self.
    # Flow: unittest chuẩn bị class → render() → cls.objects.
    # Kiến thức liên quan: @classmethod nhận cls thay self; giảm số lần chạy Helm cho suite.
    @classmethod
    def setUpClass(cls):
        cls.objects = render()

    # Purpose: Kiểm alert RAM dùng namespace thực và không còn placeholder.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Dựng input/fault riêng → next → json.dumps; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertNotIn yêu cầu không tồn tại phần tử; assertIn kiểm phần tử tồn tại.
    def test_ram_alert_uses_real_namespace(self):
        rule = next(o for o in self.objects if o["kind"] == "PrometheusRule" and o["metadata"]["name"] == "shopmon-shopping-alerts")
        text = json.dumps(rule)
        self.assertNotIn('namespace=\\"monitoring\\"', text)
        self.assertNotIn("__OBS_NAMESPACE__", text)
        self.assertIn("shopping-cart-observability", text)

    # Purpose: Kiểm Collector chỉ có pipeline trace và trỏ đúng Tempo.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Dựng input/fault riêng → next → yaml.safe_load; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertEqual so hai giá trị.
    def test_collector_has_only_trace_pipeline(self):
        obj = next(o for o in self.objects if o["kind"] == "ConfigMap" and o["metadata"]["name"] == "otel-collector-config")
        config = yaml.safe_load(obj["data"]["collector.yaml"])
        self.assertEqual(set(config["service"]["pipelines"]), {"traces"})
        self.assertEqual(config["exporters"]["otlp/tempo"]["endpoint"], "tempo.shopping-cart-observability.svc.cluster.local:4317")

    # Purpose: Kiểm datasource/scrape YAML render xong, không còn Helm expression.
    # Syntax: and/or short-circuit: chỉ tính vế sau khi cần, tránh đọc dữ liệu chưa hợp lệ.
    # Flow: Dựng input/fault riêng → obj.get → decode; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertNotIn yêu cầu không tồn tại phần tử.
    def test_datasource_and_scrape_templates_resolved(self):
        for obj in self.objects:
            if obj["kind"] == "ConfigMap" and "datasources.yaml" in obj.get("data", {}):
                self.assertNotIn("{{ .", obj["data"]["datasources.yaml"])
            if obj["kind"] == "Secret" and "additional-scrape-configs.yaml" in obj.get("data", {}):
                import base64
                text = base64.b64decode(obj["data"]["additional-scrape-configs.yaml"]).decode()
                self.assertNotIn("{{", text)

    # Purpose: Kiểm Fluent Bit đọc namespace app và gửi đúng Loki service.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Dựng input/fault riêng → next; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertNotIn yêu cầu không tồn tại phần tử; assertIn kiểm phần tử tồn tại.
    def test_fluent_input_namespace_and_output_consistent(self):
        obj = next(o for o in self.objects if o["kind"] == "ConfigMap" and o["metadata"]["name"] == "fluent-bit")
        text = obj["data"]["fluent-bit.conf"]
        self.assertNotIn("{{", text)
        self.assertIn("loki-gateway.shopping-cart-observability.svc.cluster.local", text)
        self.assertIn("*_shopping-cart-apps_*.log", text)

    # Purpose: Kiểm Helm override endpoint/namespace thực sự đi vào manifest.
    # Syntax: comprehension/generator gom hoặc lọc phần tử; generator chỉ lấy giá trị khi được duyệt.
    # Flow: Dựng input/fault riêng → render; assertion xác nhận bằng chứng đúng hoặc lỗi được yêu cầu.
    # Kiến thức liên quan: assertIn kiểm phần tử tồn tại.
    def test_collector_override_and_namespace_contract(self):
        objects = render(["--set", "tracing.collector.tempoEndpoint=external-tempo.example:4317",
                          "--set", "global.observability.applicationNamespaces[0]=existing-app"])
        cm = next(o for o in objects if o["kind"] == "ConfigMap" and o["metadata"]["name"] == "otel-collector-config")
        self.assertIn("external-tempo.example:4317", cm["data"]["collector.yaml"])
        self.assertIn("existing-app", [o["metadata"]["namespace"] for o in objects if o["kind"] == "Telemetry"])


if __name__ == "__main__":
    unittest.main()
