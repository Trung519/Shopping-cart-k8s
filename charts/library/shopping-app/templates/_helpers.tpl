{{/*
Common helpers. Values contract used by every application chart:
  serviceName, namespaceOverride, component (optional), commonLabels (optional).
*/}}
{{- define "shopping-app.name" -}}
{{- .Values.serviceName | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "shopping-app.namespace" -}}
{{- default .Release.Namespace .Values.namespaceOverride -}}
{{- end -}}

{{- define "shopping-app.selectorLabels" -}}
app.kubernetes.io/name: {{ include "shopping-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "shopping-app.labels" -}}
{{ include "shopping-app.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: shopping-cart
{{- with .Values.component }}
app.kubernetes.io/component: {{ . }}
{{- end }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}

{{/* Pod annotation value: changes only when ConfigMap data changes, not on label/chart-version bumps. */}}
{{- define "shopping-app.configChecksum" -}}
{{- toYaml .Values.config | sha256sum -}}
{{- end -}}

{{- define "shopping-app.metadata" -}}
namespace: {{ include "shopping-app.namespace" . }}
labels:
  {{- include "shopping-app.labels" . | nindent 2 }}
{{- end -}}
