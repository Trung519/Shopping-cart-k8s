{{- define "shopping-observability.collectorConfig" -}}
extensions:
  health_check:
    endpoint: 0.0.0.0:13133
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 192
    spike_limit_mib: 32
  attributes/privacy:
    actions:
      - {key: db.statement, action: delete}
      - {key: db.query.text, action: delete}
      - {key: http.url, action: delete}
      - {key: http.target, action: delete}
      - {key: url.full, action: delete}
      - {key: url.query, action: delete}
  transform/privacy_events:
    error_mode: ignore
    trace_statements:
      - context: span
        statements:
          - set(status.message, "")
      - context: spanevent
        statements:
          - delete_key(attributes, "exception.message")
          - delete_key(attributes, "exception.stacktrace")
  batch:
    timeout: 1s
    send_batch_size: 128
    send_batch_max_size: 256
exporters:
  otlp/tempo:
    endpoint: tempo.shopping-cart-observability.svc.cluster.local:4317
    tls:
      insecure: true
    timeout: 5s
    retry_on_failure:
      enabled: true
      initial_interval: 1s
      max_interval: 10s
      max_elapsed_time: 60s
    sending_queue:
      enabled: true
      num_consumers: 2
      queue_size: 128
service:
  extensions: [health_check]
  telemetry:
    metrics:
      readers:
        - pull:
            exporter:
              prometheus:
                host: 0.0.0.0
                port: 8888
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, attributes/privacy, transform/privacy_events, batch]
      exporters: [otlp/tempo]
{{- end -}}
