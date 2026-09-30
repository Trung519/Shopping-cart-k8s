{{- define "seller.name" -}}{{- .Values.serviceName | trunc 63 | trimSuffix "-" -}}{{- end -}}
{{- define "seller.namespace" -}}{{- default .Release.Namespace .Values.namespaceOverride -}}{{- end -}}
{{- define "seller.labels" -}}
app.kubernetes.io/name: {{ include "seller.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: shopping-cart
app.kubernetes.io/component: seller-management
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}
