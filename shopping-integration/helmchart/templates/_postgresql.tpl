{{- define "integration.postgresqlRepmgr" -}}
{{- $root := .root -}}
{{- $db := .db -}}
{{- $nodes := list -}}
{{- range $i := until (int $db.replicas) -}}
{{- $nodes = append $nodes (printf "%s-%d.%s-headless.%s.svc.cluster.local:%d" $db.name $i $db.name $root.Values.namespaces.data (int $root.Values.postgresql.port)) -}}
{{- end -}}
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {{ $db.name }}
  namespace: {{ $root.Values.namespaces.data }}
  labels:
    app.kubernetes.io/name: postgresql
    app.kubernetes.io/instance: {{ $db.database }}
    app.kubernetes.io/component: database
    {{- include "integration.labels" $root | nindent 4 }}
spec:
  serviceName: {{ $db.name }}-headless
  replicas: {{ $db.replicas }}
  selector:
    matchLabels:
      app.kubernetes.io/name: postgresql
      app.kubernetes.io/instance: {{ $db.database }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: postgresql
        app.kubernetes.io/instance: {{ $db.database }}
        app.kubernetes.io/component: database
        app.kubernetes.io/part-of: shopping-cart
    spec:
      terminationGracePeriodSeconds: 60
      securityContext: {fsGroup: 1001, runAsUser: 1001, runAsNonRoot: true}
      initContainers:
        - name: volume-permissions
          image: "{{ $root.Values.images.busybox.repository }}:{{ $root.Values.images.busybox.tag }}"
          imagePullPolicy: {{ $root.Values.images.busybox.pullPolicy }}
          command: [sh, -c, "mkdir -p /bitnami/postgresql/data && chown -R 1001:1001 /bitnami/postgresql"]
          securityContext: {runAsUser: 0, runAsNonRoot: false}
          volumeMounts: [{name: data, mountPath: /bitnami/postgresql}]
      containers:
        - name: postgresql
          image: "{{ $root.Values.images.postgresqlRepmgr.repository }}:{{ $root.Values.images.postgresqlRepmgr.tag }}"
          imagePullPolicy: {{ $root.Values.images.postgresqlRepmgr.pullPolicy }}
          ports: [{name: postgresql, containerPort: {{ $root.Values.postgresql.port }}, protocol: TCP}]
          env:
            - name: MY_POD_NAME
              valueFrom: {fieldRef: {fieldPath: metadata.name}}
            - name: MY_NAMESPACE
              valueFrom: {fieldRef: {fieldPath: metadata.namespace}}
            - {name: POSTGRESQL_DATABASE, value: {{ $db.database | quote }}}
            - name: POSTGRESQL_PASSWORD
              valueFrom: {secretKeyRef: {name: {{ $db.secretName }}, key: password}}
            - name: REPMGR_PASSWORD
              valueFrom: {secretKeyRef: {name: {{ $db.secretName }}, key: password}}
            - {name: REPMGR_UPGRADE_EXTENSION, value: "yes"}
            - {name: REPMGR_PRIMARY_HOST, value: {{ printf "%s-0.%s-headless.%s.svc.cluster.local" $db.name $db.name $root.Values.namespaces.data | quote }}}
            - {name: REPMGR_PARTNER_NODES, value: {{ join "," $nodes | quote }}}
            - {name: REPMGR_NODE_NAME, value: "$(MY_POD_NAME)"}
            - {name: REPMGR_NODE_NETWORK_NAME, value: {{ printf "$(MY_POD_NAME).%s-headless.$(MY_NAMESPACE).svc.cluster.local" $db.name | quote }}}
            - {name: PGDATA, value: /bitnami/postgresql/data}
          resources:
            {{- toYaml $db.resources | nindent 12 }}
          livenessProbe:
            exec: {command: [/bin/sh, -c, {{ printf "exec pg_isready -U %s -d %s -h 127.0.0.1 -p %d" $root.Values.postgresql.username $db.database (int $root.Values.postgresql.port) | quote }}]}
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            exec: {command: [/bin/sh, -c, {{ printf "exec pg_isready -U %s -d %s -h 127.0.0.1 -p %d" $root.Values.postgresql.username $db.database (int $root.Values.postgresql.port) | quote }}]}
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
          volumeMounts:
            - {name: data, mountPath: /bitnami/postgresql}
            - {name: init-scripts, mountPath: /docker-entrypoint-initdb.d}
      volumes:
        - name: init-scripts
          configMap: {name: {{ $db.name }}-init}
  volumeClaimTemplates:
    - metadata:
        name: data
        labels: {app.kubernetes.io/name: postgresql, app.kubernetes.io/instance: {{ $db.database }}}
      spec:
        accessModes: [ReadWriteOnce]
        resources: {requests: {storage: {{ $db.storage }}}}
{{- end -}}

{{- define "integration.pgpool" -}}
{{- $root := .root -}}
{{- $db := .db -}}
{{- $nodes := list -}}
{{- range $i := until (int $db.replicas) -}}
{{- $nodes = append $nodes (printf "%d:%s-%d.%s-headless.%s.svc.cluster.local:%d" $i $db.name $i $db.name $root.Values.namespaces.data (int $root.Values.postgresql.port)) -}}
{{- end -}}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ $db.name }}-pgpool
  namespace: {{ $root.Values.namespaces.data }}
  labels:
    app.kubernetes.io/name: pgpool
    app.kubernetes.io/instance: {{ $db.database }}
    {{- include "integration.labels" $root | nindent 4 }}
spec:
  replicas: {{ $db.pgpool.replicas }}
  selector:
    matchLabels: {app.kubernetes.io/name: pgpool, app.kubernetes.io/instance: {{ $db.database }}}
  template:
    metadata:
      labels: {app.kubernetes.io/name: pgpool, app.kubernetes.io/instance: {{ $db.database }}, app.kubernetes.io/part-of: shopping-cart}
    spec:
      securityContext: {fsGroup: 1001, runAsUser: 1001, runAsNonRoot: true}
      containers:
        - name: pgpool
          image: "{{ $root.Values.images.pgpool.repository }}:{{ $root.Values.images.pgpool.tag }}"
          imagePullPolicy: {{ $root.Values.images.pgpool.pullPolicy }}
          ports: [{name: postgresql, containerPort: {{ $root.Values.postgresql.port }}, protocol: TCP}]
          env:
            - {name: PGPOOL_BACKEND_NODES, value: {{ join "," $nodes | quote }}}
            - {name: PGPOOL_SR_CHECK_USER, value: {{ $root.Values.postgresql.username | quote }}}
            - name: PGPOOL_SR_CHECK_PASSWORD
              valueFrom: {secretKeyRef: {name: {{ $db.secretName }}, key: password}}
            - {name: PGPOOL_POSTGRES_USERNAME, value: {{ $root.Values.postgresql.username | quote }}}
            - name: PGPOOL_POSTGRES_PASSWORD
              valueFrom: {secretKeyRef: {name: {{ $db.secretName }}, key: password}}
            - {name: PGPOOL_ADMIN_USERNAME, value: admin}
            - name: PGPOOL_ADMIN_PASSWORD
              valueFrom: {secretKeyRef: {name: {{ $db.secretName }}, key: password}}
            - {name: PGPOOL_ENABLE_LDAP, value: "no"}
            - {name: PGPOOL_ENABLE_LOAD_BALANCING, value: {{ $db.pgpool.loadBalancing | quote }}}
          resources:
            {{- toYaml $db.pgpool.resources | nindent 12 }}
          readinessProbe: {tcpSocket: {port: postgresql}, initialDelaySeconds: 10, periodSeconds: 5, timeoutSeconds: 3, failureThreshold: 6}
          livenessProbe: {tcpSocket: {port: postgresql}, initialDelaySeconds: 30, periodSeconds: 10, timeoutSeconds: 5, failureThreshold: 6}
{{- end -}}

