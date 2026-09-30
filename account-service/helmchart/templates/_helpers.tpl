{{- define "account.name" -}}{{- .Values.serviceName | trunc 63 | trimSuffix "-" -}}{{- end -}}
{{- define "account.namespace" -}}{{- default .Release.Namespace .Values.namespaceOverride -}}{{- end -}}
{{- define "account.labels" -}}
app.kubernetes.io/name: {{ include "account.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: shopping-cart
app.kubernetes.io/component: identity-administration
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}
