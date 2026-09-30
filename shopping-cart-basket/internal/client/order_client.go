package client

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/user/shopping-cart-basket/internal/model"
)

type OrderClient struct {
	baseURL    string
	httpClient *http.Client
}

type createOrderRequest struct {
	CustomerID      string                     `json:"customerId"`
	Items           []createOrderItemRequest   `json:"items"`
	ShippingAddress createOrderAddressRequest  `json:"shippingAddress"`
	Currency        string                     `json:"currency"`
}

type createOrderItemRequest struct {
	ProductID   string  `json:"productId"`
	ProductName string  `json:"productName"`
	Quantity    int     `json:"quantity"`
	UnitPrice   float64 `json:"unitPrice"`
}

type createOrderAddressRequest struct {
	Street     string `json:"street"`
	City       string `json:"city"`
	State      string `json:"state"`
	PostalCode string `json:"postalCode"`
	Country    string `json:"country"`
}

type createOrderResponse struct {
	ID string `json:"id"`
}

func NewOrderClient(baseURL string) *OrderClient {
	return &OrderClient{
		baseURL: strings.TrimRight(baseURL, "/"),
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

func (c *OrderClient) CreateOrder(
	ctx context.Context,
	customerID string,
	cart *model.Cart,
	shippingAddress model.ShippingAddress,
	correlationID string,
) (string, error) {
	reqBody := createOrderRequest{
		CustomerID: customerID,
		Items:      make([]createOrderItemRequest, 0, len(cart.Items)),
		ShippingAddress: createOrderAddressRequest{
			Street:     shippingAddress.Street,
			City:       shippingAddress.City,
			State:      shippingAddress.State,
			PostalCode: shippingAddress.PostalCode,
			Country:    shippingAddress.Country,
		},
		Currency: cart.Currency,
	}

	for _, item := range cart.Items {
		reqBody.Items = append(reqBody.Items, createOrderItemRequest{
			ProductID:   item.ProductID,
			ProductName: item.Name,
			Quantity:    item.Quantity,
			UnitPrice:   item.UnitPrice,
		})
	}

	payload, err := json.Marshal(reqBody)
	if err != nil {
		return "", fmt.Errorf("marshal order request: %w", err)
	}

	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		c.baseURL+"/api/orders",
		bytes.NewReader(payload),
	)
	if err != nil {
		return "", fmt.Errorf("build order request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-User-ID", customerID)
	if correlationID != "" {
		req.Header.Set("X-Correlation-ID", correlationID)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("create order request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		return "", fmt.Errorf("create order failed with status %d", resp.StatusCode)
	}

	var response createOrderResponse
	if err := json.NewDecoder(resp.Body).Decode(&response); err != nil {
		return "", fmt.Errorf("decode order response: %w", err)
	}

	if response.ID == "" {
		return "", fmt.Errorf("order response missing id")
	}

	return response.ID, nil
}
