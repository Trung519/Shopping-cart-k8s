{{- define "shopping-app.name" -}}{{- .Values.serviceName | trunc 63 | trimSuffix "-" -}}{{- end -}}
{{- define "shopping-app.namespace" -}}{{- default .Release.Namespace .Values.namespaceOverride -}}{{- end -}}
{{- define "shopping-app.labels" -}}
app.kubernetes.io/name: {{ include "shopping-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: shopping-cart
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}

