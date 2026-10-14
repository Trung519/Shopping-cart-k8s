// Package mock serves a fake marketplace API from inside the BFF.
//
// Requests are real HTTP calls that travel FE -> BFF and back, so they show up
// in traces, logs and metrics, but they never reach another service. Responses
// come from embedded fixtures plus small amounts of per-user state in Redis.
// Every response carries "mock": true and an X-Mock header, and every span is
// tagged mock=true so mock traffic is easy to filter out of real dashboards.
package mock

import (
	"crypto/rand"
	"embed"
	"encoding/hex"
	"encoding/json"
	"hash/fnv"
	"log"
	"math"
	"net/http"
	"strconv"
	"strings"
	"time"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

//go:embed fixtures/*.json
var fixtureFS embed.FS

const prefix = "/api/v2/mock"

type Identity struct {
	ID    string
	Name  string
	Roles []string
}

// AuthFunc resolves the signed-in user. It writes the 401 itself when it fails.
type AuthFunc func(http.ResponseWriter, *http.Request) (Identity, bool)

type Config struct {
	PaymentDelay  time.Duration // how long a QR payment stays PENDING
	ShipmentStep  time.Duration // time between shipment tracking steps
	EventInterval time.Duration // gap between pushed notification events
	Now           func() time.Time
	Rand          func() float64 // used by ?fail=; injectable for tests
}

type access int

const (
	accessPublic access = iota
	accessUser
	accessAdmin
)

// adminRoles mirrors the roles the frontend already treats as "admin".
var adminRoles = []string{"admin", "platform-admin", "cart-admin", "user-admin", "seller-reviewer", "catalog-moderator", "order-operator", "finance-operator", "support-agent"}

type handlerFunc func(w http.ResponseWriter, r *http.Request, id Identity)

type Handler struct {
	cfg   Config
	store Store
	auth  AuthFunc
	mux   *http.ServeMux
	fx    fixtures
}

func New(cfg Config, store Store, auth AuthFunc) *Handler {
	if cfg.PaymentDelay <= 0 {
		cfg.PaymentDelay = 5 * time.Second
	}
	if cfg.ShipmentStep <= 0 {
		cfg.ShipmentStep = 10 * time.Second
	}
	if cfg.EventInterval <= 0 {
		cfg.EventInterval = 15 * time.Second
	}
	if cfg.Now == nil {
		cfg.Now = time.Now
	}
	if cfg.Rand == nil {
		cfg.Rand = func() float64 {
			var b [8]byte
			_, _ = rand.Read(b[:])
			return float64(uint64(b[0])<<8|uint64(b[1])) / 65536
		}
	}
	h := &Handler{cfg: cfg, store: store, auth: auth, mux: http.NewServeMux(), fx: loadFixtures()}
	h.routes()
	return h
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) { h.mux.ServeHTTP(w, r) }

func (h *Handler) routes() {
	r := h.route
	r("GET "+prefix+"/config", accessPublic, h.getConfig)

	// Buyer
	r("POST "+prefix+"/payments", accessUser, h.createPayment)
	r("GET "+prefix+"/payments/{id}", accessUser, h.getPayment)
	r("POST "+prefix+"/payments/{id}/cancel", accessUser, h.cancelPayment)
	r("GET "+prefix+"/shipments/{orderId}", accessUser, h.getShipment)
	r("GET "+prefix+"/addresses", accessUser, h.listAddresses)
	r("POST "+prefix+"/addresses", accessUser, h.createAddress)
	r("PUT "+prefix+"/addresses/{id}", accessUser, h.updateAddress)
	r("DELETE "+prefix+"/addresses/{id}", accessUser, h.deleteAddress)
	r("POST "+prefix+"/addresses/{id}/default", accessUser, h.defaultAddress)
	r("GET "+prefix+"/vouchers", accessUser, h.listVouchers)
	r("POST "+prefix+"/vouchers/apply", accessUser, h.applyVoucher)
	r("GET "+prefix+"/products/{id}/reviews", accessUser, h.listReviews)
	r("POST "+prefix+"/products/{id}/reviews", accessUser, h.createReview)
	r("GET "+prefix+"/products/{id}/extras", accessUser, h.getExtras)
	r("GET "+prefix+"/returns", accessUser, h.listReturns)
	r("POST "+prefix+"/returns", accessUser, h.createReturn)
	r("GET "+prefix+"/notifications", accessUser, h.listNotifications)
	r("POST "+prefix+"/notifications/read", accessUser, h.readNotifications)
	r("GET "+prefix+"/events", accessUser, h.events)

	// Seller
	r("GET "+prefix+"/seller/dashboard", accessUser, h.sellerDashboard)
	r("GET "+prefix+"/seller/orders", accessUser, h.sellerOrders)
	r("PATCH "+prefix+"/seller/orders/{id}", accessUser, h.sellerOrderAction)
	r("GET "+prefix+"/seller/inventory", accessUser, h.sellerInventory)
	r("PATCH "+prefix+"/seller/inventory/{sku}", accessUser, h.sellerInventoryUpdate)
	r("GET "+prefix+"/seller/promotions", accessUser, h.sellerPromotions)
	r("POST "+prefix+"/seller/promotions", accessUser, h.sellerPromotionCreate)
	r("POST "+prefix+"/seller/promotions/{id}/toggle", accessUser, h.sellerPromotionToggle)
	r("GET "+prefix+"/seller/messages", accessUser, h.sellerMessages)
	r("POST "+prefix+"/seller/messages/{id}", accessUser, h.sellerMessageReply)
	r("GET "+prefix+"/seller/finance", accessUser, h.sellerFinance)
	r("POST "+prefix+"/seller/payouts", accessUser, h.sellerPayout)
	r("GET "+prefix+"/seller/settings", accessUser, h.sellerSettingsGet)
	r("PUT "+prefix+"/seller/settings", accessUser, h.sellerSettingsPut)

	// Admin
	r("GET "+prefix+"/admin/returns", accessAdmin, h.adminReturns)
	r("PATCH "+prefix+"/admin/returns/{id}", accessAdmin, h.adminReturnAction)
	r("GET "+prefix+"/admin/finance", accessAdmin, h.adminFinance)
	r("POST "+prefix+"/admin/finance/settlements/{id}/approve", accessAdmin, h.adminSettlementApprove)
	r("GET "+prefix+"/admin/analytics", accessAdmin, h.adminAnalytics)
	r("GET "+prefix+"/admin/audit", accessAdmin, h.adminAudit)
}

func (h *Handler) route(pattern string, acc access, fn handlerFunc) {
	scenario := scenarioOf(pattern)
	h.mux.HandleFunc(pattern, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Mock", "true")
		w.Header().Set("Cache-Control", "no-store")
		span := trace.SpanFromContext(r.Context())
		span.SetAttributes(attribute.Bool("mock", true), attribute.String("mock.scenario", scenario))

		var id Identity
		if acc != accessPublic {
			var ok bool
			if id, ok = h.auth(w, r); !ok {
				return
			}
			if acc == accessAdmin && !hasAnyRole(id.Roles, adminRoles) {
				writeFail(w, http.StatusForbidden, "Bạn không có quyền thực hiện thao tác này")
				return
			}
		}
		if pattern != "GET "+prefix+"/config" && !h.chaos(w, r) {
			return
		}
		if sc := span.SpanContext(); sc.IsValid() {
			entry, _ := json.Marshal(map[string]any{"event": "mock_api_call", "mock": true, "service": "commerce-bff", "scenario": scenario, "route": pattern, "trace_id": sc.TraceID().String()})
			log.Print(string(entry))
		}
		fn(w, r, id)
	})
}

// chaos lets a lab user inject latency and failures into any mock call:
// ?delay=800ms (or 800) and ?fail=0.3 (30% of calls return 503).
func (h *Handler) chaos(w http.ResponseWriter, r *http.Request) bool {
	q := r.URL.Query()
	if raw := q.Get("delay"); raw != "" {
		d, err := time.ParseDuration(raw)
		if err != nil {
			if ms, convErr := strconv.Atoi(raw); convErr == nil {
				d, err = time.Duration(ms)*time.Millisecond, nil
			}
		}
		if err == nil && d > 0 {
			if d > 10*time.Second {
				d = 10 * time.Second
			}
			select {
			case <-time.After(d):
			case <-r.Context().Done():
				return false
			}
		}
	}
	if raw := q.Get("fail"); raw != "" {
		if p, err := strconv.ParseFloat(raw, 64); err == nil && h.cfg.Rand() < p {
			writeFail(w, http.StatusServiceUnavailable, "Lỗi giả lập (mock chaos)")
			return false
		}
	}
	return true
}

func (h *Handler) getConfig(w http.ResponseWriter, _ *http.Request, _ Identity) {
	writeOK(w, http.StatusOK, map[string]any{
		"enabled":              true,
		"paymentDelaySeconds":  h.cfg.PaymentDelay.Seconds(),
		"shipmentStepSeconds":  h.cfg.ShipmentStep.Seconds(),
		"paymentMethods":       []string{"momo", "vnpay", "zalopay", "cod"},
		"chaosQueryParameters": []string{"delay", "fail", "outcome", "payDelay"},
	})
}

func scenarioOf(pattern string) string {
	path := pattern[strings.Index(pattern, " ")+1:]
	path = strings.TrimPrefix(path, prefix+"/")
	parts := strings.Split(path, "/")
	if (parts[0] == "seller" || parts[0] == "admin") && len(parts) > 1 {
		return parts[0] + "." + parts[1]
	}
	return parts[0]
}

func hasAnyRole(userRoles, allowed []string) bool {
	have := make(map[string]bool, len(userRoles))
	for _, role := range userRoles {
		have[strings.ToLower(role)] = true
	}
	for _, role := range allowed {
		if have[role] {
			return true
		}
	}
	return false
}

func writeOK(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data, "mock": true})
}

func writeFail(w http.ResponseWriter, status int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]any{"success": false, "message": message, "mock": true})
}

// decode reads a small JSON body and writes a 400 itself when it is malformed.
func decode(w http.ResponseWriter, r *http.Request, out any) bool {
	r.Body = http.MaxBytesReader(w, r.Body, 64<<10)
	if err := json.NewDecoder(r.Body).Decode(out); err != nil {
		writeFail(w, http.StatusBadRequest, "Dữ liệu gửi lên không hợp lệ")
		return false
	}
	return true
}

func newID(kind string) string {
	var b [6]byte
	_, _ = rand.Read(b[:])
	return kind + "_" + hex.EncodeToString(b[:])
}

func hashOf(s string) uint32 {
	f := fnv.New32a()
	_, _ = f.Write([]byte(s))
	return f.Sum32()
}

func ceilSeconds(d time.Duration) int {
	if d <= 0 {
		return 0
	}
	return int(math.Ceil(d.Seconds()))
}

func (h *Handler) now() time.Time { return h.cfg.Now().UTC() }

func (h *Handler) fail500(w http.ResponseWriter, err error) {
	log.Printf("mock store error: %v", err)
	writeFail(w, http.StatusInternalServerError, "Không thể xử lý yêu cầu giả lập")
}
