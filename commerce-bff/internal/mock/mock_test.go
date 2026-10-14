package mock

import (
	"bufio"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/sdk/trace/tracetest"
)

type fakeClock struct {
	mu sync.Mutex
	t  time.Time
}

func (c *fakeClock) Now() time.Time {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.t
}

func (c *fakeClock) Advance(d time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.t = c.t.Add(d)
}

type env struct {
	t     *testing.T
	h     *Handler
	clock *fakeClock
}

type reply struct {
	Code    int
	Header  http.Header
	Success bool
	Mock    bool
	Message string
	Data    json.RawMessage
}

func (r reply) obj(t *testing.T) map[string]any {
	t.Helper()
	var out map[string]any
	if err := json.Unmarshal(r.Data, &out); err != nil {
		t.Fatalf("data is not an object: %s", r.Data)
	}
	return out
}

func (r reply) list(t *testing.T) []map[string]any {
	t.Helper()
	var out []map[string]any
	if err := json.Unmarshal(r.Data, &out); err != nil {
		t.Fatalf("data is not a list: %s", r.Data)
	}
	return out
}

func newEnv(t *testing.T, mutate ...func(*Config)) *env {
	t.Helper()
	clock := &fakeClock{t: time.Date(2026, 10, 14, 9, 0, 0, 0, time.UTC)}
	cfg := Config{PaymentDelay: 5 * time.Second, ShipmentStep: 10 * time.Second, Now: clock.Now}
	for _, m := range mutate {
		m(&cfg)
	}
	auth := func(w http.ResponseWriter, r *http.Request) (Identity, bool) {
		user := r.Header.Get("X-User")
		if user == "" {
			writeFail(w, http.StatusUnauthorized, "Vui lòng đăng nhập")
			return Identity{}, false
		}
		var roles []string
		if raw := r.Header.Get("X-Roles"); raw != "" {
			roles = strings.Split(raw, ",")
		}
		return Identity{ID: user, Name: "Tên " + user, Roles: roles}, true
	}
	return &env{t: t, h: New(cfg, NewMemoryStore(), auth), clock: clock}
}

func (e *env) do(method, path, user, roles, body string) reply {
	e.t.Helper()
	req := httptest.NewRequest(method, "http://bff"+prefix+path, strings.NewReader(body))
	if user != "" {
		req.Header.Set("X-User", user)
	}
	if roles != "" {
		req.Header.Set("X-Roles", roles)
	}
	rec := httptest.NewRecorder()
	e.h.ServeHTTP(rec, req)
	out := reply{Code: rec.Code, Header: rec.Header()}
	var envelope struct {
		Success bool            `json:"success"`
		Mock    bool            `json:"mock"`
		Message string          `json:"message"`
		Data    json.RawMessage `json:"data"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &envelope); err != nil {
		e.t.Fatalf("%s %s: body is not JSON: %q", method, path, rec.Body.String())
	}
	out.Success, out.Mock, out.Message, out.Data = envelope.Success, envelope.Mock, envelope.Message, envelope.Data
	return out
}

func (e *env) expect(r reply, code int) reply {
	e.t.Helper()
	if r.Code != code {
		e.t.Fatalf("status = %d, want %d (message %q, data %s)", r.Code, code, r.Message, r.Data)
	}
	if !r.Mock {
		e.t.Fatalf("response is missing mock=true")
	}
	if r.Header.Get("X-Mock") != "true" {
		e.t.Fatalf("response is missing X-Mock header")
	}
	return r
}

const admin = "platform-admin"

func TestFixturesParse(t *testing.T) {
	fx := loadFixtures()
	if len(fx.Vouchers) == 0 || len(fx.Reviews) < 4 || len(fx.SellerOrders) == 0 || len(fx.Threads) == 0 || len(fx.Settlements) == 0 {
		t.Fatalf("fixtures look empty: %+v", fx)
	}
}

func TestEveryRouteIsMarkedMockAndNeedsLogin(t *testing.T) {
	e := newEnv(t)
	cfg := e.expect(e.do("GET", "/config", "", "", ""), 200)
	if cfg.obj(t)["enabled"] != true {
		t.Fatalf("config should report enabled")
	}
	for _, path := range []string{"/payments/x", "/shipments/o1", "/addresses", "/vouchers", "/products/p1/reviews", "/returns", "/notifications", "/seller/dashboard", "/seller/orders", "/seller/finance", "/admin/audit", "/events"} {
		r := e.do("GET", path, "", "", "")
		if r.Code != http.StatusUnauthorized {
			t.Errorf("GET %s without login = %d, want 401", path, r.Code)
		}
		if r.Header.Get("X-Mock") != "true" {
			t.Errorf("GET %s: missing X-Mock header", path)
		}
	}
}

func TestPaymentQRLifecycle(t *testing.T) {
	e := newEnv(t)
	created := e.expect(e.do("POST", "/payments", "u1", "", `{"orderId":"ord-1","method":"momo","amount":1290000}`), 202).obj(t)
	id := created["id"].(string)
	if created["status"] != "PENDING" || created["remainingSeconds"].(float64) != 5 {
		t.Fatalf("new payment should be PENDING with 5s left: %v", created)
	}
	qr := created["qr"].(map[string]any)
	if rows := qr["matrix"].([]any); len(rows) != 25 || len(rows[0].(string)) != 25 {
		t.Fatalf("qr matrix should be 25x25")
	}
	if !strings.HasPrefix(qr["payload"].(string), "MOCK|MOMO|") {
		t.Fatalf("qr payload must be clearly fake: %v", qr["payload"])
	}

	e.clock.Advance(2 * time.Second)
	mid := e.expect(e.do("GET", "/payments/"+id, "u1", "", ""), 200).obj(t)
	if mid["status"] != "PENDING" || mid["remainingSeconds"].(float64) != 3 {
		t.Fatalf("after 2s expected PENDING/3s left: %v", mid)
	}
	e.clock.Advance(3 * time.Second)
	done := e.expect(e.do("GET", "/payments/"+id, "u1", "", ""), 200).obj(t)
	if done["status"] != "SUCCESS" || done["paidAt"] == nil {
		t.Fatalf("after 5s expected SUCCESS with paidAt: %v", done)
	}
	e.expect(e.do("GET", "/payments/"+id, "someone-else", "", ""), 404)
	e.expect(e.do("POST", "/payments/"+id+"/cancel", "u1", "", ""), 409)
}

func TestPaymentVariants(t *testing.T) {
	e := newEnv(t)
	cod := e.expect(e.do("POST", "/payments", "u1", "", `{"orderId":"ord-2","method":"cod","amount":50000}`), 201).obj(t)
	if cod["status"] != "SUCCESS" || cod["qr"] != nil {
		t.Fatalf("COD should succeed immediately without QR: %v", cod)
	}
	failed := e.expect(e.do("POST", "/payments?outcome=fail", "u1", "", `{"orderId":"ord-3","method":"vnpay","amount":50000}`), 202).obj(t)
	e.clock.Advance(5 * time.Second)
	if got := e.expect(e.do("GET", "/payments/"+failed["id"].(string), "u1", "", ""), 200).obj(t); got["status"] != "FAILED" {
		t.Fatalf("outcome=fail should end FAILED: %v", got)
	}
	fast := e.expect(e.do("POST", "/payments?payDelay=1", "u1", "", `{"orderId":"ord-4","method":"zalopay","amount":1000}`), 202).obj(t)
	if fast["expiresInSeconds"].(float64) != 1 {
		t.Fatalf("payDelay=1 should shorten the wait: %v", fast)
	}
	cancelled := e.expect(e.do("POST", "/payments", "u1", "", `{"orderId":"ord-5","method":"momo","amount":1000}`), 202).obj(t)
	if got := e.expect(e.do("POST", "/payments/"+cancelled["id"].(string)+"/cancel", "u1", "", ""), 200).obj(t); got["status"] != "CANCELLED" {
		t.Fatalf("cancel should end CANCELLED: %v", got)
	}
	for _, body := range []string{`{"orderId":"o","method":"bitcoin","amount":1}`, `{"orderId":"o","method":"momo","amount":0}`, `{"orderId":"","method":"momo","amount":5}`, `not json`} {
		if r := e.do("POST", "/payments", "u1", "", body); r.Code != 422 && r.Code != 400 {
			t.Errorf("body %q = %d, want 4xx", body, r.Code)
		}
	}
}

func TestPaymentCallbackSpanLinksToOriginTrace(t *testing.T) {
	recorder := tracetest.NewSpanRecorder()
	provider := sdktrace.NewTracerProvider(sdktrace.WithSpanProcessor(recorder))
	previous := otel.GetTracerProvider()
	otel.SetTracerProvider(provider)
	otel.SetTextMapPropagator(propagation.TraceContext{})
	defer otel.SetTracerProvider(previous)

	e := newEnv(t)
	tracer := provider.Tracer("test")
	originCtx, origin := tracer.Start(context.Background(), "create")
	req := httptest.NewRequest("POST", "http://bff"+prefix+"/payments", strings.NewReader(`{"orderId":"ord-t","method":"momo","amount":1000}`)).WithContext(originCtx)
	req.Header.Set("X-User", "u1")
	rec := httptest.NewRecorder()
	e.h.ServeHTTP(rec, req)
	origin.End()
	var created struct{ Data map[string]any }
	_ = json.Unmarshal(rec.Body.Bytes(), &created)
	id := created.Data["id"].(string)

	e.clock.Advance(6 * time.Second)
	for i := 0; i < 3; i++ { // polling repeatedly must emit the callback only once
		e.expect(e.do("GET", "/payments/"+id, "u1", "", ""), 200)
	}
	callbacks := 0
	for _, span := range recorder.Ended() {
		if span.Name() != "mock.payment.callback" {
			continue
		}
		callbacks++
		if len(span.Links()) != 1 || span.Links()[0].SpanContext.SpanID() != origin.SpanContext().SpanID() {
			t.Fatalf("callback span must link back to the creating span")
		}
	}
	if callbacks != 1 {
		t.Fatalf("callback spans = %d, want exactly 1", callbacks)
	}
}

func TestSpansAreTaggedMock(t *testing.T) {
	recorder := tracetest.NewSpanRecorder()
	provider := sdktrace.NewTracerProvider(sdktrace.WithSpanProcessor(recorder))
	e := newEnv(t)
	ctx, span := provider.Tracer("test").Start(context.Background(), "server")
	req := httptest.NewRequest("GET", "http://bff"+prefix+"/vouchers", nil).WithContext(ctx)
	req.Header.Set("X-User", "u1")
	e.h.ServeHTTP(httptest.NewRecorder(), req)
	span.End()
	attrs := map[string]string{}
	for _, kv := range recorder.Ended()[0].Attributes() {
		attrs[string(kv.Key)] = kv.Value.Emit()
	}
	if attrs["mock"] != "true" || attrs["mock.scenario"] != "vouchers" {
		t.Fatalf("span attributes = %v", attrs)
	}
}

func TestShipmentTimeline(t *testing.T) {
	e := newEnv(t)
	pay := e.expect(e.do("POST", "/payments", "u1", "", `{"orderId":"ord-s","method":"momo","amount":9000}`), 202).obj(t)
	waiting := e.expect(e.do("GET", "/shipments/ord-s", "u1", "", ""), 200).obj(t)
	if waiting["status"] != "WAITING_PAYMENT" {
		t.Fatalf("unpaid order should wait for payment: %v", waiting)
	}
	e.clock.Advance(5 * time.Second) // payment succeeds exactly now
	atPaid := e.expect(e.do("GET", "/shipments/ord-s", "u1", "", ""), 200).obj(t)
	if atPaid["status"] != "PLACED" {
		t.Fatalf("timeline should start at PLACED once paid: %v", atPaid)
	}
	e.clock.Advance(25 * time.Second)
	mid := e.expect(e.do("GET", "/shipments/ord-s", "u1", "", ""), 200).obj(t)
	if mid["status"] != "PACKING" { // steps land at 0s, 10s, 20s, 30s...
		t.Fatalf("25s after payment should be PACKING: %v", mid["status"])
	}
	e.clock.Advance(6 * time.Second)
	if next := e.expect(e.do("GET", "/shipments/ord-s", "u1", "", ""), 200).obj(t); next["status"] != "HANDED_OVER" {
		t.Fatalf("31s after payment should be HANDED_OVER: %v", next["status"])
	}
	e.clock.Advance(time.Minute)
	last := e.expect(e.do("GET", "/shipments/ord-s", "u1", "", ""), 200).obj(t)
	if last["status"] != "DELIVERED" || last["trackingCode"] == "" || last["carrier"] == "" {
		t.Fatalf("expected DELIVERED with tracking info: %v", last)
	}
	_ = pay

	// An order that never used a mock payment starts when first viewed.
	first := e.expect(e.do("GET", "/shipments/ord-real", "u1", "", ""), 200).obj(t)
	if first["status"] != "PLACED" {
		t.Fatalf("first view should be PLACED: %v", first["status"])
	}
	e.clock.Advance(10 * time.Second)
	if next := e.expect(e.do("GET", "/shipments/ord-real", "u1", "", ""), 200).obj(t); next["status"] != "CONFIRMED" {
		t.Fatalf("10s later should be CONFIRMED: %v", next["status"])
	}

	failed := e.expect(e.do("POST", "/payments?outcome=fail", "u1", "", `{"orderId":"ord-f","method":"momo","amount":9000}`), 202).obj(t)
	_ = failed
	e.clock.Advance(6 * time.Second)
	if got := e.expect(e.do("GET", "/shipments/ord-f", "u1", "", ""), 200).obj(t); got["status"] != "PAYMENT_FAILED" {
		t.Fatalf("failed payment should block shipping: %v", got["status"])
	}
}

func TestAddressBook(t *testing.T) {
	e := newEnv(t)
	body := `{"fullName":"Nguyễn Văn A","phone":"0912 345 678","province":"TP. Hồ Chí Minh","district":"Quận 1","ward":"Bến Nghé","street":"1 Lê Lợi"}`
	first := e.expect(e.do("POST", "/addresses", "u1", "", body), 201).obj(t)
	if first["isDefault"] != true {
		t.Fatalf("first address becomes default")
	}
	second := e.expect(e.do("POST", "/addresses", "u1", "", strings.Replace(body, "1 Lê Lợi", "2 Nguyễn Huệ", 1)), 201).obj(t)
	if second["isDefault"] != false {
		t.Fatalf("second address is not default")
	}
	list := e.expect(e.do("POST", "/addresses/"+second["id"].(string)+"/default", "u1", "", ""), 200).list(t)
	if list[0]["isDefault"] != false || list[1]["isDefault"] != true {
		t.Fatalf("default should move to the second address: %v", list)
	}
	e.expect(e.do("PUT", "/addresses/"+first["id"].(string), "u1", "", strings.Replace(body, "Quận 1", "Quận 3", 1)), 200)
	remaining := e.expect(e.do("DELETE", "/addresses/"+second["id"].(string), "u1", "", ""), 200).list(t)
	if len(remaining) != 1 || remaining[0]["isDefault"] != true {
		t.Fatalf("deleting the default must promote another: %v", remaining)
	}
	if other := e.expect(e.do("GET", "/addresses", "u2", "", ""), 200).list(t); len(other) != 0 {
		t.Fatalf("addresses must be per user")
	}
	e.expect(e.do("POST", "/addresses", "u1", "", strings.Replace(body, "0912 345 678", "abc", 1)), 422)
	e.expect(e.do("POST", "/addresses", "u1", "", strings.Replace(body, "Nguyễn Văn A", "", 1)), 422)
	e.expect(e.do("DELETE", "/addresses/nope", "u1", "", ""), 404)
}

func TestVouchers(t *testing.T) {
	e := newEnv(t)
	sale := e.expect(e.do("POST", "/vouchers/apply", "u1", "", `{"code":" sale50 ","subtotal":400000}`), 200).obj(t)
	if sale["discount"].(float64) != 50000 {
		t.Fatalf("SALE50 should take 50k off: %v", sale)
	}
	pct := e.expect(e.do("POST", "/vouchers/apply", "u1", "", `{"code":"GIAM10","subtotal":5000000}`), 200).obj(t)
	if pct["discount"].(float64) != 100000 {
		t.Fatalf("GIAM10 is capped at 100k: %v", pct)
	}
	ship := e.expect(e.do("POST", "/vouchers/apply", "u1", "", `{"code":"FREESHIP","subtotal":10}`), 200).obj(t)
	if ship["shippingDiscount"].(float64) != 30000 {
		t.Fatalf("FREESHIP should discount shipping: %v", ship)
	}
	if r := e.expect(e.do("POST", "/vouchers/apply", "u1", "", `{"code":"SALE50","subtotal":100000}`), 422); !strings.Contains(r.Message, "tối thiểu") {
		t.Fatalf("below minimum should explain why: %q", r.Message)
	}
	if r := e.expect(e.do("POST", "/vouchers/apply", "u1", "", `{"code":"HETHAN","subtotal":999999}`), 422); !strings.Contains(r.Message, "hết hạn") {
		t.Fatalf("expired voucher should say so: %q", r.Message)
	}
	e.expect(e.do("POST", "/vouchers/apply", "u1", "", `{"code":"NOPE","subtotal":1}`), 422)
	list := e.expect(e.do("GET", "/vouchers?subtotal=250000", "u1", "", ""), 200).list(t)
	eligible := map[string]bool{}
	for _, v := range list {
		eligible[v["code"].(string)] = v["eligible"].(bool)
	}
	if !eligible["GIAM10"] || eligible["SALE50"] || eligible["HETHAN"] || !eligible["FREESHIP"] {
		t.Fatalf("eligibility at 250k wrong: %v", eligible)
	}
	e.expect(e.do("GET", "/vouchers?subtotal=abc", "u1", "", ""), 400)
}

func TestReviewsAndExtras(t *testing.T) {
	e := newEnv(t)
	before := e.expect(e.do("GET", "/products/p-1/reviews", "u1", "", ""), 200).obj(t)
	count := before["summary"].(map[string]any)["count"].(float64)
	if count < 4 || count > 8 {
		t.Fatalf("seed review count out of range: %v", count)
	}
	e.expect(e.do("POST", "/products/p-1/reviews", "u1", "", `{"rating":5,"comment":"Dùng rất tốt, đáng tiền"}`), 201)
	after := e.expect(e.do("GET", "/products/p-1/reviews", "u1", "", ""), 200).obj(t)
	if after["summary"].(map[string]any)["count"].(float64) != count+1 {
		t.Fatalf("new review should be counted")
	}
	if first := after["items"].([]any)[0].(map[string]any); first["mine"] != true {
		t.Fatalf("newest review should be marked mine: %v", first)
	}
	e.expect(e.do("POST", "/products/p-1/reviews", "u1", "", `{"rating":4,"comment":"Lần hai thử xem"}`), 409)
	e.expect(e.do("POST", "/products/p-1/reviews", "u2", "", `{"rating":9,"comment":"Điểm không hợp lệ"}`), 422)
	e.expect(e.do("POST", "/products/p-1/reviews", "u2", "", `{"rating":3,"comment":"ok"}`), 422)

	a := e.expect(e.do("GET", "/products/p-1/extras", "u1", "", ""), 200).obj(t)
	b := e.expect(e.do("GET", "/products/p-1/extras", "u2", "", ""), 200).obj(t)
	ja, _ := json.Marshal(a)
	jb, _ := json.Marshal(b)
	if string(ja) != string(jb) || len(a["gallery"].([]any)) != 4 || len(a["colors"].([]any)) < 2 {
		t.Fatalf("extras must be deterministic per product: %s", ja)
	}
}

func TestReturnsFlowAndRoles(t *testing.T) {
	e := newEnv(t)
	created := e.expect(e.do("POST", "/returns", "u1", "", `{"orderId":"ord-9","reason":"defective","note":"Bị rè","amount":120000}`), 201).obj(t)
	if created["status"] != "REQUESTED" {
		t.Fatalf("new return should be REQUESTED")
	}
	e.expect(e.do("POST", "/returns", "u1", "", `{"orderId":"ord-9","reason":"DEFECTIVE"}`), 409)
	e.expect(e.do("POST", "/returns", "u1", "", `{"orderId":"ord-10","reason":"BORED"}`), 422)
	if mine := e.expect(e.do("GET", "/returns", "u1", "", ""), 200).list(t); len(mine) != 1 {
		t.Fatalf("buyer should only see own returns: %v", mine)
	}

	e.expect(e.do("GET", "/admin/returns", "u1", "seller-owner", ""), 403)
	queue := e.expect(e.do("GET", "/admin/returns", "a1", admin, ""), 200).obj(t)
	if queue["counts"].(map[string]any)["REQUESTED"].(float64) != 2 { // 1 seed + 1 new
		t.Fatalf("admin queue counts wrong: %v", queue["counts"])
	}
	id := created["id"].(string)
	e.expect(e.do("PATCH", "/admin/returns/"+id, "a1", admin, `{"action":"refund"}`), 409)
	e.expect(e.do("PATCH", "/admin/returns/"+id, "a1", admin, `{"action":"approve"}`), 200)
	if refunded := e.expect(e.do("PATCH", "/admin/returns/"+id, "a1", admin, `{"action":"refund"}`), 200).obj(t); refunded["status"] != "REFUNDED" {
		t.Fatalf("approved return should be refundable")
	}
	e.expect(e.do("PATCH", "/admin/returns/"+id, "a1", admin, `{"action":"explode"}`), 422)
	e.expect(e.do("PATCH", "/admin/returns/nope", "a1", admin, `{"action":"approve"}`), 404)
	filtered := e.expect(e.do("GET", "/admin/returns?status=refunded", "a1", admin, ""), 200).obj(t)
	if len(filtered["items"].([]any)) != 1 {
		t.Fatalf("status filter should return one refunded item")
	}
	audit := e.expect(e.do("GET", "/admin/audit?q=RETURN_REFUNDED", "a1", admin, ""), 200).list(t)
	if len(audit) != 1 {
		t.Fatalf("admin actions must land in the audit log: %v", audit)
	}
}

func TestNotifications(t *testing.T) {
	e := newEnv(t)
	base := e.expect(e.do("GET", "/notifications", "u1", "", ""), 200).obj(t)
	if base["unread"].(float64) != 4 {
		t.Fatalf("all fixtures start unread: %v", base["unread"])
	}
	e.expect(e.do("POST", "/payments", "u1", "", `{"orderId":"ord-n","method":"momo","amount":1000}`), 202)
	e.clock.Advance(6 * time.Second)
	after := e.expect(e.do("GET", "/notifications", "u1", "", ""), 200).obj(t)
	if first := after["items"].([]any)[0].(map[string]any); !strings.Contains(first["title"].(string), "MoMo") {
		t.Fatalf("a finished payment should surface as the newest notification: %v", first)
	}
	e.expect(e.do("POST", "/notifications/read", "u1", "", ""), 200)
	if read := e.expect(e.do("GET", "/notifications", "u1", "", ""), 200).obj(t); read["unread"].(float64) != 0 {
		t.Fatalf("mark-as-read should clear unread: %v", read["unread"])
	}
}

func TestServerSentEvents(t *testing.T) {
	e := newEnv(t, func(c *Config) { c.EventInterval = 20 * time.Millisecond })
	srv := httptest.NewServer(e.h)
	defer srv.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, "GET", srv.URL+prefix+"/events", nil)
	req.Header.Set("X-User", "u1")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if ct := resp.Header.Get("Content-Type"); ct != "text/event-stream" {
		t.Fatalf("content-type = %q", ct)
	}
	scanner := bufio.NewScanner(resp.Body)
	var titles []string
	for scanner.Scan() && len(titles) < 2 {
		if line := scanner.Text(); strings.HasPrefix(line, "data: ") {
			var ev map[string]any
			if err := json.Unmarshal([]byte(strings.TrimPrefix(line, "data: ")), &ev); err != nil {
				t.Fatalf("bad event payload: %q", line)
			}
			titles = append(titles, ev["title"].(string))
		}
	}
	if len(titles) != 2 || titles[0] == titles[1] {
		t.Fatalf("expected two different events, got %v", titles)
	}
}

func TestChaosParameters(t *testing.T) {
	e := newEnv(t)
	if r := e.expect(e.do("GET", "/vouchers?fail=1", "u1", "", ""), 503); r.Success {
		t.Fatalf("fail=1 must return a failure envelope")
	}
	e.expect(e.do("GET", "/vouchers?fail=0", "u1", "", ""), 200)
	started := time.Now()
	e.expect(e.do("GET", "/vouchers?delay=60ms", "u1", "", ""), 200)
	if time.Since(started) < 60*time.Millisecond {
		t.Fatalf("delay=60ms should slow the call down")
	}
	started = time.Now()
	e.expect(e.do("GET", "/vouchers?delay=40", "u1", "", ""), 200)
	if time.Since(started) < 40*time.Millisecond {
		t.Fatalf("a bare number is milliseconds")
	}
	started = time.Now()
	e.expect(e.do("GET", "/config?fail=1&delay=500ms", "", "", ""), 200)
	if time.Since(started) > 400*time.Millisecond {
		t.Fatalf("/config must ignore chaos parameters")
	}
	e2 := newEnv(t, func(c *Config) { c.Rand = func() float64 { return 0.5 } })
	e2.expect(e2.do("GET", "/vouchers?fail=0.3", "u1", "", ""), 200)
	e2.expect(e2.do("GET", "/vouchers?fail=0.7", "u1", "", ""), 503)
}

func TestSellerWorkspace(t *testing.T) {
	e := newEnv(t)
	orders := e.expect(e.do("GET", "/seller/orders", "s1", "", ""), 200).obj(t)
	if len(orders["items"].([]any)) != 6 || orders["counts"].(map[string]any)["NEW"].(float64) != 2 {
		t.Fatalf("unexpected seed orders: %v", orders["counts"])
	}
	e.expect(e.do("PATCH", "/seller/orders/SO-1001", "s1", "", `{"action":"ship"}`), 409)
	e.expect(e.do("PATCH", "/seller/orders/SO-1001", "s1", "", `{"action":"confirm"}`), 200)
	e.expect(e.do("PATCH", "/seller/orders/SO-1001", "s1", "", `{"action":"pack"}`), 200)
	if shipped := e.expect(e.do("PATCH", "/seller/orders/SO-1001", "s1", "", `{"action":"ship"}`), 200).obj(t); shipped["status"] != "SHIPPED" {
		t.Fatalf("expected SHIPPED")
	}
	e.expect(e.do("PATCH", "/seller/orders/SO-1002", "s1", "", `{"action":"cancel"}`), 200)
	e.expect(e.do("PATCH", "/seller/orders/SO-1006", "s1", "", `{"action":"cancel"}`), 409)
	e.expect(e.do("PATCH", "/seller/orders/SO-1001", "s1", "", `{"action":"x"}`), 422)
	e.expect(e.do("PATCH", "/seller/orders/SO-9999", "s1", "", `{"action":"confirm"}`), 404)
	if shippedOnly := e.expect(e.do("GET", "/seller/orders?status=shipped", "s1", "", ""), 200).obj(t); len(shippedOnly["items"].([]any)) != 2 {
		t.Fatalf("status filter should find the two shipped orders")
	}
	if other := e.expect(e.do("GET", "/seller/orders", "s2", "", ""), 200).obj(t); other["counts"].(map[string]any)["NEW"].(float64) != 2 {
		t.Fatalf("order state must be per seller")
	}

	inv := e.expect(e.do("PATCH", "/seller/inventory/WH-40-CRM", "s1", "", `{"stock":50}`), 200).list(t)
	for _, item := range inv {
		if item["sku"] == "WH-40-CRM" && (item["stock"].(float64) != 50 || item["low"] != false) {
			t.Fatalf("restock should clear the low flag: %v", item)
		}
	}
	e.expect(e.do("PATCH", "/seller/inventory/WH-40-CRM", "s1", "", `{"stock":-1}`), 422)
	e.expect(e.do("PATCH", "/seller/inventory/NOPE", "s1", "", `{"stock":1}`), 404)

	promos := e.expect(e.do("GET", "/seller/promotions", "s1", "", ""), 200).list(t)
	if len(promos) != 2 {
		t.Fatalf("seed promotions missing")
	}
	made := e.expect(e.do("POST", "/seller/promotions", "s1", "", `{"name":"Giảm 20% mùa thu","kind":"percent","value":20,"minSpend":100000}`), 201).obj(t)
	if made["status"] != "ACTIVE" {
		t.Fatalf("new promotion starts ACTIVE")
	}
	if toggled := e.expect(e.do("POST", "/seller/promotions/"+made["id"].(string)+"/toggle", "s1", "", ""), 200).obj(t); toggled["status"] != "PAUSED" {
		t.Fatalf("toggle should pause an active promotion")
	}
	e.expect(e.do("POST", "/seller/promotions", "s1", "", `{"name":"ab","kind":"percent","value":20}`), 422)
	e.expect(e.do("POST", "/seller/promotions", "s1", "", `{"name":"Hợp lệ","kind":"percent","value":95}`), 422)
	e.expect(e.do("POST", "/seller/promotions", "s1", "", `{"name":"Hợp lệ","kind":"bogus","value":5}`), 422)

	dash := e.expect(e.do("GET", "/seller/dashboard", "s1", "", ""), 200).obj(t)
	if len(dash["series"].([]any)) != 7 || dash["kpis"].(map[string]any)["revenue7d"].(float64) <= 0 {
		t.Fatalf("dashboard should have a 7-day series: %v", dash["kpis"])
	}
	again := e.expect(e.do("GET", "/seller/dashboard", "s1", "", ""), 200).obj(t)
	if a, b := dash["series"], again["series"]; len(a.([]any)) != len(b.([]any)) || a.([]any)[3].(map[string]any)["revenue"] != b.([]any)[3].(map[string]any)["revenue"] {
		t.Fatalf("dashboard numbers must be stable for the same day")
	}
}

func TestSellerMessagesFinanceAndSettings(t *testing.T) {
	e := newEnv(t)
	threads := e.expect(e.do("GET", "/seller/messages", "s1", "", ""), 200).list(t)
	if threads[1]["unread"] != true {
		t.Fatalf("thread ending on a buyer message is unread")
	}
	e.expect(e.do("POST", "/seller/messages/th-2", "s1", "", `{"text":"Dạ dùng được ạ"}`), 201)
	now := e.expect(e.do("GET", "/seller/messages", "s1", "", ""), 200).list(t)
	if msgs := now[1]["messages"].([]any); msgs[len(msgs)-1].(map[string]any)["from"] != "seller" {
		t.Fatalf("buyer's canned reply must not appear instantly")
	}
	e.clock.Advance(4 * time.Second)
	later := e.expect(e.do("GET", "/seller/messages", "s1", "", ""), 200).list(t)
	if msgs := later[1]["messages"].([]any); msgs[len(msgs)-1].(map[string]any)["from"] != "buyer" {
		t.Fatalf("buyer should reply after 3s")
	}
	e.expect(e.do("POST", "/seller/messages/th-2", "s1", "", `{"text":"  "}`), 422)
	e.expect(e.do("POST", "/seller/messages/nope", "s1", "", `{"text":"hi"}`), 404)

	fin := e.expect(e.do("GET", "/seller/finance", "s1", "", ""), 200).obj(t)
	balance := fin["availableBalance"].(float64)
	e.expect(e.do("POST", "/seller/payouts", "s1", "", `{"amount":50000}`), 422)
	e.expect(e.do("POST", "/seller/payouts", "s1", "", `{"amount":999999999}`), 422)
	po := e.expect(e.do("POST", "/seller/payouts", "s1", "", `{"amount":1000000}`), 202).obj(t)
	if po["status"] != "PROCESSING" {
		t.Fatalf("payout starts PROCESSING")
	}
	fin2 := e.expect(e.do("GET", "/seller/finance", "s1", "", ""), 200).obj(t)
	if fin2["availableBalance"].(float64) != balance-1000000 {
		t.Fatalf("payout should reduce available balance")
	}
	e.clock.Advance(4 * time.Second)
	fin3 := e.expect(e.do("GET", "/seller/finance", "s1", "", ""), 200).obj(t)
	if fin3["payouts"].([]any)[0].(map[string]any)["status"] != "COMPLETED" {
		t.Fatalf("payout should complete after 3s: %v", fin3["payouts"])
	}

	if def := e.expect(e.do("GET", "/seller/settings", "s1", "", ""), 200).obj(t); def["returnDays"].(float64) != 7 {
		t.Fatalf("default settings missing")
	}
	e.expect(e.do("PUT", "/seller/settings", "s1", "", `{"shopName":"Tech House","description":"x","phone":"0901 234 567","returnDays":14,"notifyOrders":true}`), 200)
	if saved := e.expect(e.do("GET", "/seller/settings", "s1", "", ""), 200).obj(t); saved["shopName"] != "Tech House" || saved["returnDays"].(float64) != 14 {
		t.Fatalf("settings should persist: %v", saved)
	}
	e.expect(e.do("PUT", "/seller/settings", "s1", "", `{"shopName":"A","returnDays":7}`), 422)
	e.expect(e.do("PUT", "/seller/settings", "s1", "", `{"shopName":"Hợp lệ","returnDays":99}`), 422)
	e.expect(e.do("PUT", "/seller/settings", "s1", "", `{"shopName":"Hợp lệ","phone":"abc","returnDays":7}`), 422)
}

func TestAdminFinanceAndAnalytics(t *testing.T) {
	e := newEnv(t)
	e.expect(e.do("GET", "/admin/finance", "u1", "customer", ""), 403)
	fin := e.expect(e.do("GET", "/admin/finance", "a1", "finance-operator", ""), 200).obj(t)
	if fin["totals"].(map[string]any)["pendingPayout"].(float64) != 17527500+5899500 {
		t.Fatalf("pending payout should sum the pending settlements: %v", fin["totals"])
	}
	e.expect(e.do("POST", "/admin/finance/settlements/st-1/approve", "a1", admin, ""), 200)
	e.expect(e.do("POST", "/admin/finance/settlements/st-1/approve", "a1", admin, ""), 409)
	e.expect(e.do("POST", "/admin/finance/settlements/st-3/approve", "a1", admin, ""), 409)
	e.expect(e.do("POST", "/admin/finance/settlements/nope/approve", "a1", admin, ""), 404)
	after := e.expect(e.do("GET", "/admin/finance", "a1", admin, ""), 200).obj(t)
	if after["totals"].(map[string]any)["pendingPayout"].(float64) != 5899500 {
		t.Fatalf("approved settlement should leave the pending total: %v", after["totals"])
	}

	a := e.expect(e.do("GET", "/admin/analytics", "a1", admin, ""), 200).obj(t)
	b := e.expect(e.do("GET", "/admin/analytics", "a1", admin, ""), 200).obj(t)
	ja, _ := json.Marshal(a)
	jb, _ := json.Marshal(b)
	if string(ja) != string(jb) || len(a["series"].([]any)) != 7 {
		t.Fatalf("analytics must be deterministic and default to 7 days")
	}
	if month := e.expect(e.do("GET", "/admin/analytics?range=30d", "a1", admin, ""), 200).obj(t); len(month["series"].([]any)) != 30 {
		t.Fatalf("30d range should have 30 points")
	}
	e.expect(e.do("GET", "/admin/analytics?range=1y", "a1", admin, ""), 400)
	funnel := a["funnel"].([]any)
	if funnel[0].(map[string]any)["value"].(float64) <= funnel[3].(map[string]any)["value"].(float64) {
		t.Fatalf("a funnel narrows: %v", funnel)
	}
	seed := e.expect(e.do("GET", "/admin/audit", "a1", admin, ""), 200).list(t)
	if len(seed) < 4 || seed[0]["action"] != "SETTLEMENT_PAID" {
		t.Fatalf("audit should list the new action first: %v", seed[0])
	}
}
