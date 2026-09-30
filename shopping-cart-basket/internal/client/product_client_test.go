package client

import (
	"encoding/json"
	"testing"
)

func TestProductSnapshotAcceptsStringPrice(t *testing.T) {
	var product ProductSnapshot
	if err := json.Unmarshal([]byte(`{"id":"product-1","price":"999.99","quantity":2,"is_active":true}`), &product); err != nil {
		t.Fatalf("unmarshal string price: %v", err)
	}
	if product.Price != 999.99 {
		t.Fatalf("price = %v, want 999.99", product.Price)
	}
}

func TestProductSnapshotAcceptsNumericPrice(t *testing.T) {
	var product ProductSnapshot
	if err := json.Unmarshal([]byte(`{"id":"product-1","price":299.99,"quantity":2,"is_active":true}`), &product); err != nil {
		t.Fatalf("unmarshal numeric price: %v", err)
	}
	if product.Price != 299.99 {
		t.Fatalf("price = %v, want 299.99", product.Price)
	}
}

func TestProductSnapshotRejectsInvalidPrice(t *testing.T) {
	var product ProductSnapshot
	if err := json.Unmarshal([]byte(`{"id":"product-1","price":"not-a-price"}`), &product); err == nil {
		t.Fatal("expected invalid price to fail")
	}
}
