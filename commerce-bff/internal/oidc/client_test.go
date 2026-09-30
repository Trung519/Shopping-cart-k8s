package oidc

import (
	"net/url"
	"testing"
)

func TestEndSessionURL(t *testing.T) {
	client := New("http://keycloak/realms/shop", "http://public/auth", "http://public/logout", "commerce-bff", "secret", "http://shop/callback")
	got, err := url.Parse(client.EndSessionURL("id-token", "http://shop/"))
	if err != nil {
		t.Fatal(err)
	}
	if got.String() == "" || got.Query().Get("id_token_hint") != "id-token" {
		t.Fatalf("logout URL does not contain the ID token hint: %q", got.String())
	}
	if got.Query().Get("client_id") != "commerce-bff" || got.Query().Get("post_logout_redirect_uri") != "http://shop/" {
		t.Fatalf("logout URL has invalid client or redirect: %q", got.String())
	}
}
