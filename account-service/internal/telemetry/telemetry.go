package telemetry

import (
	"context"
	"encoding/json"
	"errors"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel/attribute"
	"log"
	"net/http"
	"os"
	"os/signal"
	"regexp"
	"strings"
	"syscall"
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
	http.DefaultTransport = otelhttp.NewTransport(http.DefaultTransport)
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
	sampler := sdktrace.ParentBased(sdktrace.AlwaysSample())
	if os.Getenv("OTEL_TRACES_SAMPLER") == "always_on" {
		sampler = sdktrace.AlwaysSample()
	}
	provider := sdktrace.NewTracerProvider(
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sampler),
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
		current := trace.SpanFromContext(r.Context())
		route := routeIDs.ReplaceAllString(r.URL.Path, "{id}")
		current.SetName(r.Method + " " + route)
		current.SetAttributes(attribute.String("http.route", route))
		span := current.SpanContext()
		if !span.IsValid() {
			return
		}
		entry, _ := json.Marshal(map[string]any{
			"event": "http_request_completed", "service": os.Getenv("OTEL_SERVICE_NAME"),
			"trace_id": span.TraceID().String(), "span_id": span.SpanID().String(),
			"method": r.Method, "duration_ms": time.Since(started).Milliseconds(),
		})
		log.Print(string(entry))
	})
}

// HTTPHandler instruments every business route, including rejected/error requests.
func HTTPHandler(name string, next http.Handler) http.Handler {
	return otelhttp.NewHandler(RequestLog(next), name, otelhttp.WithFilter(func(r *http.Request) bool {
		return !strings.HasPrefix(r.URL.Path, "/health") && !strings.HasPrefix(r.URL.Path, "/metrics")
	}))
}

// Serve drains active requests before main flushes telemetry on graceful shutdown.
func Serve(server *http.Server) error {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()
	drained := make(chan struct{})
	go func() {
		<-ctx.Done()
		timeout, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		_ = server.Shutdown(timeout)
		close(drained)
	}()
	err := server.ListenAndServe()
	stop()
	<-drained
	if errors.Is(err, http.ErrServerClosed) {
		return nil
	}
	return err
}

var routeIDs = regexp.MustCompile(`[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}`)
