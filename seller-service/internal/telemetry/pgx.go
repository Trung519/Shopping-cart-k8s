package telemetry

import (
	"context"
	"github.com/jackc/pgx/v5"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
	"strings"
)

// QueryTracer records only SQL operation names; never query text or arguments.
type QueryTracer struct{}

func (QueryTracer) TraceQueryStart(ctx context.Context, _ *pgx.Conn, data pgx.TraceQueryStartData) context.Context {
	operation := "query"
	if fields := strings.Fields(data.SQL); len(fields) > 0 {
		switch strings.ToUpper(fields[0]) {
		case "SELECT", "INSERT", "UPDATE", "DELETE", "CREATE":
			operation = strings.ToUpper(fields[0])
		}
	}
	ctx, _ = otel.Tracer("shopping/pgx").Start(ctx, "postgresql "+operation, trace.WithSpanKind(trace.SpanKindClient), trace.WithAttributes(attribute.String("db.system", "postgresql"), attribute.String("db.operation", operation)))
	return ctx
}
func (QueryTracer) TraceQueryEnd(ctx context.Context, _ *pgx.Conn, data pgx.TraceQueryEndData) {
	span := trace.SpanFromContext(ctx)
	if data.Err != nil {
		span.SetStatus(codes.Error, "PostgreSQL request failed")
	}
	span.End()
}
