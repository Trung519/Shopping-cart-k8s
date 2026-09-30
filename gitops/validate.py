#!/usr/bin/env python3
"""Validate the service catalog and render all Helm charts without contacting Kubernetes."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def documents(text):
    result = subprocess.run(
        ["ruby", "-ryaml", "-rjson", "-e", "puts JSON.generate(YAML.load_stream(STDIN.read))"],
        input=text, text=True, capture_output=True, check=True,
    )
    return [document for document in json.loads(result.stdout) if document]


def main():
    project = documents((ROOT / "gitops/control-plane/project.yaml").read_text())[0]
    appset = documents((ROOT / "gitops/control-plane/services.yaml").read_text())[0]
    bootstrap = documents((ROOT / "gitops/bootstrap/root-app.yaml").read_text())[0]
    assert bootstrap["spec"]["source"]["path"] == "gitops/control-plane"
    assert appset["spec"]["syncPolicy"]["preserveResourcesOnDeletion"] is True
    assert appset["spec"]["syncPolicy"]["applicationsSync"] == "create-update"
    template = appset["spec"]["template"]["spec"]
    assert "automated" not in template.get("syncPolicy", {})
    assert template["project"] == project["metadata"]["name"]
    repo = bootstrap["spec"]["source"]["repoURL"]
    for source in template["sources"]:
        assert source["repoURL"] == repo and source["targetRevision"] == "dev"
    namespaces = {item["namespace"] for item in project["spec"]["destinations"]}
    cluster_allowed = {(item["group"], item["kind"]) for item in project["spec"]["clusterResourceWhitelist"]}
    cluster_kinds = {"Namespace", "ClusterSecretStore", "ClusterRole", "ClusterRoleBinding", "CustomResourceDefinition", "PersistentVolume"}
    names, resources = set(), set()
    total = 0
    for entry in appset["spec"]["generators"][0]["list"]["elements"]:
        name, namespace = entry["name"], entry["namespace"]
        assert name not in names, f"Duplicate Application: {name}"
        names.add(name)
        assert namespace in namespaces, f"Destination not allowed: {name}"
        chart = ROOT / entry["chartPath"]
        assert (chart / "Chart.yaml").is_file(), f"Missing chart: {name}"
        # Resolve exactly the template's declared values in precedence order.
        values = [path.replace("$values/", "").replace("{{.valuesPath}}", entry["valuesPath"])
                  for path in template["sources"][0]["helm"]["valueFiles"]]
        command = ["helm", "template", name, str(chart), "--namespace", namespace]
        for value in values:
            path = (ROOT / value).resolve()
            assert ROOT in path.parents and path.is_file(), f"Missing/invalid values file: {name}"
            command += ["-f", str(path)]
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(f"Helm render failed for {name}; rendered credentials are not printed")
        rendered = documents(result.stdout)
        images = []
        for document in rendered:
            kind = document["kind"]
            api = document["apiVersion"]
            group = api.split("/")[0] if "/" in api else ""
            metadata = document.get("metadata", {})
            ns = "" if kind in cluster_kinds else metadata.get("namespace", namespace)
            if kind in cluster_kinds:
                assert (group, kind) in cluster_allowed, f"Cluster kind not allowed: {name}: {group}/{kind}"
            else:
                assert ns in namespaces, f"Rendered namespace not allowed: {name}: {ns}"
            identity = (group, kind, ns, metadata.get("name"))
            assert identity not in resources, f"Resource shared by Applications: {identity}"
            resources.add(identity)
            if kind == "Deployment" and metadata.get("name") == "frontend":
                images = [container["image"] for container in document["spec"]["template"]["spec"]["containers"]]
        total += len(rendered)
        print(f"PASS {name}: {len(rendered)} resources")
        if images:
            print("Frontend image: " + ", ".join(images))
    print(f"Validated {len(names)} Applications / {total} resources; no duplicate ownership. No cluster changes.")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, RuntimeError, subprocess.CalledProcessError, KeyError) as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        sys.exit(1)
