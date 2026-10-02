package main

import (
	"context"
	"crypto/subtle"
	"encoding/json"
	"github.com/wilddog64/account-service/internal/telemetry"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/wilddog64/account-service/internal/keycloak"
)

type server struct {
	keycloak         *keycloak.Client
	serviceAuthToken string
}

const defaultCountryID = "VN"

type userInput struct {
	Username  string   `json:"username"`
	Password  string   `json:"password"`
	Name      string   `json:"name"`
	Email     string   `json:"email"`
	CountryID string   `json:"countryId"`
	Roles     []string `json:"roles"`
	Enabled   *bool    `json:"enabled,omitempty"`
}

func main() {

	flush, err := telemetry.Init(context.Background())
	if err != nil {
		panic("tracing initialization failed")
	}
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = flush(ctx)
	}()

	secret := os.Getenv("KEYCLOAK_CLIENT_SECRET")
	if secret == "" {
		log.Fatal("KEYCLOAK_CLIENT_SECRET is required")
	}
	serviceAuthToken := os.Getenv("SERVICE_AUTH_TOKEN")
	if serviceAuthToken == "" {
		log.Fatal("SERVICE_AUTH_TOKEN is required")
	}
	s := &server{keycloak: keycloak.New(env("KEYCLOAK_URL", "http://keycloak.shopping-cart-identity.svc.cluster.local"), env("KEYCLOAK_REALM", "shopping-cart"), env("KEYCLOAK_CLIENT_ID", "account-service"), secret), serviceAuthToken: serviceAuthToken}
	mux := http.NewServeMux()
	mux.HandleFunc("/health/live", health)
	mux.HandleFunc("/health/ready", health)
	mux.HandleFunc("/api/v1/users", s.users)
	mux.HandleFunc("/api/v1/users/", s.user)
	mux.HandleFunc("/internal/v1/users/", s.internalUser)
	srv := &http.Server{Addr: env("HTTP_ADDRESS", ":8080"), Handler: telemetry.HTTPHandler("account-service", headers(mux)), ReadHeaderTimeout: 5 * time.Second}
	log.Printf("account-service listening on %s", srv.Addr)
	if err := telemetry.Serve(srv); err != nil {
		log.Printf("HTTP server stopped: %v", err)
	}
}

func (s *server) internalUser(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	provided := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
	if len(provided) != len(s.serviceAuthToken) || subtle.ConstantTimeCompare([]byte(provided), []byte(s.serviceAuthToken)) != 1 {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"message": "Service authentication failed"})
		return
	}
	path := strings.Trim(strings.TrimPrefix(r.URL.Path, "/internal/v1/users/"), "/")
	parts := strings.Split(path, "/")
	if len(parts) != 2 || parts[0] == "" || parts[1] != "roles" {
		http.NotFound(w, r)
		return
	}
	var input struct {
		Roles []string `json:"roles"`
	}
	if !decode(w, r, &input) || len(input.Roles) == 0 {
		return
	}
	if err := s.keycloak.AddRoles(r.Context(), parts[0], input.Roles); err != nil {
		serverError(w, err)
		return
	}
	log.Printf("audit action=user.roles-add actor=service target=%s roles=%s", parts[0], strings.Join(input.Roles, ","))
	w.WriteHeader(http.StatusNoContent)
}
func health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "up"})
}

func (s *server) users(w http.ResponseWriter, r *http.Request) {
	if !authorized(r) {
		writeJSON(w, http.StatusForbidden, map[string]string{"message": "Bạn không có quyền quản lý người dùng"})
		return
	}
	switch r.Method {
	case http.MethodGet:
		users, err := s.keycloak.ListUsers(r.Context(), r.URL.Query().Get("search"))
		if err != nil {
			serverError(w, err)
			return
		}
		result := make([]map[string]any, 0, len(users))
		for _, user := range users {
			result = append(result, toResponse(user))
		}
		writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": result})
	case http.MethodPost:
		var input userInput
		if !decode(w, r, &input) || input.Password == "" {
			return
		}
		countryID, ok := countryID(input.CountryID, defaultCountryID)
		if !ok {
			invalidCountryID(w)
			return
		}
		created, err := s.keycloak.CreateUser(r.Context(), keycloak.User{Username: input.Username, Email: input.Email, FirstName: input.Name, CountryID: countryID, Enabled: true, Roles: input.Roles}, input.Password)
		if err != nil {
			serverError(w, err)
			return
		}
		log.Printf("audit action=user.create actor=%s target=%s", r.Header.Get("X-User-ID"), created.ID)
		writeJSON(w, http.StatusCreated, map[string]any{"success": true, "data": toResponse(created)})
	default:
		methodNotAllowed(w)
	}
}

func (s *server) user(w http.ResponseWriter, r *http.Request) {
	if !authorized(r) {
		writeJSON(w, http.StatusForbidden, map[string]string{"message": "Bạn không có quyền quản lý người dùng"})
		return
	}
	path := strings.TrimPrefix(r.URL.Path, "/api/v1/users/")
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) == 0 || parts[0] == "" {
		http.NotFound(w, r)
		return
	}
	id := parts[0]
	actor := r.Header.Get("X-User-ID")
	if len(parts) == 2 && parts[1] == "logout" && r.Method == http.MethodPost {
		if err := s.keycloak.LogoutUser(r.Context(), id); err != nil {
			serverError(w, err)
			return
		}
		log.Printf("audit action=user.logout actor=%s target=%s", actor, id)
		w.WriteHeader(http.StatusNoContent)
		return
	}
	if len(parts) == 2 && parts[1] == "reset-password" && r.Method == http.MethodPost {
		var input struct {
			Password string `json:"password"`
		}
		if !decode(w, r, &input) || input.Password == "" {
			return
		}
		if err := s.keycloak.ResetPassword(r.Context(), id, input.Password, true); err != nil {
			serverError(w, err)
			return
		}
		log.Printf("audit action=user.password-reset actor=%s target=%s", actor, id)
		w.WriteHeader(http.StatusNoContent)
		return
	}
	if len(parts) != 1 {
		http.NotFound(w, r)
		return
	}
	target, err := s.keycloak.GetUser(r.Context(), id)
	if err != nil {
		serverError(w, err)
		return
	}
	switch r.Method {
	case http.MethodPut:
		var input userInput
		if !decode(w, r, &input) {
			return
		}
		countryID, ok := countryID(input.CountryID, target.CountryID)
		if !ok {
			invalidCountryID(w)
			return
		}
		enabled := target.Enabled
		if input.Enabled != nil {
			enabled = *input.Enabled
		}
		if actor == id && (!enabled || !contains(input.Roles, "platform-admin") && contains(target.Roles, "platform-admin")) {
			writeJSON(w, http.StatusConflict, map[string]string{"message": "Không thể tự khóa hoặc tự gỡ quyền platform-admin"})
			return
		}
		if contains(target.Roles, "platform-admin") && (!enabled || !contains(input.Roles, "platform-admin")) {
			count, err := s.keycloak.CountEnabledPlatformAdmins(r.Context())
			if err != nil {
				serverError(w, err)
				return
			}
			if count <= 1 {
				writeJSON(w, http.StatusConflict, map[string]string{"message": "Không thể vô hiệu hóa platform admin cuối cùng"})
				return
			}
		}
		updated, err := s.keycloak.UpdateUser(r.Context(), id, keycloak.User{Username: input.Username, Email: input.Email, FirstName: input.Name, CountryID: countryID, Attributes: target.Attributes, Enabled: enabled, Roles: input.Roles})
		if err != nil {
			serverError(w, err)
			return
		}
		if input.Password != "" {
			if err := s.keycloak.ResetPassword(r.Context(), id, input.Password, true); err != nil {
				serverError(w, err)
				return
			}
		}
		log.Printf("audit action=user.update actor=%s target=%s", actor, id)
		writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": toResponse(updated)})
	case http.MethodDelete:
		if actor == id {
			writeJSON(w, http.StatusConflict, map[string]string{"message": "Không thể tự khóa tài khoản đang đăng nhập"})
			return
		}
		if contains(target.Roles, "platform-admin") {
			count, err := s.keycloak.CountEnabledPlatformAdmins(r.Context())
			if err != nil {
				serverError(w, err)
				return
			}
			if count <= 1 {
				writeJSON(w, http.StatusConflict, map[string]string{"message": "Không thể vô hiệu hóa platform admin cuối cùng"})
				return
			}
		}
		if err := s.keycloak.DisableUser(r.Context(), id); err != nil {
			serverError(w, err)
			return
		}
		log.Printf("audit action=user.disable actor=%s target=%s", actor, id)
		w.WriteHeader(http.StatusNoContent)
	default:
		methodNotAllowed(w)
	}
}

func authorized(r *http.Request) bool {
	roles := strings.Split(strings.ToLower(r.Header.Get("X-User-Roles")), ",")
	return contains(roles, "platform-admin") || contains(roles, "user-admin")
}
func toResponse(user keycloak.User) map[string]any {
	return map[string]any{"id": user.ID, "username": user.Username, "email": user.Email, "name": user.FirstName, "countryId": user.CountryID, "roles": user.Roles, "enabled": user.Enabled}
}
func contains(values []string, target string) bool {
	for _, value := range values {
		if strings.TrimSpace(value) == target {
			return true
		}
	}
	return false
}

func countryID(value, fallback string) (string, bool) {
	value = strings.ToUpper(strings.TrimSpace(value))
	if value == "" {
		value = strings.ToUpper(strings.TrimSpace(fallback))
	}
	if len(value) != 2 || value[0] < 'A' || value[0] > 'Z' || value[1] < 'A' || value[1] > 'Z' {
		return "", false
	}
	return value, true
}

func invalidCountryID(w http.ResponseWriter) {
	writeJSON(w, http.StatusBadRequest, map[string]string{"message": "countryId phải là mã quốc gia ISO 3166-1 alpha-2"})
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
	log.Printf("account operation failed: %v", err)
	writeJSON(w, http.StatusBadGateway, map[string]string{"message": "Không thể cập nhật tài khoản lúc này"})
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
