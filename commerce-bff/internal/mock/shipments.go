package mock

import (
	"net/http"
	"time"
)

var shipmentSteps = []struct{ Key, Label string }{
	{"PLACED", "Đã đặt hàng"},
	{"CONFIRMED", "Đã xác nhận"},
	{"PACKING", "Đang đóng gói"},
	{"HANDED_OVER", "Đã bàn giao cho đơn vị vận chuyển"},
	{"IN_TRANSIT", "Đang vận chuyển"},
	{"DELIVERED", "Đã giao thành công"},
}

var carriers = []string{"GHN Express", "Giao Hàng Tiết Kiệm", "Viettel Post"}

type shipmentStep struct {
	Key   string     `json:"key"`
	Label string     `json:"label"`
	At    *time.Time `json:"at,omitempty"`
	Done  bool       `json:"done"`
}

type shipmentView struct {
	OrderID      string         `json:"orderId"`
	Status       string         `json:"status"` // WAITING_PAYMENT, PAYMENT_FAILED or a step key
	Carrier      string         `json:"carrier"`
	TrackingCode string         `json:"trackingCode"`
	CurrentStep  int            `json:"currentStep"`
	Steps        []shipmentStep `json:"steps"`
	StepSeconds  float64        `json:"stepSeconds"`
}

// getShipment derives tracking from the clock. The timeline starts when the
// mock payment for the order succeeds; orders without a mock payment start the
// first time somebody looks at them.
func (h *Handler) getShipment(w http.ResponseWriter, r *http.Request, id Identity) {
	orderID := r.PathValue("orderId")
	if orderID == "" || len(orderID) > 64 {
		writeFail(w, http.StatusBadRequest, "Mã đơn hàng không hợp lệ")
		return
	}
	ctx, now := r.Context(), h.now()
	view := shipmentView{OrderID: orderID, StepSeconds: h.cfg.ShipmentStep.Seconds(), Steps: make([]shipmentStep, len(shipmentSteps))}
	sum := hashOf(orderID)
	view.Carrier = carriers[int(sum)%len(carriers)]
	view.TrackingCode = "MOCK" + padNumber(sum%1000000) + padNumber((sum / 7) % 1000000)[:3]

	var start time.Time
	var paymentID string
	if found, err := getJSON(ctx, h.store, "payorder:"+id.ID+":"+orderID, &paymentID); err != nil {
		h.fail500(w, err)
		return
	} else if found {
		var p payment
		if ok, err := getJSON(ctx, h.store, "payment:"+paymentID, &p); err != nil {
			h.fail500(w, err)
			return
		} else if ok {
			switch p.status(now) {
			case "PENDING":
				view.Status = "WAITING_PAYMENT"
			case "FAILED", "CANCELLED":
				view.Status = "PAYMENT_FAILED"
			default:
				start = p.CreatedAt.Add(p.delay())
			}
		}
	}
	if view.Status == "" && start.IsZero() {
		first := now
		stored, err := h.store.SetNX(ctx, "shipstart:"+id.ID+":"+orderID, []byte(now.Format(time.RFC3339Nano)), ttl)
		if err != nil {
			h.fail500(w, err)
			return
		}
		if !stored {
			var raw string
			data, _, _ := h.store.Get(ctx, "shipstart:"+id.ID+":"+orderID)
			raw = string(data)
			if t, perr := time.Parse(time.RFC3339Nano, raw); perr == nil {
				first = t
			}
		}
		start = first
	}

	view.CurrentStep = -1
	for i, step := range shipmentSteps {
		s := shipmentStep{Key: step.Key, Label: step.Label}
		if view.Status == "" || (view.Status != "WAITING_PAYMENT" && view.Status != "PAYMENT_FAILED") {
			at := start.Add(time.Duration(i) * h.cfg.ShipmentStep)
			if !now.Before(at) {
				s.Done, s.At = true, &at
				view.CurrentStep = i
			}
		} else if i == 0 {
			s.Done = true
			view.CurrentStep = 0
		}
		view.Steps[i] = s
	}
	if view.Status == "" {
		view.Status = shipmentSteps[max(view.CurrentStep, 0)].Key
	}
	writeOK(w, http.StatusOK, view)
}

func padNumber(n uint32) string {
	s := "000000"
	digits := []byte(s)
	for i := len(digits) - 1; i >= 0; i-- {
		digits[i] = byte('0' + n%10)
		n /= 10
	}
	return string(digits)
}
