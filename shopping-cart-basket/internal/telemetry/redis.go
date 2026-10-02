package telemetry

import (
	"context"
	"github.com/redis/go-redis/v9"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
)

// RedisHook records commands without keys, values, credentials or statements.
type RedisHook struct{}

func (RedisHook) DialHook(next redis.DialHook) redis.DialHook { return next }
func (RedisHook) ProcessHook(next redis.ProcessHook) redis.ProcessHook {
	return func(ctx context.Context, cmd redis.Cmder) error {
		ctx, span := otel.Tracer("shopping/redis").Start(ctx, "redis "+cmd.Name(), trace.WithSpanKind(trace.SpanKindClient), trace.WithAttributes(attribute.String("db.system", "redis"), attribute.String("db.operation", cmd.Name())))
		defer span.End()
		err := next(ctx, cmd)
		if err != nil && err != redis.Nil {
			span.SetStatus(codes.Error, "Redis request failed")
		}
		return err
	}
}
func (RedisHook) ProcessPipelineHook(next redis.ProcessPipelineHook) redis.ProcessPipelineHook {
	return func(ctx context.Context, cmds []redis.Cmder) error {
		ctx, span := otel.Tracer("shopping/redis").Start(ctx, "redis pipeline", trace.WithSpanKind(trace.SpanKindClient), trace.WithAttributes(attribute.String("db.system", "redis"), attribute.Int("db.batch.size", len(cmds))))
		defer span.End()
		err := next(ctx, cmds)
		if err != nil && err != redis.Nil {
			span.SetStatus(codes.Error, "Redis pipeline failed")
		}
		return err
	}
}
