package client

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

var (
	ErrProductNotFound    = errors.New("product not found")
	ErrProductUnavailable = errors.New("product is unavailable")
)

// ProductSnapshot is the catalog-owned data that may be copied into a cart.
// Price and availability are never accepted from the browser.
type ProductSnapshot struct {
	ID       string  `json:"id"`
	SKU      string  `json:"sku"`
	Name     string  `json:"name"`
	Price    float64 `json:"price"`
	Currency string  `json:"currency"`
	Quantity int     `json:"quantity"`
	Category string  `json:"category"`
	ImageURL string  `json:"image_url"`
	SellerID string  `json:"seller_id"`
	ShopName string  `json:"shop_name"`
	IsActive bool    `json:"is_active"`
}

func (p *ProductSnapshot) UnmarshalJSON(data []byte) error {
	type snapshotAlias ProductSnapshot
	payload := struct {
		*snapshotAlias
		Price json.RawMessage `json:"price"`
	}{snapshotAlias: (*snapshotAlias)(p)}
	if err := json.Unmarshal(data, &payload); err != nil {
		return err
	}
	if len(payload.Price) == 0 || string(payload.Price) == "null" {
		return errors.New("product price is required")
	}
	if payload.Price[0] == '"' {
		var value string
		if err := json.Unmarshal(payload.Price, &value); err != nil {
			return fmt.Errorf("decode product price: %w", err)
		}
		price, err := strconv.ParseFloat(value, 64)
		if err != nil {
			return fmt.Errorf("decode product price: %w", err)
		}
		p.Price = price
		return nil
	}
	if err := json.Unmarshal(payload.Price, &p.Price); err != nil {
		return fmt.Errorf("decode product price: %w", err)
	}
	return nil
}

type ProductCatalogClient interface {
	GetProduct(ctx context.Context, productID string) (*ProductSnapshot, error)
}

// InventoryReservationClient is implemented by production catalog clients.
type InventoryReservationClient interface {
	ReserveInventory(ctx context.Context, items []InventoryItem) error
	ReleaseInventory(ctx context.Context, items []InventoryItem) error
}

type InventoryItem struct {
	ProductID string `json:"product_id"`
	Quantity  int    `json:"quantity"`
}

type HTTPProductCatalogClient struct {
	baseURL       string
	httpClient    *http.Client
	internalToken string
}

func NewProductCatalogClient(baseURL, internalToken string) *HTTPProductCatalogClient {
	return &HTTPProductCatalogClient{
		baseURL:       strings.TrimRight(baseURL, "/"),
		internalToken: internalToken,
		httpClient: &http.Client{
			Timeout: 5 * time.Second,
		},
	}
}

func (c *HTTPProductCatalogClient) ReserveInventory(ctx context.Context, items []InventoryItem) error {
	return c.adjustInventory(ctx, "reserve", items)
}

func (c *HTTPProductCatalogClient) ReleaseInventory(ctx context.Context, items []InventoryItem) error {
	return c.adjustInventory(ctx, "release", items)
}

func (c *HTTPProductCatalogClient) adjustInventory(ctx context.Context, operation string, items []InventoryItem) error {
	body, err := json.Marshal(map[string]any{"operation": operation, "items": items})
	if err != nil {
		return fmt.Errorf("encode inventory request: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/api/products/inventory/batch", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("build inventory request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Internal-Api-Token", c.internalToken)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("catalog inventory request failed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusConflict {
		return ErrProductUnavailable
	}
	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		return fmt.Errorf("catalog inventory returned status %d", resp.StatusCode)
	}
	return nil
}

func (c *HTTPProductCatalogClient) GetProduct(
	ctx context.Context,
	productID string,
) (*ProductSnapshot, error) {
	endpoint := c.baseURL + "/api/products/" + url.PathEscape(productID)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return nil, fmt.Errorf("build product request: %w", err)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("catalog request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound || resp.StatusCode == http.StatusUnprocessableEntity {
		return nil, ErrProductNotFound
	}
	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		return nil, fmt.Errorf("catalog returned status %d", resp.StatusCode)
	}

	var product ProductSnapshot
	if err := json.NewDecoder(resp.Body).Decode(&product); err != nil {
		return nil, fmt.Errorf("decode product response: %w", err)
	}
	if product.ID == "" {
		return nil, ErrProductNotFound
	}
	if !product.IsActive || product.Quantity <= 0 {
		return nil, ErrProductUnavailable
	}
	return &product, nil
}
