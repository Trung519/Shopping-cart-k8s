{{- define "integration.labels" -}}
app.kubernetes.io/part-of: shopping-cart
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "integration.externalSecret" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $namespace := .namespace -}}
{{- $targetName := .targetName -}}
{{- $remoteKey := .remoteKey -}}
{{- $properties := .properties -}}
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: {{ $name }}
  namespace: {{ $namespace }}
  labels:
    {{- include "integration.labels" $root | nindent 4 }}
spec:
  refreshInterval: {{ $root.Values.externalSecrets.refreshInterval }}
  secretStoreRef:
    name: {{ $root.Values.externalSecrets.storeName }}
    kind: ClusterSecretStore
  target:
    name: {{ $targetName }}
    creationPolicy: Owner
  data:
    {{- range $secretKey, $property := $properties }}
    - secretKey: {{ $secretKey }}
      remoteRef:
        key: {{ $remoteKey }}
        property: {{ $property }}
    {{- end }}
{{- end -}}

