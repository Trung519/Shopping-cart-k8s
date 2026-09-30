package main

import (
	"net/http/httptest"
	"testing"
)

func TestCanonicalLoginRedirect(t *testing.T) {
	request := httptest.NewRequest("GET", "http://localhost:8080/api/v2/auth/login?returnTo=%2Fadmin", nil)
	got := canonicalLoginRedirect(request, "http://shopping-cart.localhost:8080")
	want := "http://shopping-cart.localhost:8080/api/v2/auth/login?returnTo=%2Fadmin"
	if got != want {
		t.Fatalf("redirect = %q, want %q", got, want)
	}
}

func TestCanonicalLoginRedirectSkipsCanonicalHost(t *testing.T) {
	request := httptest.NewRequest("GET", "http://shopping-cart.localhost:8080/api/v2/auth/login", nil)
	if got := canonicalLoginRedirect(request, "http://shopping-cart.localhost:8080"); got != "" {
		t.Fatalf("unexpected redirect: %q", got)
	}
}
