package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

type Config struct {
	Address            string
	PublicURL          string
	FrontendURL        string
	CookieSecure       bool
	SessionSecret      string
	SessionTTL         time.Duration
	RedisAddress       string
	RedisPassword      string
	RedisDB            int
	OIDCIssuerInternal string
	OIDCAuthorizeURL   string
	OIDCEndSessionURL  string
	OIDCClientID       string
	OIDCClientSecret   string
	OIDCRedirectURL    string
	ProductCatalogURL  string
	BasketURL          string
	OrderURL           string
	PaymentURL         string
	AccountURL         string
	SellerURL          string
}

func Load() (Config, error) {
	cfg := Config{
		Address:            env("HTTP_ADDRESS", ":8080"),
		PublicURL:          env("PUBLIC_URL", "http://shopping-cart.localhost:8080"),
		FrontendURL:        env("FRONTEND_URL", "http://shopping-cart.localhost:8080"),
		CookieSecure:       envBool("COOKIE_SECURE", false),
		SessionSecret:      os.Getenv("SESSION_SECRET"),
		SessionTTL:         envDuration("SESSION_TTL", 8*time.Hour),
		RedisAddress:       env("REDIS_ADDRESS", "redis-cart.shopping-cart-data.svc.cluster.local:6379"),
		RedisPassword:      os.Getenv("REDIS_PASSWORD"),
		RedisDB:            envInt("REDIS_DB", 2),
		OIDCIssuerInternal: env("OIDC_ISSUER_INTERNAL", "http://keycloak.shopping-cart-identity.svc.cluster.local/realms/shopping-cart"),
		OIDCAuthorizeURL:   env("OIDC_AUTHORIZE_URL", "http://keycloak.localhost:8080/realms/shopping-cart/protocol/openid-connect/auth"),
		OIDCEndSessionURL:  env("OIDC_END_SESSION_URL", "http://keycloak.localhost:8080/realms/shopping-cart/protocol/openid-connect/logout"),
		OIDCClientID:       env("OIDC_CLIENT_ID", "commerce-bff"),
		OIDCClientSecret:   os.Getenv("OIDC_CLIENT_SECRET"),
		OIDCRedirectURL:    env("OIDC_REDIRECT_URL", "http://shopping-cart.localhost:8080/api/v2/auth/callback"),
		ProductCatalogURL:  env("PRODUCT_CATALOG_URL", "http://product-catalog.shopping-cart-apps.svc.cluster.local"),
		BasketURL:          env("BASKET_URL", "http://basket-service.shopping-cart-apps.svc.cluster.local:8083"),
		OrderURL:           env("ORDER_URL", "http://order-service.shopping-cart-apps.svc.cluster.local"),
		PaymentURL:         env("PAYMENT_URL", "http://payment-service.shopping-cart-payment.svc.cluster.local"),
		AccountURL:         env("ACCOUNT_URL", "http://account-service.shopping-cart-apps.svc.cluster.local"),
		SellerURL:          env("SELLER_URL", "http://seller-service.shopping-cart-apps.svc.cluster.local"),
	}
	if len(cfg.SessionSecret) < 32 {
		return Config{}, fmt.Errorf("SESSION_SECRET must contain at least 32 characters")
	}
	if cfg.OIDCClientSecret == "" {
		return Config{}, fmt.Errorf("OIDC_CLIENT_SECRET is required")
	}
	return cfg, nil
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func envBool(key string, fallback bool) bool {
	value, err := strconv.ParseBool(os.Getenv(key))
	if err != nil {
		return fallback
	}
	return value
}

func envInt(key string, fallback int) int {
	value, err := strconv.Atoi(os.Getenv(key))
	if err != nil {
		return fallback
	}
	return value
}

func envDuration(key string, fallback time.Duration) time.Duration {
	value, err := time.ParseDuration(os.Getenv(key))
	if err != nil {
		return fallback
	}
	return value
}
