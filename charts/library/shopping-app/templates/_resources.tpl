{{/*
Standard resources. Each application chart renders them with a one-line template,
e.g. templates/networking/<release>-service.yaml: {{ include "shopping-app.service" . }}
*/}}

{{- define "shopping-app.serviceaccount" -}}
{{- if .Values.serviceAccount.create }}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ .Values.serviceAccount.name }}
  {{- include "shopping-app.metadata" . | nindent 2 }}
{{- if hasKey .Values.serviceAccount "automountToken" }}
automountServiceAccountToken: {{ .Values.serviceAccount.automountToken }}
{{- end }}
{{- end }}
{{- end -}}

{{- define "shopping-app.service" -}}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "shopping-app.name" . }}
  {{- include "shopping-app.metadata" . | nindent 2 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - name: {{ .Values.service.portName }}
      port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
      protocol: TCP
  selector:
    {{- include "shopping-app.selectorLabels" . | nindent 4 }}
{{- end -}}

{{- define "shopping-app.destinationrule" -}}
{{- if .Values.destinationRule.enabled }}
apiVersion: networking.istio.io/v1
kind: DestinationRule
metadata:
  name: {{ include "shopping-app.name" . }}
  {{- include "shopping-app.metadata" . | nindent 2 }}
spec:
  host: {{ .Values.destinationRule.host }}
  trafficPolicy:
    connectionPool:
      {{- toYaml .Values.destinationRule.connectionPool | nindent 6 }}
    outlierDetection:
      {{- toYaml .Values.destinationRule.outlierDetection | nindent 6 }}
{{- end }}
{{- end -}}

{{- define "shopping-app.configmap" -}}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "shopping-app.name" . }}-config
  {{- include "shopping-app.metadata" . | nindent 2 }}
data:
  {{- range $key, $value := .Values.config }}
  {{ $key }}: {{ $value | toString | quote }}
  {{- end }}
{{- end -}}

{{- define "shopping-app.externalsecret" -}}
{{- if .Values.externalSecret.enabled }}
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: {{ include "shopping-app.name" . }}
  {{- include "shopping-app.metadata" . | nindent 2 }}
spec:
  refreshInterval: {{ .Values.externalSecret.refreshInterval }}
  secretStoreRef:
    name: {{ .Values.externalSecret.storeName }}
    kind: {{ .Values.externalSecret.storeKind }}
  target:
    name: {{ .Values.externalSecret.targetName }}
    creationPolicy: Owner
  data:
    {{- toYaml .Values.externalSecret.data | nindent 4 }}
{{- end }}
{{- end -}}
