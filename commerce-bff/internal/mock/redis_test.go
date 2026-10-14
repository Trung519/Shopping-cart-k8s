package mock

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"testing"
	"time"
)

// Runs only when REDIS_TEST_ADDR is set, e.g.
//
//	docker run -d --rm -p 16379:6379 redis:7-alpine
//	REDIS_TEST_ADDR=localhost:16379 go test ./internal/mock -run Redis
func mustJSON(v any) []byte {
	data, _ := json.Marshal(v)
	return data
}

func redisStore(t *testing.T) *RedisStore {
	t.Helper()
	addr := os.Getenv("REDIS_TEST_ADDR")
	if addr == "" {
		t.Skip("REDIS_TEST_ADDR not set")
	}
	store := NewRedisStore(addr, "", 15)
	t.Cleanup(func() { _ = store.Close() })
	return store
}

func TestRedisStoreContract(t *testing.T) {
	store := redisStore(t)
	ctx := context.Background()
	key := "contract:" + time.Now().Format("150405.000000")
	defer store.Del(ctx, key)

	if _, found, err := store.Get(ctx, key); err != nil || found {
		t.Fatalf("missing key: found=%v err=%v", found, err)
	}
	if first, err := store.SetNX(ctx, key, []byte("a"), time.Minute); err != nil || !first {
		t.Fatalf("first SetNX should win: %v %v", first, err)
	}
	if second, _ := store.SetNX(ctx, key, []byte("b"), time.Minute); second {
		t.Fatalf("second SetNX must lose")
	}
	if value, found, _ := store.Get(ctx, key); !found || string(value) != "a" {
		t.Fatalf("value = %q", value)
	}
	if err := store.Set(ctx, key, []byte("c"), time.Minute); err != nil {
		t.Fatal(err)
	}
	if value, _, _ := store.Get(ctx, key); string(value) != "c" {
		t.Fatalf("Set should overwrite: %q", value)
	}
	_ = store.Del(ctx, key)
	if _, found, _ := store.Get(ctx, key); found {
		t.Fatalf("Del should remove the key")
	}
}

// TestRedisBackedJourney walks the buyer journey against real Redis, with two
// Handler instances sharing it, to prove state really is shared across replicas.
func TestRedisBackedJourney(t *testing.T) {
	store := redisStore(t)
	user := "redis-" + time.Now().Format("150405.000000")
	auth := func(w http.ResponseWriter, r *http.Request) (Identity, bool) {
		return Identity{ID: user, Name: "Redis Tester"}, true
	}
	replicaA := New(Config{PaymentDelay: 300 * time.Millisecond, ShipmentStep: 200 * time.Millisecond}, store, auth)
	replicaB := New(Config{PaymentDelay: 300 * time.Millisecond, ShipmentStep: 200 * time.Millisecond}, store, auth)
	a := &env{t: t, h: replicaA, clock: &fakeClock{}}
	b := &env{t: t, h: replicaB, clock: &fakeClock{}}

	created := a.expect(a.do("POST", "/payments", user, "", `{"orderId":"redis-ord","method":"momo","amount":5000}`), 202).obj(t)
	id := created["id"].(string)
	if got := b.expect(b.do("GET", "/payments/"+id, user, "", ""), 200).obj(t); got["status"] != "PENDING" {
		t.Fatalf("replica B should see the payment created on A: %v", got)
	}
	time.Sleep(400 * time.Millisecond)
	if got := b.expect(b.do("GET", "/payments/"+id, user, "", ""), 200).obj(t); got["status"] != "SUCCESS" {
		t.Fatalf("payment should have succeeded after the delay: %v", got)
	}
	if ship := a.expect(a.do("GET", "/shipments/redis-ord", user, "", ""), 200).obj(t); ship["status"] == "WAITING_PAYMENT" {
		t.Fatalf("shipment should follow the paid order: %v", ship)
	}

	body := `{"fullName":"A","phone":"0912345678","province":"HCM","district":"Q1","ward":"BN","street":"1 Lê Lợi"}`
	a.expect(a.do("POST", "/addresses", user, "", body), 201)
	if list := b.expect(b.do("GET", "/addresses", user, "", ""), 200).list(t); len(list) != 1 {
		t.Fatalf("address written on A must be readable on B")
	}
	a.expect(a.do("POST", "/seller/payouts", user, "", `{"amount":1000000}`), 202)
	fin := b.expect(b.do("GET", "/seller/finance", user, "", ""), 200).obj(t)
	if !strings.Contains(string(mustJSON(fin["payouts"])), "PROCESSING") && !strings.Contains(string(mustJSON(fin["payouts"])), "COMPLETED") {
		t.Fatalf("payout should be visible from the other replica: %v", fin["payouts"])
	}
}
