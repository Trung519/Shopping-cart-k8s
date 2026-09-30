package repository

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strings"

	"github.com/redis/go-redis/v9"
	"github.com/user/shopping-cart-basket/internal/auth"
	"github.com/user/shopping-cart-basket/internal/model"
)

var (
	// ErrLocalUserNotFound is returned when a local user cannot be found.
	ErrLocalUserNotFound = errors.New("local user not found")
)

// LocalUserRepository manages local auth users.
type LocalUserRepository interface {
	Bootstrap(ctx context.Context, users []model.LocalUser) error
	List(ctx context.Context) ([]model.LocalUser, error)
	GetByUsername(ctx context.Context, username string) (*model.LocalUser, error)
	GetByID(ctx context.Context, id string) (*model.LocalUser, error)
	Save(ctx context.Context, user model.LocalUser) error
	DeleteByUsername(ctx context.Context, username string) error
}

// RedisLocalUserRepository stores local auth users in Redis.
type RedisLocalUserRepository struct {
	client *redis.Client
}

// NewRedisLocalUserRepository creates a Redis-backed local user repository.
func NewRedisLocalUserRepository(client *redis.Client) *RedisLocalUserRepository {
	return &RedisLocalUserRepository{client: client}
}

func (r *RedisLocalUserRepository) userKey(username string) string {
	return fmt.Sprintf("auth:user:%s", normalizeUsername(username))
}

// Bootstrap seeds missing default users without overwriting existing ones.
func (r *RedisLocalUserRepository) Bootstrap(ctx context.Context, users []model.LocalUser) error {
	for _, user := range users {
		exists, err := r.client.Exists(ctx, r.userKey(user.Username)).Result()
		if err != nil {
			return fmt.Errorf("failed to check local user bootstrap state: %w", err)
		}
		if exists > 0 {
			continue
		}
		if err := r.Save(ctx, user); err != nil {
			return err
		}
	}
	return nil
}

// List returns all local users sorted by username.
func (r *RedisLocalUserRepository) List(ctx context.Context) ([]model.LocalUser, error) {
	iter := r.client.Scan(ctx, 0, "auth:user:*", 0).Iterator()
	users := make([]model.LocalUser, 0)

	for iter.Next(ctx) {
		data, err := r.client.Get(ctx, iter.Val()).Bytes()
		if err != nil {
			return nil, fmt.Errorf("failed to read local user: %w", err)
		}

		var user model.LocalUser
		if err := json.Unmarshal(data, &user); err != nil {
			return nil, fmt.Errorf("failed to decode local user: %w", err)
		}

		users = append(users, user)
	}

	if err := iter.Err(); err != nil {
		return nil, fmt.Errorf("failed to iterate local users: %w", err)
	}

	sort.Slice(users, func(i, j int) bool {
		return users[i].Username < users[j].Username
	})

	return users, nil
}

// GetByUsername returns a local user by username.
func (r *RedisLocalUserRepository) GetByUsername(ctx context.Context, username string) (*model.LocalUser, error) {
	data, err := r.client.Get(ctx, r.userKey(username)).Bytes()
	if err != nil {
		if errors.Is(err, redis.Nil) {
			return nil, ErrLocalUserNotFound
		}
		return nil, fmt.Errorf("failed to get local user: %w", err)
	}

	var user model.LocalUser
	if err := json.Unmarshal(data, &user); err != nil {
		return nil, fmt.Errorf("failed to decode local user: %w", err)
	}

	return &user, nil
}

// GetByID returns a local user by ID.
func (r *RedisLocalUserRepository) GetByID(ctx context.Context, id string) (*model.LocalUser, error) {
	users, err := r.List(ctx)
	if err != nil {
		return nil, err
	}

	for _, user := range users {
		if user.ID == id {
			copy := user
			return &copy, nil
		}
	}

	return nil, ErrLocalUserNotFound
}

// Save creates or replaces a local user entry.
func (r *RedisLocalUserRepository) Save(ctx context.Context, user model.LocalUser) error {
	user.Username = normalizeUsername(user.Username)
	if user.Password != "" {
		passwordHash, err := auth.HashPassword(user.Password)
		if err != nil {
			return fmt.Errorf("failed to hash local user password: %w", err)
		}
		user.PasswordHash = passwordHash
		user.Password = ""
	}
	if user.PasswordHash == "" {
		return errors.New("local user password hash is required")
	}

	data, err := json.Marshal(user)
	if err != nil {
		return fmt.Errorf("failed to encode local user: %w", err)
	}

	if err := r.client.Set(ctx, r.userKey(user.Username), data, 0).Err(); err != nil {
		return fmt.Errorf("failed to save local user: %w", err)
	}

	return nil
}

// DeleteByUsername deletes a local user by username.
func (r *RedisLocalUserRepository) DeleteByUsername(ctx context.Context, username string) error {
	result, err := r.client.Del(ctx, r.userKey(username)).Result()
	if err != nil {
		return fmt.Errorf("failed to delete local user: %w", err)
	}
	if result == 0 {
		return ErrLocalUserNotFound
	}
	return nil
}

func normalizeUsername(username string) string {
	return strings.ToLower(strings.TrimSpace(username))
}
