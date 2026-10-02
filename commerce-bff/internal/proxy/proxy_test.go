package proxy

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/sdk/trace/tracetest"
	"go.opentelemetry.io/otel/trace"
)

func TestProxyPropagatesChildSpanToUpstream(t *testing.T) {
	exporter := tracetest.NewInMemoryExporter()
	provider := sdktrace.NewTracerProvider(sdktrace.WithSyncer(exporter))
	previousProvider, previousPropagator := otel.GetTracerProvider(), otel.GetTextMapPropagator()
	otel.SetTracerProvider(provider)
	otel.SetTextMapPropagator(propagation.TraceContext{})
	defer func() {
		otel.SetTracerProvider(previousProvider)
		otel.SetTextMapPropagator(previousPropagator)
		provider.Shutdown(context.Background())
	}()
	var received trace.SpanContext
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		received = trace.SpanContextFromContext(otel.GetTextMapPropagator().Extract(r.Context(), propagation.HeaderCarrier(r.Header)))
		if r.URL.Path != "/api/products" {
			t.Errorf("unexpected upstream path %s", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()
	target, err := NewTarget("/api/v2/products", "/api/products", upstream.URL, true, nil)
	if err != nil {
		t.Fatal(err)
	}
	ctx, parent := provider.Tracer("test").Start(context.Background(), "incoming")
	request := httptest.NewRequest(http.MethodGet, "/api/v2/products", nil).WithContext(ctx)
	target.ServeHTTP(httptest.NewRecorder(), request, nil)
	parent.End()
	if !received.IsValid() || received.TraceID() != parent.SpanContext().TraceID() {
		t.Fatal("upstream did not receive the incoming trace ID")
	}
	for _, span := range exporter.GetSpans() {
		if span.SpanKind == trace.SpanKindClient && span.SpanContext.SpanID() == received.SpanID() && span.Parent.SpanID() == parent.SpanContext().SpanID() {
			return
		}
	}
	t.Fatal("upstream header did not point to a child HTTP client span")
}
