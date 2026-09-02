{{/*
Wrapper chart name and labels (used for wrapper-owned resources).
*/}}
{{- define "nebari-unity-catalog.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "nebari-unity-catalog.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "nebari-unity-catalog.labels" -}}
helm.sh/chart: {{ include "nebari-unity-catalog.chart" . }}
app.kubernetes.io/name: {{ include "nebari-unity-catalog.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: unity-catalog
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Fullname the upstream subchart will use. Mirrors unitycatalog.fullname so the
wrapper can reference subchart Services and Secrets by name.
*/}}
{{- define "nebari-unity-catalog.ucFullname" -}}
{{- if .Values.unitycatalog.fullnameOverride }}
{{- .Values.unitycatalog.fullnameOverride | trunc 56 | trimSuffix "-" }}
{{- else if contains "unitycatalog" .Release.Name }}
{{- .Release.Name | trunc 56 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-unitycatalog" .Release.Name | trunc 56 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "nebari-unity-catalog.uiServiceName" -}}
{{- .Values.nebariapp.service.name | default (printf "%s-ui" (include "nebari-unity-catalog.ucFullname" .)) }}
{{- end }}

{{- define "nebari-unity-catalog.serverUrl" -}}
{{- .Values.sync.serverUrl | default (printf "http://%s-server:8080" (include "nebari-unity-catalog.ucFullname" .)) }}
{{- end }}

{{- define "nebari-unity-catalog.jwtSecretName" -}}
{{- .Values.sync.jwtKeypairSecretName | default .Values.unitycatalog.server.jwtKeypairSecret.name | default (printf "%s-server-jwt-key" (include "nebari-unity-catalog.ucFullname" .)) }}
{{- end }}
