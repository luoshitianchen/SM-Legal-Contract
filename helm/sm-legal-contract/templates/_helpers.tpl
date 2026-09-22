{{/*
通用辅助模板：名称/全名/标签选择器
*/}}
{{- define "sm-legal-contract.name" -}}
{{ default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "sm-legal-contract.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end -}}
{{- end }}

{{- define "sm-legal-contract.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "sm-legal-contract.commonLabels" -}}
app.kubernetes.io/name: {{ include "sm-legal-contract.name" . }}
helm.sh/chart: {{ include "sm-legal-contract.chart" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "sm-legal-contract.selectorLabels" -}}
app.kubernetes.io/name: {{ include "sm-legal-contract.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "sm-legal-contract.serviceAccountName" -}}
{{ default (printf "%s-sa" (include "sm-legal-contract.fullname" .)) .Values.serviceAccount.name }}
{{- end }}
