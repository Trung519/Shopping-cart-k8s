package model

// CheckoutResponse represents the checkout result returned to clients.
type CheckoutResponse struct {
	Message string        `json:"message"`
	OrderID string        `json:"orderId"`
	Cart    *CartResponse `json:"cart"`
}
