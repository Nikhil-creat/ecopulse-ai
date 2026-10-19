{{- define "ecopulse.name" -}}ecopulse{{- end -}}
{{- define "ecopulse.fullname" -}}{{ .Release.Name }}-{{ include "ecopulse.name" . }}{{- end -}}
{{- define "ecopulse.selector" -}}
app.kubernetes.io/name: {{ include "ecopulse.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .name }}
{{- end -}}
