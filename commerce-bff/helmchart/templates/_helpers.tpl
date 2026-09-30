{{- define "commerce-bff.name" -}}{{- .Values.serviceName | trunc 63 | trimSuffix "-" -}}{{- end -}}
{{- define "commerce-bff.namespace" -}}{{- default .Release.Namespace .Values.namespaceOverride -}}{{- end -}}
{{- define "commerce-bff.labels" -}}
app.kubernetes.io/name: {{ include "commerce-bff.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: shopping-cart
app.kubernetes.io/component: edge-api
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}
