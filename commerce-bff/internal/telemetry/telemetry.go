package telemetry

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/trace"
)

// Init uses OTEL_* configuration. A missing endpoint leaves tracing disabled.
func Init(ctx context.Context) (func(context.Context) error, error) {
	otel.SetTextMapPropagator(propagation.TraceContext{})
	if os.Getenv("OTEL_SDK_DISABLED") == "true" || os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT") == "" {
		return func(context.Context) error { return nil }, nil
	}
	exporter, err := otlptracehttp.New(ctx)
	if err != nil {
		return nil, err
	}
	res, err := resource.New(ctx, resource.WithFromEnv(), resource.WithTelemetrySDK())
	if err != nil {
		return nil, err
	}
	provider := sdktrace.NewTracerProvider(
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.ParentBased(sdktrace.AlwaysSample())),
		sdktrace.WithBatcher(exporter, sdktrace.WithMaxQueueSize(512),
			sdktrace.WithMaxExportBatchSize(128), sdktrace.WithBatchTimeout(time.Second),
			sdktrace.WithExportTimeout(5*time.Second)),
	)
	otel.SetTracerProvider(provider)
	return provider.Shutdown, nil
}

// RequestLog emits correlation IDs without cookies, query strings or user data.
func RequestLog(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()
		next.ServeHTTP(w, r)
		span := trace.SpanContextFromContext(r.Context())
		if !span.IsValid() {
			return
		}
		entry, _ := json.Marshal(map[string]any{
			"event": "http_request_completed", "service": "commerce-bff",
			"trace_id": span.TraceID().String(), "span_id": span.SpanID().String(),
			"method": r.Method, "duration_ms": time.Since(started).Milliseconds(),
		})
		log.Print(string(entry))
	})
}
