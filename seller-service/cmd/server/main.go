package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/wilddog64/seller-service/internal/account"
	"github.com/wilddog64/seller-service/internal/store"
)

type roleAssigner interface {
	AddRoles(context.Context, string, ...string) error
}
type server struct {
	store   *store.Store
	account roleAssigner
}
type applicationInput struct {
	Name        string `json:"name"`
	Description string `json:"description"`
}
type reviewInput struct {
	Status string `json:"status"`
	Reason string `json:"reason"`
}

var nonSlug = regexp.MustCompile(`[^a-z0-9]+`)

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	databaseURL := buildDatabaseURL()
	serviceAuthToken := os.Getenv("SERVICE_AUTH_TOKEN")
	if serviceAuthToken == "" {
		log.Fatal("SERVICE_AUTH_TOKEN is required")
	}
	repository, err := store.New(ctx, databaseURL)
	if err != nil {
		log.Fatalf("database unavailable: %v", err)
	}
	defer repository.Close()
	s := &server{store: repository, account: account.New(env("ACCOUNT_SERVICE_URL", "http://account-service.shopping-cart-apps.svc.cluster.local"), serviceAuthToken)}
	mux := http.NewServeMux()
	mux.HandleFunc("/health/live", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "up"})
	})
	mux.HandleFunc("/health/ready", s.ready)
	mux.HandleFunc("/api/v1/me", s.me)
	mux.HandleFunc("/api/v1/applications", s.applications)
	mux.HandleFunc("/api/v1/applications/", s.review)
	srv := &http.Server{Addr: env("HTTP_ADDRESS", ":8080"), Handler: headers(mux), ReadHeaderTimeout: 5 * time.Second}
	log.Printf("seller-service listening on %s", srv.Addr)
	log.Fatal(srv.ListenAndServe())
}
func (s *server) ready(w http.ResponseWriter, r *http.Request) {
	if err := s.store.Ping(r.Context()); err != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"status": "down"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "up"})
}
func (s *server) me(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"message": "Vui lòng đăng nhập"})
		return
	}
	shop, err := s.store.GetByOwner(r.Context(), userID)
	if err == store.ErrNotFound {
		w.WriteHeader(http.StatusNoContent)
		return
	}
	if err != nil {
		serverError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": response(shop)})
}
func (s *server) applications(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"message": "Vui lòng đăng nhập"})
		return
	}
	switch r.Method {
	case http.MethodPost:
		var input applicationInput
		if !decode(w, r, &input) || strings.TrimSpace(input.Name) == "" {
			return
		}
		suffix := strings.ToLower(uuid.NewString()[:6])
		slug := strings.Trim(nonSlug.ReplaceAllString(strings.ToLower(input.Name), "-"), "-") + "-" + suffix
		shop, err := s.store.CreateApplication(r.Context(), userID, slug, strings.TrimSpace(input.Name), strings.TrimSpace(input.Description))
		if err != nil {
			writeJSON(w, http.StatusConflict, map[string]string{"message": "Bạn đã có hồ sơ đăng ký người bán"})
			return
		}
		log.Printf("audit action=seller.apply actor=%s shop=%s", userID, shop.ID)
		writeJSON(w, http.StatusCreated, map[string]any{"success": true, "data": response(shop)})
	case http.MethodGet:
		if !hasRole(r, "platform-admin", "seller-reviewer") {
			writeJSON(w, http.StatusForbidden, map[string]string{"message": "Bạn không có quyền duyệt người bán"})
			return
		}
		shops, err := s.store.List(r.Context(), strings.ToUpper(r.URL.Query().Get("status")))
		if err != nil {
			serverError(w, err)
			return
		}
		result := make([]map[string]any, 0, len(shops))
		for _, shop := range shops {
			result = append(result, response(shop))
		}
		writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": result})
	default:
		methodNotAllowed(w)
	}
}
func (s *server) review(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPatch {
		methodNotAllowed(w)
		return
	}
	if !hasRole(r, "platform-admin", "seller-reviewer") {
		writeJSON(w, http.StatusForbidden, map[string]string{"message": "Bạn không có quyền duyệt người bán"})
		return
	}
	id := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/applications/"), "/")
	var input reviewInput
	if !decode(w, r, &input) {
		return
	}
	input.Status = strings.ToUpper(input.Status)
	if input.Status != "APPROVED" && input.Status != "REJECTED" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"message": "Trạng thái duyệt không hợp lệ"})
		return
	}
	if input.Status == "REJECTED" && strings.TrimSpace(input.Reason) == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"message": "Cần nhập lý do từ chối"})
		return
	}
	if input.Status == "APPROVED" {
		shop, err := s.store.GetByID(r.Context(), id)
		if err != nil {
			serverError(w, err)
			return
		}
		if err := s.account.AddRoles(r.Context(), shop.OwnerUserID, "seller-owner"); err != nil {
			log.Printf("seller role sync failed shop=%s: %v", id, err)
			writeJSON(w, http.StatusBadGateway, map[string]string{"message": "Chưa thể đồng bộ quyền người bán; hồ sơ chưa được duyệt"})
			return
		}
	}
	shop, err := s.store.Review(r.Context(), id, input.Status, strings.TrimSpace(input.Reason))
	if err != nil {
		serverError(w, err)
		return
	}
	log.Printf("audit action=seller.review actor=%s shop=%s status=%s", r.Header.Get("X-User-ID"), shop.ID, shop.Status)
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": response(shop)})
}
func response(shop store.Shop) map[string]any {
	return map[string]any{"id": shop.ID, "ownerUserId": shop.OwnerUserID, "slug": shop.Slug, "name": shop.Name, "description": shop.Description, "status": shop.Status, "rejectionReason": shop.RejectionReason, "createdAt": shop.CreatedAt, "updatedAt": shop.UpdatedAt}
}
func hasRole(r *http.Request, allowed ...string) bool {
	roles := strings.Split(strings.ToLower(r.Header.Get("X-User-Roles")), ",")
	for _, role := range roles {
		for _, candidate := range allowed {
			if strings.TrimSpace(role) == candidate {
				return true
			}
		}
	}
	return false
}
func buildDatabaseURL() string {
	u := &url.URL{Scheme: "postgres", User: url.UserPassword(env("DB_USER", "seller_service"), os.Getenv("DB_PASSWORD")), Host: env("DB_HOST", "postgresql-marketplace.shopping-cart-data.svc.cluster.local") + ":" + env("DB_PORT", "5432"), Path: env("DB_NAME", "seller_service")}
	query := u.Query()
	query.Set("sslmode", env("DB_SSLMODE", "disable"))
	u.RawQuery = query.Encode()
	return u.String()
}
func decode(w http.ResponseWriter, r *http.Request, target any) bool {
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"message": "Dữ liệu không hợp lệ"})
		return false
	}
	return true
}
func serverError(w http.ResponseWriter, err error) {
	log.Printf("seller operation failed: %v", err)
	writeJSON(w, http.StatusInternalServerError, map[string]string{"message": "Không thể xử lý hồ sơ người bán"})
}
func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(value)
}
func methodNotAllowed(w http.ResponseWriter) {
	writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"message": "Phương thức không được hỗ trợ"})
}
func headers(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		next.ServeHTTP(w, r)
	})
}
func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
