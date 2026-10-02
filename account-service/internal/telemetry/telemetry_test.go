package telemetry

import (
	"context"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/sdk/trace/tracetest"
	"go.opentelemetry.io/otel/trace"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHTTPContextSurvivesRejectedRequest(t *testing.T) {
	exporter := tracetest.NewInMemoryExporter()
	provider := sdktrace.NewTracerProvider(sdktrace.WithSyncer(exporter))
	oldProvider, oldPropagator := otel.GetTracerProvider(), otel.GetTextMapPropagator()
	otel.SetTracerProvider(provider)
	otel.SetTextMapPropagator(propagation.TraceContext{})
	defer func() {
		otel.SetTracerProvider(oldProvider)
		otel.SetTextMapPropagator(oldPropagator)
		_ = provider.Shutdown(context.Background())
	}()
	ctx, root := provider.Tracer("test").Start(context.Background(), "request-root")
	var seen trace.SpanContext
	server := httptest.NewServer(HTTPHandler("test-service", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = trace.SpanContextFromContext(r.Context())
		w.WriteHeader(http.StatusForbidden)
	})))
	defer server.Close()
	request, _ := http.NewRequestWithContext(ctx, http.MethodGet, server.URL+"/api/protected?secret=must-not-capture", nil)
	response, err := (&http.Client{Transport: otelhttp.NewTransport(http.DefaultTransport)}).Do(request)
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	root.End()
	if response.StatusCode != http.StatusForbidden || seen.TraceID() != root.SpanContext().TraceID() {
		t.Fatal("HTTP error request lost its trace context")
	}
	spans := exporter.GetSpans()
	var serverParent, clientID trace.SpanID
	for _, s := range spans {
		if s.SpanKind == trace.SpanKindClient {
			clientID = s.SpanContext.SpanID()
		}
		if s.SpanKind == trace.SpanKindServer {
			serverParent = s.Parent.SpanID()
		}
	}
	if !clientID.IsValid() || serverParent != clientID {
		t.Fatal("Server is not a child of the propagated HTTP client span")
	}
}
