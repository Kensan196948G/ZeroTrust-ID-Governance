{{/*
ZeroTrust ID Governance Helm テンプレートヘルパー
*/}}

{{/*
チャート名の展開
*/}}
{{- define "zerotrust.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
フルネーム（release + chart）
*/}}
{{- define "zerotrust.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
チャートラベル
*/}}
{{- define "zerotrust.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
共通ラベル
*/}}
{{- define "zerotrust.labels" -}}
helm.sh/chart: {{ include "zerotrust.chart" . }}
{{ include "zerotrust.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
セレクターラベル
*/}}
{{- define "zerotrust.selectorLabels" -}}
app.kubernetes.io/name: {{ include "zerotrust.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
バックエンド専用ラベル
*/}}
{{- define "zerotrust.backend.labels" -}}
{{ include "zerotrust.labels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
バックエンド専用セレクターラベル（PDB/NetworkPolicy用）
*/}}
{{- define "zerotrust.backend.selectorLabels" -}}
{{ include "zerotrust.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
フロントエンド専用ラベル
*/}}
{{- define "zerotrust.frontend.labels" -}}
{{ include "zerotrust.labels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
フロントエンド専用セレクターラベル（PDB/NetworkPolicy用）
*/}}
{{- define "zerotrust.frontend.selectorLabels" -}}
{{ include "zerotrust.selectorLabels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Namespace（namespaceOverride 対応・マルチテナント用）
global.namespaceOverride が設定されている場合はそれを使用し、
未設定の場合は helm install --namespace で指定した Release.Namespace を使用する。
*/}}
{{- define "zerotrust.namespace" -}}
{{- default .Release.Namespace .Values.global.namespaceOverride }}
{{- end }}

{{/*
ServiceAccount 名
*/}}
{{- define "zerotrust.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "zerotrust.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
