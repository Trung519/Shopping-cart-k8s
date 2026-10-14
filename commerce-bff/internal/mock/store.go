package mock

import (
	"context"
	"encoding/json"
	"errors"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/wilddog64/commerce-bff/internal/telemetry"
)

// ttl keeps mock data self-cleaning: nothing a mock call writes outlives a day.
const ttl = 24 * time.Hour

// Store is the small key/value surface the mock API needs. State lives in
// Redis so every BFF replica sees the same mock data.
type Store interface {
	Get(ctx context.Context, key string) ([]byte, bool, error)
	Set(ctx context.Context, key string, value []byte, ttl time.Duration) error
	SetNX(ctx context.Context, key string, value []byte, ttl time.Duration) (bool, error)
	Del(ctx context.Context, key string) error
}

func getJSON(ctx context.Context, s Store, key string, out any) (bool, error) {
	data, found, err := s.Get(ctx, key)
	if err != nil || !found {
		return false, err
	}
	return true, json.Unmarshal(data, out)
}

func setJSON(ctx context.Context, s Store, key string, value any) error {
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return s.Set(ctx, key, data, ttl)
}

// RedisStore keeps mock state under the "bff:mock:" prefix, apart from sessions.
type RedisStore struct{ client *redis.Client }

func NewRedisStore(address, password string, db int) *RedisStore {
	client := redis.NewClient(&redis.Options{Addr: address, Password: password, DB: db})
	client.AddHook(telemetry.RedisHook{})
	return &RedisStore{client: client}
}

func (s *RedisStore) Close() error { return s.client.Close() }

func (s *RedisStore) Get(ctx context.Context, key string) ([]byte, bool, error) {
	data, err := s.client.Get(ctx, "bff:mock:"+key).Bytes()
	if errors.Is(err, redis.Nil) {
		return nil, false, nil
	}
	return data, err == nil, err
}

func (s *RedisStore) Set(ctx context.Context, key string, value []byte, ttl time.Duration) error {
	return s.client.Set(ctx, "bff:mock:"+key, value, ttl).Err()
}

func (s *RedisStore) SetNX(ctx context.Context, key string, value []byte, ttl time.Duration) (bool, error) {
	return s.client.SetNX(ctx, "bff:mock:"+key, value, ttl).Result()
}

func (s *RedisStore) Del(ctx context.Context, key string) error {
	return s.client.Del(ctx, "bff:mock:"+key).Err()
}

// MemoryStore is used by tests and by local runs without Redis.
type MemoryStore struct {
	mu   sync.Mutex
	data map[string][]byte
}

func NewMemoryStore() *MemoryStore { return &MemoryStore{data: map[string][]byte{}} }

func (s *MemoryStore) Get(_ context.Context, key string) ([]byte, bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	value, ok := s.data[key]
	return append([]byte(nil), value...), ok, nil
}

func (s *MemoryStore) Set(_ context.Context, key string, value []byte, _ time.Duration) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.data[key] = append([]byte(nil), value...)
	return nil
}

func (s *MemoryStore) SetNX(_ context.Context, key string, value []byte, _ time.Duration) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.data[key]; exists {
		return false, nil
	}
	s.data[key] = append([]byte(nil), value...)
	return true, nil
}

func (s *MemoryStore) Del(_ context.Context, key string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.data, key)
	return nil
}
