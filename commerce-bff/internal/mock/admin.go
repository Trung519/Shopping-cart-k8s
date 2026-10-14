package mock

import (
	"net/http"
	"time"
)

type settlementView struct {
	settlementFx
	PaidAt *time.Time `json:"paidAt,omitempty"`
}

func (h *Handler) settlementStatuses(r *http.Request) (map[string]time.Time, error) {
	paid := map[string]time.Time{}
	_, err := getJSON(r.Context(), h.store, "settled:all", &paid)
	return paid, err
}

func (h *Handler) adminFinance(w http.ResponseWriter, r *http.Request, _ Identity) {
	paid, err := h.settlementStatuses(r)
	if err != nil {
		h.fail500(w, err)
		return
	}
	var gross, commission, pending int64
	items := make([]settlementView, 0, len(h.fx.Settlements))
	for _, s := range h.fx.Settlements {
		view := settlementView{settlementFx: s}
		if at, ok := paid[s.ID]; ok {
			view.Status, view.PaidAt = "PAID", &at
		}
		gross += s.Gross
		commission += s.Commission
		if view.Status == "PENDING" {
			pending += s.Net
		}
		items = append(items, view)
	}
	writeOK(w, http.StatusOK, map[string]any{
		"totals":      map[string]int64{"gross": gross, "commission": commission, "pendingPayout": pending},
		"settlements": items,
	})
}

func (h *Handler) adminSettlementApprove(w http.ResponseWriter, r *http.Request, id Identity) {
	paid, err := h.settlementStatuses(r)
	if err != nil {
		h.fail500(w, err)
		return
	}
	for _, s := range h.fx.Settlements {
		if s.ID != r.PathValue("id") {
			continue
		}
		if _, done := paid[s.ID]; done || s.Status != "PENDING" {
			writeFail(w, http.StatusConflict, "Kỳ đối soát này đã được thanh toán")
			return
		}
		paid[s.ID] = h.now()
		if err := setJSON(r.Context(), h.store, "settled:all", paid); err != nil {
			h.fail500(w, err)
			return
		}
		h.audit(r.Context(), id, "SETTLEMENT_PAID", s.ID)
		at := paid[s.ID]
		writeOK(w, http.StatusOK, settlementView{settlementFx: settlementFx{ID: s.ID, Shop: s.Shop, Period: s.Period, Gross: s.Gross, Commission: s.Commission, Net: s.Net, Status: "PAID"}, PaidAt: &at})
		return
	}
	writeFail(w, http.StatusNotFound, "Không tìm thấy kỳ đối soát")
}

var categoryShare = []struct {
	Name   string
	Weight int
}{{"Máy tính & laptop", 34}, {"Điện thoại & phụ kiện", 27}, {"Thời trang", 21}, {"Sách & VPP", 11}, {"Nhà cửa", 7}}

// adminAnalytics is deterministic per day and range, so refreshing the page
// shows the same chart and the numbers only drift when the date changes.
func (h *Handler) adminAnalytics(w http.ResponseWriter, r *http.Request, _ Identity) {
	days := 7
	switch r.URL.Query().Get("range") {
	case "30d":
		days = 30
	case "90d":
		days = 90
	case "", "7d":
	default:
		writeFail(w, http.StatusBadRequest, "range chỉ nhận 7d, 30d hoặc 90d")
		return
	}
	now := h.now()
	type point struct {
		Date   string `json:"date"`
		GMV    int64  `json:"gmv"`
		Orders int    `json:"orders"`
	}
	series := make([]point, 0, days)
	var gmv int64
	var orders int
	for d := days - 1; d >= 0; d-- {
		day := now.AddDate(0, 0, -d).Format("2006-01-02")
		rng := dayRand("admin" + day)
		g := int64(38_000_000+rng.Intn(42_000_000)) / 1000 * 1000
		n := 60 + int(g/900_000)
		series = append(series, point{Date: day, GMV: g, Orders: n})
		gmv += g
		orders += n
	}
	visits := orders * 31
	funnel := []map[string]any{
		{"step": "Lượt truy cập", "value": visits},
		{"step": "Thêm vào giỏ", "value": visits * 14 / 100},
		{"step": "Bắt đầu thanh toán", "value": visits * 7 / 100},
		{"step": "Thanh toán thành công", "value": orders},
	}
	categories := make([]map[string]any, 0, len(categoryShare))
	for _, c := range categoryShare {
		categories = append(categories, map[string]any{"name": c.Name, "share": c.Weight, "gmv": gmv * int64(c.Weight) / 100})
	}
	writeOK(w, http.StatusOK, map[string]any{
		"range":      days,
		"kpis":       map[string]any{"gmv": gmv, "orders": orders, "aov": gmv / int64(orders), "conversion": float64(orders) / float64(visits), "newSellers": days / 7 * 3},
		"series":     series,
		"funnel":     funnel,
		"categories": categories,
	})
}
