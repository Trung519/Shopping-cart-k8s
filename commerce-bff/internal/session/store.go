package session

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

var ErrNotFound = errors.New("session not found")

type User struct {
	ID       string   `json:"id"`
	Username string   `json:"username"`
	Email    string   `json:"email"`
	Name     string   `json:"name"`
	Roles    []string `json:"roles"`
}

type Session struct {
	ID           string    `json:"id"`
	AccessToken  string    `json:"accessToken"`
	RefreshToken string    `json:"refreshToken"`
	IDToken      string    `json:"idToken,omitempty"`
	ExpiresAt    time.Time `json:"expiresAt"`
	User         User      `json:"user"`
}

type Store struct {
	client *redis.Client
	ttl    time.Duration
}

func New(address, password string, db int, ttl time.Duration) *Store {
	return &Store{client: redis.NewClient(&redis.Options{Addr: address, Password: password, DB: db}), ttl: ttl}
}

func (s *Store) Ping(ctx context.Context) error { return s.client.Ping(ctx).Err() }
func (s *Store) Close() error                   { return s.client.Close() }

func (s *Store) Save(ctx context.Context, value Session) error {
	data, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("encode session: %w", err)
	}
	if err := s.client.Set(ctx, "bff:session:"+value.ID, data, s.ttl).Err(); err != nil {
		return fmt.Errorf("save session: %w", err)
	}
	return nil
}

func (s *Store) Get(ctx context.Context, id string) (*Session, error) {
	data, err := s.client.Get(ctx, "bff:session:"+id).Bytes()
	if errors.Is(err, redis.Nil) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("get session: %w", err)
	}
	var value Session
	if err := json.Unmarshal(data, &value); err != nil {
		return nil, fmt.Errorf("decode session: %w", err)
	}
	return &value, nil
}

func (s *Store) Delete(ctx context.Context, id string) error {
	return s.client.Del(ctx, "bff:session:"+id).Err()
}
