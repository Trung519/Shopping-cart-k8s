package oidc

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/wilddog64/commerce-bff/internal/session"
)

type Client struct {
	issuer, authorizeURL, endSessionURL, clientID, clientSecret, redirectURL string
	httpClient                                                               *http.Client
}

type Tokens struct {
	AccessToken  string
	RefreshToken string
	IDToken      string
	ExpiresAt    time.Time
	User         session.User
}

type tokenResponse struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	IDToken      string `json:"id_token"`
	ExpiresIn    int    `json:"expires_in"`
}

func New(issuer, authorizeURL, endSessionURL, clientID, clientSecret, redirectURL string) *Client {
	return &Client{issuer: strings.TrimRight(issuer, "/"), authorizeURL: authorizeURL, endSessionURL: endSessionURL, clientID: clientID, clientSecret: clientSecret, redirectURL: redirectURL, httpClient: &http.Client{Timeout: 10 * time.Second}}
}

func (c *Client) AuthorizationURL(state, challenge string) string {
	query := url.Values{"client_id": {c.clientID}, "redirect_uri": {c.redirectURL}, "response_type": {"code"}, "scope": {"openid profile email"}, "state": {state}, "code_challenge": {challenge}, "code_challenge_method": {"S256"}}
	return c.authorizeURL + "?" + query.Encode()
}

func (c *Client) Exchange(ctx context.Context, code, verifier string) (Tokens, error) {
	return c.tokenRequest(ctx, url.Values{"grant_type": {"authorization_code"}, "code": {code}, "redirect_uri": {c.redirectURL}, "code_verifier": {verifier}})
}

func (c *Client) Refresh(ctx context.Context, refreshToken string) (Tokens, error) {
	return c.tokenRequest(ctx, url.Values{"grant_type": {"refresh_token"}, "refresh_token": {refreshToken}})
}

func (c *Client) tokenRequest(ctx context.Context, form url.Values) (Tokens, error) {
	form.Set("client_id", c.clientID)
	form.Set("client_secret", c.clientSecret)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.issuer+"/protocol/openid-connect/token", strings.NewReader(form.Encode()))
	if err != nil {
		return Tokens{}, err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return Tokens{}, fmt.Errorf("OIDC token request: %w", err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return Tokens{}, err
	}
	if resp.StatusCode != http.StatusOK {
		return Tokens{}, fmt.Errorf("OIDC token request returned %d", resp.StatusCode)
	}
	var token tokenResponse
	if err := json.Unmarshal(body, &token); err != nil {
		return Tokens{}, fmt.Errorf("decode OIDC token: %w", err)
	}
	user, err := userFromTokens(token.AccessToken, token.IDToken, c.clientID)
	if err != nil {
		return Tokens{}, err
	}
	if token.RefreshToken == "" {
		token.RefreshToken = form.Get("refresh_token")
	}
	return Tokens{AccessToken: token.AccessToken, RefreshToken: token.RefreshToken, IDToken: token.IDToken, ExpiresAt: time.Now().Add(time.Duration(token.ExpiresIn) * time.Second), User: user}, nil
}

func (c *Client) EndSessionURL(idToken, postLogoutRedirectURI string) string {
	query := url.Values{
		"client_id":                {c.clientID},
		"post_logout_redirect_uri": {postLogoutRedirectURI},
	}
	if idToken != "" {
		query.Set("id_token_hint", idToken)
	}
	return c.endSessionURL + "?" + query.Encode()
}

func userFromTokens(accessToken, idToken, clientID string) (session.User, error) {
	claimsToken := idToken
	if claimsToken == "" {
		claimsToken = accessToken
	}
	parts := strings.Split(claimsToken, ".")
	if len(parts) != 3 {
		return session.User{}, fmt.Errorf("OIDC token does not contain JWT claims")
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return session.User{}, fmt.Errorf("decode OIDC claims: %w", err)
	}
	var claims map[string]any
	if err := json.Unmarshal(payload, &claims); err != nil {
		return session.User{}, fmt.Errorf("decode OIDC claims: %w", err)
	}
	value := func(key string) string { result, _ := claims[key].(string); return result }
	return session.User{ID: value("sub"), Username: value("preferred_username"), Email: value("email"), Name: value("name"), Roles: rolesFromToken(accessToken, clientID)}, nil
}

func rolesFromToken(token, clientID string) []string {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return []string{}
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return []string{}
	}
	var claims struct {
		RealmAccess struct {
			Roles []string `json:"roles"`
		} `json:"realm_access"`
		ResourceAccess map[string]struct {
			Roles []string `json:"roles"`
		} `json:"resource_access"`
	}
	if json.Unmarshal(payload, &claims) != nil {
		return []string{}
	}
	seen := map[string]bool{}
	roles := make([]string, 0)
	for _, role := range append(claims.RealmAccess.Roles, claims.ResourceAccess[clientID].Roles...) {
		if !seen[role] {
			seen[role] = true
			roles = append(roles, role)
		}
	}
	return roles
}

func (c *Client) Logout(ctx context.Context, refreshToken string) {
	form := url.Values{"client_id": {c.clientID}, "client_secret": {c.clientSecret}, "refresh_token": {refreshToken}}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.issuer+"/protocol/openid-connect/logout", strings.NewReader(form.Encode()))
	if err != nil {
		return
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := c.httpClient.Do(req)
	if err == nil {
		resp.Body.Close()
	}
}
