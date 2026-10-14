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

// With MOCK_API_ENABLED off the mock routes are never registered, so the
// generic API handler must answer 404 instead of leaking mock data.
func TestMockRoutesAreAbsentWhenDisabled(t *testing.T) {
	s := &server{}
	recorder := httptest.NewRecorder()
	s.api(recorder, httptest.NewRequest("GET", "http://bff/api/v2/mock/config", nil))
	if recorder.Code != 404 {
		t.Fatalf("status = %d, want 404", recorder.Code)
	}
}

func TestCanonicalLoginRedirectSkipsCanonicalHost(t *testing.T) {
	request := httptest.NewRequest("GET", "http://shopping-cart.localhost:8080/api/v2/auth/login", nil)
	if got := canonicalLoginRedirect(request, "http://shopping-cart.localhost:8080"); got != "" {
		t.Fatalf("unexpected redirect: %q", got)
	}
}
