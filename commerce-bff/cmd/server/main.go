package main

import (
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/wilddog64/commerce-bff/internal/config"
	"github.com/wilddog64/commerce-bff/internal/oidc"
	commerceproxy "github.com/wilddog64/commerce-bff/internal/proxy"
	"github.com/wilddog64/commerce-bff/internal/session"
)

const sessionCookie = "shopcart_session"

type server struct {
	cfg      config.Config
	sessions *session.Store
	oidc     *oidc.Client
	targets  []commerceproxy.Target
}

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatal(err)
	}
	store := session.New(cfg.RedisAddress, cfg.RedisPassword, cfg.RedisDB, cfg.SessionTTL)
	defer store.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := store.Ping(ctx); err != nil {
		log.Fatalf("redis unavailable: %v", err)
	}
	targets := mustTargets(cfg)
	s := &server{cfg: cfg, sessions: store, oidc: oidc.New(cfg.OIDCIssuerInternal, cfg.OIDCAuthorizeURL, cfg.OIDCEndSessionURL, cfg.OIDCClientID, cfg.OIDCClientSecret, cfg.OIDCRedirectURL), targets: targets}
	mux := http.NewServeMux()
	mux.HandleFunc("/health/live", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "up"})
	})
	mux.HandleFunc("/health/ready", s.ready)
	mux.HandleFunc("/api/v2/auth/login", s.login)
	mux.HandleFunc("/api/v2/auth/callback", s.callback)
	mux.HandleFunc("/api/v2/auth/me", s.me)
	mux.HandleFunc("/api/v2/auth/logout", s.logout)
	mux.HandleFunc("/api/v2/", s.api)
	log.Printf("commerce-bff listening on %s", cfg.Address)
	log.Fatal(http.ListenAndServe(cfg.Address, securityHeaders(mux)))
}

func mustTargets(cfg config.Config) []commerceproxy.Target {
	definitions := []struct {
		public, upstream, target string
		publicRead               bool
		allowedRoles             []string
	}{
		{"/api/v2/products", "/api/products", cfg.ProductCatalogURL, true, nil},
		{"/api/v2/cart", "/api/v1/cart", cfg.BasketURL, false, nil},
		{"/api/v2/orders", "/api/orders", cfg.OrderURL, false, nil},
		{"/api/v2/payments", "/api/v1/payments", cfg.PaymentURL, false, nil},
		{"/api/v2/accounts", "/api/v1", cfg.AccountURL, false, []string{"platform-admin", "user-admin"}},
		{"/api/v2/sellers", "/api/v1", cfg.SellerURL, false, nil},
	}
	targets := make([]commerceproxy.Target, 0, len(definitions))
	for _, definition := range definitions {
		target, err := commerceproxy.NewTarget(definition.public, definition.upstream, definition.target, definition.publicRead, definition.allowedRoles)
		if err != nil {
			log.Fatal(err)
		}
		targets = append(targets, target)
	}
	return targets
}

func (s *server) ready(w http.ResponseWriter, r *http.Request) {
	if err := s.sessions.Ping(r.Context()); err != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"status": "down"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "up"})
}

func (s *server) login(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	if redirectURL := canonicalLoginRedirect(r, s.cfg.PublicURL); redirectURL != "" {
		http.Redirect(w, r, redirectURL, http.StatusFound)
		return
	}
	state := randomString(32)
	verifier := randomString(64)
	challengeBytes := sha256.Sum256([]byte(verifier))
	challenge := base64.RawURLEncoding.EncodeToString(challengeBytes[:])
	returnTo := r.URL.Query().Get("returnTo")
	if !strings.HasPrefix(returnTo, "/") || strings.HasPrefix(returnTo, "//") {
		returnTo = "/"
	}
	s.setTemporaryCookie(w, "shopcart_oauth_state", s.sign(state), 600)
	s.setTemporaryCookie(w, "shopcart_pkce", s.sign(verifier), 600)
	s.setTemporaryCookie(w, "shopcart_return_to", s.sign(returnTo), 600)
	http.Redirect(w, r, s.oidc.AuthorizationURL(state, challenge), http.StatusFound)
}

func canonicalLoginRedirect(r *http.Request, publicURL string) string {
	canonical, err := url.Parse(publicURL)
	if err != nil || canonical.Scheme == "" || canonical.Host == "" {
		return ""
	}
	requestHost := r.Host
	if forwarded := strings.TrimSpace(strings.Split(r.Header.Get("X-Forwarded-Host"), ",")[0]); forwarded != "" {
		requestHost = forwarded
	}
	if strings.EqualFold(requestHost, canonical.Host) {
		return ""
	}
	return strings.TrimRight(publicURL, "/") + r.URL.RequestURI()
}

func (s *server) callback(w http.ResponseWriter, r *http.Request) {
	state, ok := s.readSignedCookie(r, "shopcart_oauth_state")
	if !ok || state != r.URL.Query().Get("state") || r.URL.Query().Get("code") == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"message": "Phiên đăng nhập không hợp lệ"})
		return
	}
	verifier, ok := s.readSignedCookie(r, "shopcart_pkce")
	if !ok {
		writeJSON(w, http.StatusBadRequest, map[string]string{"message": "Thiếu PKCE verifier"})
		return
	}
	tokens, err := s.oidc.Exchange(r.Context(), r.URL.Query().Get("code"), verifier)
	if err != nil {
		log.Printf("OIDC callback failed: %v", err)
		writeJSON(w, http.StatusBadGateway, map[string]string{"message": "Không thể hoàn tất đăng nhập"})
		return
	}
	sessionID := randomString(48)
	value := session.Session{ID: sessionID, AccessToken: tokens.AccessToken, RefreshToken: tokens.RefreshToken, IDToken: tokens.IDToken, ExpiresAt: tokens.ExpiresAt, User: tokens.User}
	if err := s.sessions.Save(r.Context(), value); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"message": "Không thể tạo phiên đăng nhập"})
		return
	}
	http.SetCookie(w, &http.Cookie{Name: sessionCookie, Value: s.sign(sessionID), Path: "/", MaxAge: int(s.cfg.SessionTTL.Seconds()), HttpOnly: true, Secure: s.cfg.CookieSecure, SameSite: http.SameSiteLaxMode})
	returnTo, ok := s.readSignedCookie(r, "shopcart_return_to")
	if !ok {
		returnTo = "/"
	}
	s.clearTemporaryCookies(w)
	http.Redirect(w, r, s.cfg.FrontendURL+returnTo, http.StatusFound)
}

func (s *server) me(w http.ResponseWriter, r *http.Request) {
	value, ok := s.currentSession(w, r, true)
	if !ok {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": value.User})
}

func (s *server) logout(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	value, ok := s.currentSession(w, r, false)
	logoutURL := s.oidc.EndSessionURL("", s.cfg.FrontendURL)
	if ok && value != nil {
		s.sessions.Delete(r.Context(), value.ID)
		logoutURL = s.oidc.EndSessionURL(value.IDToken, s.cfg.FrontendURL)
	}
	http.SetCookie(w, &http.Cookie{Name: sessionCookie, Path: "/", MaxAge: -1, HttpOnly: true, Secure: s.cfg.CookieSecure, SameSite: http.SameSiteLaxMode})
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": map[string]string{"logoutUrl": logoutURL}})
}

func (s *server) api(w http.ResponseWriter, r *http.Request) {
	for _, target := range s.targets {
		if r.URL.Path == target.PublicPrefix || strings.HasPrefix(r.URL.Path, target.PublicPrefix+"/") {
			needsAuth := !target.PublicRead || r.Method != http.MethodGet
			value, ok := s.currentSession(w, r, needsAuth)
			if needsAuth && !ok {
				return
			}
			if len(target.AllowedRoles) > 0 && !hasAnyRole(value.User.Roles, target.AllowedRoles) {
				writeJSON(w, http.StatusForbidden, map[string]string{"message": "Bạn không có quyền thực hiện thao tác này"})
				return
			}
			target.ServeHTTP(w, r, value)
			return
		}
	}
	writeJSON(w, http.StatusNotFound, map[string]string{"message": "API không tồn tại"})
}

func hasAnyRole(userRoles, allowed []string) bool {
	roles := make(map[string]bool, len(userRoles))
	for _, role := range userRoles {
		roles[strings.ToLower(role)] = true
	}
	for _, role := range allowed {
		if roles[strings.ToLower(role)] {
			return true
		}
	}
	return false
}

func (s *server) currentSession(w http.ResponseWriter, r *http.Request, required bool) (*session.Session, bool) {
	id, ok := s.readSignedCookie(r, sessionCookie)
	if !ok {
		if required {
			writeJSON(w, http.StatusUnauthorized, map[string]string{"message": "Vui lòng đăng nhập"})
		}
		return nil, false
	}
	value, err := s.sessions.Get(r.Context(), id)
	if err != nil {
		if required {
			writeJSON(w, http.StatusUnauthorized, map[string]string{"message": "Phiên đăng nhập đã hết hạn"})
		}
		return nil, false
	}
	if time.Until(value.ExpiresAt) < 30*time.Second {
		tokens, err := s.oidc.Refresh(r.Context(), value.RefreshToken)
		if err != nil {
			s.sessions.Delete(r.Context(), id)
			if required {
				writeJSON(w, http.StatusUnauthorized, map[string]string{"message": "Phiên đăng nhập đã hết hạn"})
			}
			return nil, false
		}
		value.AccessToken, value.RefreshToken, value.ExpiresAt, value.User = tokens.AccessToken, tokens.RefreshToken, tokens.ExpiresAt, tokens.User
		if s.sessions.Save(r.Context(), *value) != nil {
			return nil, false
		}
	}
	return value, true
}

func (s *server) sign(value string) string {
	mac := hmac.New(sha256.New, []byte(s.cfg.SessionSecret))
	mac.Write([]byte(value))
	return base64.RawURLEncoding.EncodeToString([]byte(value)) + "." + base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}
func (s *server) readSignedCookie(r *http.Request, name string) (string, bool) {
	cookie, err := r.Cookie(name)
	if err != nil {
		return "", false
	}
	parts := strings.Split(cookie.Value, ".")
	if len(parts) != 2 {
		return "", false
	}
	value, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil {
		return "", false
	}
	signature, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return "", false
	}
	mac := hmac.New(sha256.New, []byte(s.cfg.SessionSecret))
	mac.Write(value)
	return string(value), hmac.Equal(signature, mac.Sum(nil))
}
func (s *server) setTemporaryCookie(w http.ResponseWriter, name, value string, maxAge int) {
	http.SetCookie(w, &http.Cookie{Name: name, Value: value, Path: "/api/v2/auth", MaxAge: maxAge, HttpOnly: true, Secure: s.cfg.CookieSecure, SameSite: http.SameSiteLaxMode})
}
func (s *server) clearTemporaryCookies(w http.ResponseWriter) {
	for _, name := range []string{"shopcart_oauth_state", "shopcart_pkce", "shopcart_return_to"} {
		s.setTemporaryCookie(w, name, "", -1)
	}
}
func randomString(size int) string {
	buffer := make([]byte, size)
	if _, err := rand.Read(buffer); err != nil {
		panic(err)
	}
	return base64.RawURLEncoding.EncodeToString(buffer)
}
func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(value)
}
func methodNotAllowed(w http.ResponseWriter) {
	writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"message": "Phương thức không được hỗ trợ"})
}
func securityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
		next.ServeHTTP(w, r)
	})
}
