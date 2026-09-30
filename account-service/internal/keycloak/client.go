package keycloak

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

var MarketplaceRoles = []string{"platform-admin", "user-admin", "seller-reviewer", "catalog-moderator", "order-operator", "finance-operator", "support-agent", "seller-owner", "seller-manager", "seller-staff", "buyer"}

type User struct {
	ID, Username, Email, FirstName, LastName string
	CountryID                                string
	Attributes                               map[string][]string
	Enabled                                  bool
	Roles                                    []string
}

type userRepresentation struct {
	ID              string              `json:"id,omitempty"`
	Username        string              `json:"username"`
	Email           string              `json:"email"`
	FirstName       string              `json:"firstName"`
	LastName        string              `json:"lastName"`
	Enabled         bool                `json:"enabled"`
	EmailVerified   bool                `json:"emailVerified"`
	RequiredActions []string            `json:"requiredActions,omitempty"`
	Attributes      map[string][]string `json:"attributes,omitempty"`
}

type roleRepresentation struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}
type tokenResponse struct {
	AccessToken string `json:"access_token"`
	ExpiresIn   int    `json:"expires_in"`
}

type Client struct {
	baseURL, realm, clientID, clientSecret string
	httpClient                             *http.Client
	mu                                     sync.Mutex
	token                                  string
	expiresAt                              time.Time
}

func New(baseURL, realm, clientID, clientSecret string) *Client {
	return &Client{baseURL: strings.TrimRight(baseURL, "/"), realm: realm, clientID: clientID, clientSecret: clientSecret, httpClient: &http.Client{Timeout: 15 * time.Second}}
}

func (c *Client) tokenFor(ctx context.Context) (string, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.token != "" && time.Until(c.expiresAt) > 30*time.Second {
		return c.token, nil
	}
	form := url.Values{"grant_type": {"client_credentials"}, "client_id": {c.clientID}, "client_secret": {c.clientSecret}}
	req, _ := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/realms/"+url.PathEscape(c.realm)+"/protocol/openid-connect/token", strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("Keycloak token returned %d", resp.StatusCode)
	}
	var token tokenResponse
	if err := json.NewDecoder(resp.Body).Decode(&token); err != nil {
		return "", err
	}
	c.token, c.expiresAt = token.AccessToken, time.Now().Add(time.Duration(token.ExpiresIn)*time.Second)
	return c.token, nil
}

func (c *Client) request(ctx context.Context, method, path string, body any, result any) (*http.Response, error) {
	accessToken, err := c.tokenFor(ctx)
	if err != nil {
		return nil, err
	}
	var reader io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		reader = bytes.NewReader(data)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+"/admin/realms/"+url.PathEscape(c.realm)+path, reader)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		defer resp.Body.Close()
		message, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return resp, fmt.Errorf("Keycloak API %s %s returned %d: %s", method, path, resp.StatusCode, strings.TrimSpace(string(message)))
	}
	if result != nil {
		defer resp.Body.Close()
		if err := json.NewDecoder(resp.Body).Decode(result); err != nil {
			return resp, err
		}
	}
	return resp, nil
}

func (c *Client) ListUsers(ctx context.Context, search string) ([]User, error) {
	path := "/users?max=200"
	if search != "" {
		path += "&search=" + url.QueryEscape(search)
	}
	var records []userRepresentation
	if _, err := c.request(ctx, http.MethodGet, path, nil, &records); err != nil {
		return nil, err
	}
	users := make([]User, 0, len(records))
	for _, record := range records {
		roles, err := c.UserRoles(ctx, record.ID)
		if err != nil {
			return nil, err
		}
		users = append(users, fromRepresentation(record, roles))
	}
	return users, nil
}

func (c *Client) GetUser(ctx context.Context, id string) (User, error) {
	var record userRepresentation
	if _, err := c.request(ctx, http.MethodGet, "/users/"+url.PathEscape(id), nil, &record); err != nil {
		return User{}, err
	}
	roles, err := c.UserRoles(ctx, id)
	if err != nil {
		return User{}, err
	}
	return fromRepresentation(record, roles), nil
}

func (c *Client) CreateUser(ctx context.Context, user User, temporaryPassword string) (User, error) {
	first, last := splitName(user.FirstName)
	record := userRepresentation{Username: user.Username, Email: user.Email, FirstName: first, LastName: last, Enabled: true, EmailVerified: true, RequiredActions: []string{"UPDATE_PASSWORD"}, Attributes: userAttributes(user.Attributes, user.CountryID)}
	resp, err := c.request(ctx, http.MethodPost, "/users", record, nil)
	if err != nil {
		return User{}, err
	}
	resp.Body.Close()
	location := resp.Header.Get("Location")
	id := location[strings.LastIndex(location, "/")+1:]
	if err := c.ResetPassword(ctx, id, temporaryPassword, true); err != nil {
		return User{}, err
	}
	if err := c.ReplaceRoles(ctx, id, user.Roles); err != nil {
		return User{}, err
	}
	return c.GetUser(ctx, id)
}

func (c *Client) UpdateUser(ctx context.Context, id string, user User) (User, error) {
	first, last := splitName(user.FirstName)
	record := userRepresentation{ID: id, Username: user.Username, Email: user.Email, FirstName: first, LastName: last, Enabled: user.Enabled, EmailVerified: true, Attributes: userAttributes(user.Attributes, user.CountryID)}
	resp, err := c.request(ctx, http.MethodPut, "/users/"+url.PathEscape(id), record, nil)
	if resp != nil {
		resp.Body.Close()
	}
	if err != nil {
		return User{}, err
	}
	if err := c.ReplaceRoles(ctx, id, user.Roles); err != nil {
		return User{}, err
	}
	return c.GetUser(ctx, id)
}
func (c *Client) DisableUser(ctx context.Context, id string) error {
	user, err := c.GetUser(ctx, id)
	if err != nil {
		return err
	}
	user.Enabled = false
	_, err = c.UpdateUser(ctx, id, user)
	return err
}
func (c *Client) LogoutUser(ctx context.Context, id string) error {
	resp, err := c.request(ctx, http.MethodPost, "/users/"+url.PathEscape(id)+"/logout", nil, nil)
	if resp != nil {
		resp.Body.Close()
	}
	return err
}
func (c *Client) ResetPassword(ctx context.Context, id, password string, temporary bool) error {
	payload := map[string]any{"type": "password", "value": password, "temporary": temporary}
	resp, err := c.request(ctx, http.MethodPut, "/users/"+url.PathEscape(id)+"/reset-password", payload, nil)
	if resp != nil {
		resp.Body.Close()
	}
	return err
}

func (c *Client) UserRoles(ctx context.Context, id string) ([]string, error) {
	var roles []roleRepresentation
	if _, err := c.request(ctx, http.MethodGet, "/users/"+url.PathEscape(id)+"/role-mappings/realm", nil, &roles); err != nil {
		return nil, err
	}
	allowed := roleSet(MarketplaceRoles)
	names := make([]string, 0)
	for _, role := range roles {
		if allowed[role.Name] {
			names = append(names, role.Name)
		}
	}
	return names, nil
}
func (c *Client) ReplaceRoles(ctx context.Context, id string, names []string) error {
	desired, err := c.resolveRoles(ctx, names)
	if err != nil {
		return err
	}
	current, err := c.roleRepresentations(ctx, id)
	if err != nil {
		return err
	}
	if len(current) > 0 {
		resp, err := c.request(ctx, http.MethodDelete, "/users/"+url.PathEscape(id)+"/role-mappings/realm", current, nil)
		if resp != nil {
			resp.Body.Close()
		}
		if err != nil {
			return err
		}
	}
	if len(desired) > 0 {
		resp, err := c.request(ctx, http.MethodPost, "/users/"+url.PathEscape(id)+"/role-mappings/realm", desired, nil)
		if resp != nil {
			resp.Body.Close()
		}
		return err
	}
	return nil
}

func (c *Client) AddRoles(ctx context.Context, id string, names []string) error {
	current, err := c.UserRoles(ctx, id)
	if err != nil {
		return err
	}
	seen := roleSet(current)
	missing := make([]string, 0, len(names))
	for _, name := range names {
		if !seen[name] {
			missing = append(missing, name)
			seen[name] = true
		}
	}
	roles, err := c.resolveRoles(ctx, missing)
	if err != nil || len(roles) == 0 {
		return err
	}
	resp, err := c.request(ctx, http.MethodPost, "/users/"+url.PathEscape(id)+"/role-mappings/realm", roles, nil)
	if resp != nil {
		resp.Body.Close()
	}
	return err
}

func (c *Client) resolveRoles(ctx context.Context, names []string) ([]roleRepresentation, error) {
	desired := make([]roleRepresentation, 0, len(names))
	allowed := roleSet(MarketplaceRoles)
	for _, name := range names {
		if !allowed[name] {
			return nil, fmt.Errorf("unsupported marketplace role %q", name)
		}
		var role roleRepresentation
		if _, err := c.request(ctx, http.MethodGet, "/roles/"+url.PathEscape(name), nil, &role); err != nil {
			return nil, err
		}
		desired = append(desired, role)
	}
	return desired, nil
}
func (c *Client) roleRepresentations(ctx context.Context, id string) ([]roleRepresentation, error) {
	var all []roleRepresentation
	if _, err := c.request(ctx, http.MethodGet, "/users/"+url.PathEscape(id)+"/role-mappings/realm", nil, &all); err != nil {
		return nil, err
	}
	allowed := roleSet(MarketplaceRoles)
	result := make([]roleRepresentation, 0)
	for _, role := range all {
		if allowed[role.Name] {
			result = append(result, role)
		}
	}
	return result, nil
}
func (c *Client) CountEnabledPlatformAdmins(ctx context.Context) (int, error) {
	users, err := c.ListUsers(ctx, "")
	if err != nil {
		return 0, err
	}
	count := 0
	for _, user := range users {
		if user.Enabled && contains(user.Roles, "platform-admin") {
			count++
		}
	}
	return count, nil
}
func fromRepresentation(record userRepresentation, roles []string) User {
	return User{ID: record.ID, Username: record.Username, Email: record.Email, FirstName: strings.TrimSpace(record.FirstName + " " + record.LastName), CountryID: firstAttribute(record.Attributes, "country_id"), Attributes: record.Attributes, Enabled: record.Enabled, Roles: roles}
}

func userAttributes(attributes map[string][]string, countryID string) map[string][]string {
	result := make(map[string][]string, len(attributes)+1)
	for name, values := range attributes {
		result[name] = append([]string(nil), values...)
	}
	if normalizedCountryID := strings.TrimSpace(countryID); normalizedCountryID != "" {
		result["country_id"] = []string{normalizedCountryID}
	}
	if len(result) == 0 {
		return nil
	}
	return result
}

func firstAttribute(attributes map[string][]string, name string) string {
	if len(attributes[name]) == 0 {
		return ""
	}
	return attributes[name][0]
}
func splitName(name string) (string, string) {
	parts := strings.Fields(name)
	if len(parts) == 0 {
		return "", ""
	}
	if len(parts) == 1 {
		return parts[0], ""
	}
	return strings.Join(parts[:len(parts)-1], " "), parts[len(parts)-1]
}
func roleSet(roles []string) map[string]bool {
	result := map[string]bool{}
	for _, role := range roles {
		result[role] = true
	}
	return result
}
func contains(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}
