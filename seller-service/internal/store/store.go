package store

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/wilddog64/seller-service/internal/telemetry"
)

var ErrNotFound = errors.New("shop not found")

type Shop struct {
	ID, OwnerUserID, Slug, Name, Description, Status, RejectionReason string
	CreatedAt, UpdatedAt                                              time.Time
}
type Store struct{ pool *pgxpool.Pool }

func New(ctx context.Context, databaseURL string) (*Store, error) {
	config, err := pgxpool.ParseConfig(databaseURL)
	if err != nil {
		return nil, err
	}
	config.ConnConfig.Tracer = telemetry.QueryTracer{}
	pool, err := pgxpool.NewWithConfig(ctx, config)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, err
	}
	store := &Store{pool: pool}
	if err := store.migrate(ctx); err != nil {
		pool.Close()
		return nil, err
	}
	return store, nil
}
func (s *Store) Close()                         { s.pool.Close() }
func (s *Store) Ping(ctx context.Context) error { return s.pool.Ping(ctx) }
func (s *Store) migrate(ctx context.Context) error {
	_, err := s.pool.Exec(ctx, `CREATE TABLE IF NOT EXISTS shops (
id uuid PRIMARY KEY, owner_user_id text NOT NULL, slug text NOT NULL UNIQUE, name text NOT NULL,
description text NOT NULL DEFAULT '', status text NOT NULL CHECK (status IN ('PENDING','APPROVED','REJECTED','SUSPENDED')),
rejection_reason text NOT NULL DEFAULT '', created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS shops_owner_idx ON shops(owner_user_id); CREATE INDEX IF NOT EXISTS shops_status_idx ON shops(status);`)
	return err
}
func (s *Store) CreateApplication(ctx context.Context, ownerID, slug, name, description string) (Shop, error) {
	existing, err := s.GetByOwner(ctx, ownerID)
	if err == nil {
		return existing, fmt.Errorf("seller application already exists")
	}
	if !errors.Is(err, ErrNotFound) {
		return Shop{}, err
	}
	id := uuid.New()
	row := s.pool.QueryRow(ctx, `INSERT INTO shops(id,owner_user_id,slug,name,description,status) VALUES($1,$2,$3,$4,$5,'PENDING') RETURNING id,owner_user_id,slug,name,description,status,rejection_reason,created_at,updated_at`, id, ownerID, slug, name, description)
	return scan(row)
}
func (s *Store) GetByOwner(ctx context.Context, ownerID string) (Shop, error) {
	return scan(s.pool.QueryRow(ctx, `SELECT id,owner_user_id,slug,name,description,status,rejection_reason,created_at,updated_at FROM shops WHERE owner_user_id=$1 ORDER BY created_at DESC LIMIT 1`, ownerID))
}
func (s *Store) GetByID(ctx context.Context, id string) (Shop, error) {
	return scan(s.pool.QueryRow(ctx, `SELECT id,owner_user_id,slug,name,description,status,rejection_reason,created_at,updated_at FROM shops WHERE id=$1`, id))
}
func (s *Store) List(ctx context.Context, status string) ([]Shop, error) {
	query := `SELECT id,owner_user_id,slug,name,description,status,rejection_reason,created_at,updated_at FROM shops`
	args := []any{}
	if status != "" {
		query += ` WHERE status=$1`
		args = append(args, status)
	}
	query += ` ORDER BY created_at DESC`
	rows, err := s.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	shops := []Shop{}
	for rows.Next() {
		shop, err := scan(rows)
		if err != nil {
			return nil, err
		}
		shops = append(shops, shop)
	}
	return shops, rows.Err()
}
func (s *Store) Review(ctx context.Context, id, status, reason string) (Shop, error) {
	row := s.pool.QueryRow(ctx, `UPDATE shops SET status=$2,rejection_reason=$3,updated_at=now() WHERE id=$1 RETURNING id,owner_user_id,slug,name,description,status,rejection_reason,created_at,updated_at`, id, status, reason)
	return scan(row)
}

type scanner interface{ Scan(...any) error }

func scan(row scanner) (Shop, error) {
	var shop Shop
	err := row.Scan(&shop.ID, &shop.OwnerUserID, &shop.Slug, &shop.Name, &shop.Description, &shop.Status, &shop.RejectionReason, &shop.CreatedAt, &shop.UpdatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return Shop{}, ErrNotFound
	}
	return shop, err
}
