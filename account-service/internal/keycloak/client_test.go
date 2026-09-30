package keycloak

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
)

func TestReplaceRolesDoesNotDeleteWhenRoleResolutionFails(t *testing.T) {
	var deleted atomic.Bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/realms/test/protocol/openid-connect/token":
			json.NewEncoder(w).Encode(map[string]any{"access_token": "token", "expires_in": 300})
		case r.Method == http.MethodGet && r.URL.Path == "/admin/realms/test/roles/buyer":
			w.WriteHeader(http.StatusForbidden)
		case r.Method == http.MethodDelete:
			deleted.Store(true)
			w.WriteHeader(http.StatusNoContent)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	client := New(server.URL, "test", "client", "secret")
	if err := client.ReplaceRoles(context.Background(), "user-1", []string{"buyer"}); err == nil {
		t.Fatal("expected role resolution error")
	}
	if deleted.Load() {
		t.Fatal("existing roles were deleted before desired roles were resolved")
	}
}

func TestAddRolesNeverDeletesExistingRoles(t *testing.T) {
	var deleted atomic.Bool
	var posted []roleRepresentation
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/realms/test/protocol/openid-connect/token":
			json.NewEncoder(w).Encode(map[string]any{"access_token": "token", "expires_in": 300})
		case r.Method == http.MethodGet && r.URL.Path == "/admin/realms/test/users/user-1/role-mappings/realm":
			json.NewEncoder(w).Encode([]roleRepresentation{{ID: "buyer-id", Name: "buyer"}})
		case r.Method == http.MethodGet && r.URL.Path == "/admin/realms/test/roles/seller-owner":
			json.NewEncoder(w).Encode(roleRepresentation{ID: "seller-id", Name: "seller-owner"})
		case r.Method == http.MethodPost && r.URL.Path == "/admin/realms/test/users/user-1/role-mappings/realm":
			json.NewDecoder(r.Body).Decode(&posted)
			w.WriteHeader(http.StatusNoContent)
		case r.Method == http.MethodDelete:
			deleted.Store(true)
			w.WriteHeader(http.StatusNoContent)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	client := New(server.URL, "test", "client", "secret")
	if err := client.AddRoles(context.Background(), "user-1", []string{"seller-owner"}); err != nil {
		t.Fatalf("AddRoles failed: %v", err)
	}
	if deleted.Load() {
		t.Fatal("AddRoles deleted existing roles")
	}
	if len(posted) != 1 || posted[0].Name != "seller-owner" {
		t.Fatalf("unexpected role mapping payload: %#v", posted)
	}
}
