package mock

import (
	"context"
	"encoding/json"
	"math/rand"
	"net/http"
	"sort"
	"strings"
	"time"
)

const payoutProcessing = 3 * time.Second

// ---- orders ------------------------------------------------------------------

type sellerOrderView struct {
	ID        string              `json:"id"`
	Buyer     string              `json:"buyer"`
	City      string              `json:"city"`
	Items     []sellerOrderItemFx `json:"items"`
	Total     int64               `json:"total"`
	Status    string              `json:"status"` // NEW, CONFIRMED, PACKED, SHIPPED, DELIVERED, CANCELLED
	CreatedAt time.Time           `json:"createdAt"`
}

func (h *Handler) sellerOrderViews(ctx context.Context, id Identity) ([]sellerOrderView, error) {
	overrides := map[string]string{}
	if _, err := getJSON(ctx, h.store, "sorders:"+id.ID, &overrides); err != nil {
		return nil, err
	}
	now := h.now()
	out := make([]sellerOrderView, 0, len(h.fx.SellerOrders))
	for _, fx := range h.fx.SellerOrders {
		view := sellerOrderView{ID: fx.ID, Buyer: fx.Buyer, City: fx.City, Items: fx.Items, Status: fx.Status, CreatedAt: now.Add(-time.Duration(fx.MinutesAgo) * time.Minute)}
		if s, ok := overrides[fx.ID]; ok {
			view.Status = s
		}
		for _, item := range fx.Items {
			view.Total += int64(item.Qty) * item.Price
		}
		out = append(out, view)
	}
	return out, nil
}

func (h *Handler) sellerOrders(w http.ResponseWriter, r *http.Request, id Identity) {
	orders, err := h.sellerOrderViews(r.Context(), id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	filter := strings.ToUpper(r.URL.Query().Get("status"))
	counts := map[string]int{"NEW": 0, "CONFIRMED": 0, "PACKED": 0, "SHIPPED": 0, "DELIVERED": 0, "CANCELLED": 0}
	items := []sellerOrderView{}
	for _, o := range orders {
		counts[o.Status]++
		if filter == "" || o.Status == filter {
			items = append(items, o)
		}
	}
	writeOK(w, http.StatusOK, map[string]any{"items": items, "counts": counts})
}

func (h *Handler) sellerOrderAction(w http.ResponseWriter, r *http.Request, id Identity) {
	var in struct {
		Action string `json:"action"`
	}
	if !decode(w, r, &in) {
		return
	}
	rules := map[string][]string{ // action -> allowed current states, then next state
		"confirm": {"NEW", "CONFIRMED"},
		"pack":    {"CONFIRMED", "PACKED"},
		"ship":    {"PACKED", "SHIPPED"},
		"cancel":  {"NEW,CONFIRMED", "CANCELLED"},
	}
	rule, ok := rules[strings.ToLower(in.Action)]
	if !ok {
		writeFail(w, http.StatusUnprocessableEntity, "Thao tác không hợp lệ")
		return
	}
	orders, err := h.sellerOrderViews(r.Context(), id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	for _, o := range orders {
		if o.ID != r.PathValue("id") {
			continue
		}
		if !strings.Contains(","+rule[0]+",", ","+o.Status+",") {
			writeFail(w, http.StatusConflict, "Trạng thái hiện tại không cho phép thao tác này")
			return
		}
		overrides := map[string]string{}
		_, _ = getJSON(r.Context(), h.store, "sorders:"+id.ID, &overrides)
		overrides[o.ID] = rule[1]
		if err := setJSON(r.Context(), h.store, "sorders:"+id.ID, overrides); err != nil {
			h.fail500(w, err)
			return
		}
		o.Status = rule[1]
		h.audit(r.Context(), id, "SELLER_ORDER_"+rule[1], o.ID)
		writeOK(w, http.StatusOK, o)
		return
	}
	writeFail(w, http.StatusNotFound, "Không tìm thấy đơn hàng")
}

// ---- inventory ------------------------------------------------------------------

type inventoryView struct {
	SKU          string `json:"sku"`
	Name         string `json:"name"`
	Stock        int    `json:"stock"`
	Reserved     int    `json:"reserved"`
	Available    int    `json:"available"`
	LowThreshold int    `json:"lowThreshold"`
	Low          bool   `json:"low"`
}

func (h *Handler) inventoryViews(ctx context.Context, id Identity) ([]inventoryView, error) {
	overrides := map[string]int{}
	if _, err := getJSON(ctx, h.store, "sinv:"+id.ID, &overrides); err != nil {
		return nil, err
	}
	out := make([]inventoryView, 0, len(h.fx.Inventory))
	for _, fx := range h.fx.Inventory {
		stock := fx.Stock
		if v, ok := overrides[fx.SKU]; ok {
			stock = v
		}
		out = append(out, inventoryView{SKU: fx.SKU, Name: fx.Name, Stock: stock, Reserved: fx.Reserved, Available: stock - fx.Reserved, LowThreshold: fx.LowThreshold, Low: stock <= fx.LowThreshold})
	}
	return out, nil
}

func (h *Handler) sellerInventory(w http.ResponseWriter, r *http.Request, id Identity) {
	items, err := h.inventoryViews(r.Context(), id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	writeOK(w, http.StatusOK, items)
}

func (h *Handler) sellerInventoryUpdate(w http.ResponseWriter, r *http.Request, id Identity) {
	var in struct {
		Stock int `json:"stock"`
	}
	if !decode(w, r, &in) {
		return
	}
	if in.Stock < 0 || in.Stock > 100000 {
		writeFail(w, http.StatusUnprocessableEntity, "Tồn kho phải từ 0 đến 100.000")
		return
	}
	known := false
	for _, fx := range h.fx.Inventory {
		known = known || fx.SKU == r.PathValue("sku")
	}
	if !known {
		writeFail(w, http.StatusNotFound, "Không tìm thấy SKU")
		return
	}
	overrides := map[string]int{}
	_, _ = getJSON(r.Context(), h.store, "sinv:"+id.ID, &overrides)
	overrides[r.PathValue("sku")] = in.Stock
	if err := setJSON(r.Context(), h.store, "sinv:"+id.ID, overrides); err != nil {
		h.fail500(w, err)
		return
	}
	items, err := h.inventoryViews(r.Context(), id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	h.audit(r.Context(), id, "INVENTORY_UPDATED", r.PathValue("sku"))
	writeOK(w, http.StatusOK, items)
}

// ---- promotions ------------------------------------------------------------------

func (h *Handler) loadPromotions(ctx context.Context, id Identity) ([]promotionFx, error) {
	var list []promotionFx
	found, err := getJSON(ctx, h.store, "sprom:"+id.ID, &list)
	if err != nil || found {
		return list, err
	}
	data, _ := json.Marshal(h.fx.Promotions)
	if _, err := h.store.SetNX(ctx, "sprom:"+id.ID, data, ttl); err != nil {
		return nil, err
	}
	_, err = getJSON(ctx, h.store, "sprom:"+id.ID, &list)
	return list, err
}

func (h *Handler) sellerPromotions(w http.ResponseWriter, r *http.Request, id Identity) {
	list, err := h.loadPromotions(r.Context(), id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	writeOK(w, http.StatusOK, list)
}

func (h *Handler) sellerPromotionCreate(w http.ResponseWriter, r *http.Request, id Identity) {
	var in promotionFx
	if !decode(w, r, &in) {
		return
	}
	in.Name = strings.TrimSpace(in.Name)
	if len([]rune(in.Name)) < 3 || len([]rune(in.Name)) > 60 {
		writeFail(w, http.StatusUnprocessableEntity, "Tên khuyến mãi cần từ 3 đến 60 ký tự")
		return
	}
	switch in.Kind {
	case "percent":
		if in.Value < 1 || in.Value > 90 {
			writeFail(w, http.StatusUnprocessableEntity, "Phần trăm giảm phải từ 1 đến 90")
			return
		}
	case "amount", "freeship":
		if in.Value < 1000 || in.Value > 10_000_000 {
			writeFail(w, http.StatusUnprocessableEntity, "Giá trị giảm không hợp lệ")
			return
		}
	default:
		writeFail(w, http.StatusUnprocessableEntity, "Loại khuyến mãi không hợp lệ")
		return
	}
	if in.MinSpend < 0 {
		writeFail(w, http.StatusUnprocessableEntity, "Đơn tối thiểu không hợp lệ")
		return
	}
	list, err := h.loadPromotions(r.Context(), id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	if len(list) >= 20 {
		writeFail(w, http.StatusUnprocessableEntity, "Tối đa 20 khuyến mãi")
		return
	}
	created := promotionFx{ID: newID("pr"), Name: in.Name, Kind: in.Kind, Value: in.Value, MinSpend: in.MinSpend, Status: "ACTIVE"}
	list = append([]promotionFx{created}, list...)
	if err := setJSON(r.Context(), h.store, "sprom:"+id.ID, list); err != nil {
		h.fail500(w, err)
		return
	}
	h.audit(r.Context(), id, "PROMOTION_CREATED", created.Name)
	writeOK(w, http.StatusCreated, created)
}

func (h *Handler) sellerPromotionToggle(w http.ResponseWriter, r *http.Request, id Identity) {
	list, err := h.loadPromotions(r.Context(), id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	for i := range list {
		if list[i].ID != r.PathValue("id") {
			continue
		}
		if list[i].Status == "ACTIVE" {
			list[i].Status = "PAUSED"
		} else {
			list[i].Status = "ACTIVE"
		}
		if err := setJSON(r.Context(), h.store, "sprom:"+id.ID, list); err != nil {
			h.fail500(w, err)
			return
		}
		writeOK(w, http.StatusOK, list[i])
		return
	}
	writeFail(w, http.StatusNotFound, "Không tìm thấy khuyến mãi")
}

// ---- messages ------------------------------------------------------------------

type chatMessage struct {
	From string    `json:"from"`
	Text string    `json:"text"`
	At   time.Time `json:"at"`
}

type threadView struct {
	ID       string        `json:"id"`
	Buyer    string        `json:"buyer"`
	Product  string        `json:"product"`
	Messages []chatMessage `json:"messages"`
	Unread   bool          `json:"unread"`
}

// canned buyer replies; a reply is stored with a future timestamp and simply
// stays hidden until the clock reaches it, which keeps this stateless.
var buyerReplies = []string{"Cảm ơn shop nhé!", "Mình hiểu rồi, để mình cân nhắc thêm.", "Ok shop, mình sẽ đặt hàng ngay."}

func (h *Handler) sellerMessages(w http.ResponseWriter, r *http.Request, id Identity) {
	extra := map[string][]chatMessage{}
	if _, err := getJSON(r.Context(), h.store, "sthreads:"+id.ID, &extra); err != nil {
		h.fail500(w, err)
		return
	}
	now := h.now()
	out := make([]threadView, 0, len(h.fx.Threads))
	for _, fx := range h.fx.Threads {
		view := threadView{ID: fx.ID, Buyer: fx.Buyer, Product: fx.Product}
		for _, m := range fx.Messages {
			view.Messages = append(view.Messages, chatMessage{From: m.From, Text: m.Text, At: now.Add(-time.Duration(m.MinutesAgo) * time.Minute)})
		}
		for _, m := range extra[fx.ID] {
			if !m.At.After(now) {
				view.Messages = append(view.Messages, m)
			}
		}
		sort.SliceStable(view.Messages, func(i, j int) bool { return view.Messages[i].At.Before(view.Messages[j].At) })
		view.Unread = len(view.Messages) > 0 && view.Messages[len(view.Messages)-1].From == "buyer"
		out = append(out, view)
	}
	writeOK(w, http.StatusOK, out)
}

func (h *Handler) sellerMessageReply(w http.ResponseWriter, r *http.Request, id Identity) {
	var in struct {
		Text string `json:"text"`
	}
	if !decode(w, r, &in) {
		return
	}
	text := strings.TrimSpace(in.Text)
	if text == "" || len([]rune(text)) > 500 {
		writeFail(w, http.StatusUnprocessableEntity, "Tin nhắn cần từ 1 đến 500 ký tự")
		return
	}
	threadID := r.PathValue("id")
	known := false
	for _, fx := range h.fx.Threads {
		known = known || fx.ID == threadID
	}
	if !known {
		writeFail(w, http.StatusNotFound, "Không tìm thấy cuộc trò chuyện")
		return
	}
	extra := map[string][]chatMessage{}
	_, _ = getJSON(r.Context(), h.store, "sthreads:"+id.ID, &extra)
	now := h.now()
	reply := buyerReplies[int(hashOf(text))%len(buyerReplies)]
	extra[threadID] = append(extra[threadID], chatMessage{From: "seller", Text: text, At: now}, chatMessage{From: "buyer", Text: reply, At: now.Add(3 * time.Second)})
	if err := setJSON(r.Context(), h.store, "sthreads:"+id.ID, extra); err != nil {
		h.fail500(w, err)
		return
	}
	writeOK(w, http.StatusCreated, chatMessage{From: "seller", Text: text, At: now})
}

// ---- finance ------------------------------------------------------------------

type payoutRec struct {
	ID        string    `json:"id"`
	Amount    int64     `json:"amount"`
	Status    string    `json:"status"`
	CreatedAt time.Time `json:"createdAt"`
}

func (p payoutRec) withStatus(now time.Time) payoutRec {
	if p.Status == "PROCESSING" && now.Sub(p.CreatedAt) >= payoutProcessing {
		p.Status = "COMPLETED"
	}
	return p
}

func (h *Handler) sellerPayouts(ctx context.Context, id Identity) ([]payoutRec, error) {
	var mine []payoutRec
	if _, err := getJSON(ctx, h.store, "spayouts:"+id.ID, &mine); err != nil {
		return nil, err
	}
	now := h.now()
	out := []payoutRec{}
	for _, p := range mine {
		out = append(out, p.withStatus(now))
	}
	for _, seed := range h.fx.Finance.SeedPayouts {
		out = append(out, payoutRec{ID: seed.ID, Amount: seed.Amount, Status: seed.Status, CreatedAt: now.AddDate(0, 0, -seed.DaysAgo)})
	}
	sort.SliceStable(out, func(i, j int) bool { return out[i].CreatedAt.After(out[j].CreatedAt) })
	return out, nil
}

func (h *Handler) availableBalance(payouts []payoutRec) int64 {
	available := h.fx.Finance.AvailableBalance
	for _, p := range payouts {
		if !strings.HasPrefix(p.ID, "PO-") { // seeded payouts are already deducted from the fixture
			available -= p.Amount
		}
	}
	return available
}

func (h *Handler) sellerFinance(w http.ResponseWriter, r *http.Request, id Identity) {
	payouts, err := h.sellerPayouts(r.Context(), id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	now := h.now()
	txs := make([]map[string]any, 0, len(h.fx.Finance.Transactions))
	for _, tx := range h.fx.Finance.Transactions {
		txs = append(txs, map[string]any{"id": tx.ID, "type": tx.Type, "ref": tx.Ref, "amount": tx.Amount, "at": now.AddDate(0, 0, -tx.DaysAgo)})
	}
	writeOK(w, http.StatusOK, map[string]any{
		"availableBalance": h.availableBalance(payouts),
		"pendingBalance":   h.fx.Finance.PendingBalance,
		"commissionRate":   h.fx.Finance.CommissionRate,
		"transactions":     txs,
		"payouts":          payouts,
	})
}

func (h *Handler) sellerPayout(w http.ResponseWriter, r *http.Request, id Identity) {
	var in struct {
		Amount int64 `json:"amount"`
	}
	if !decode(w, r, &in) {
		return
	}
	payouts, err := h.sellerPayouts(r.Context(), id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	if in.Amount < 100000 {
		writeFail(w, http.StatusUnprocessableEntity, "Số tiền rút tối thiểu là 100.000₫")
		return
	}
	if in.Amount > h.availableBalance(payouts) {
		writeFail(w, http.StatusUnprocessableEntity, "Số tiền rút vượt quá số dư khả dụng")
		return
	}
	var mine []payoutRec
	_, _ = getJSON(r.Context(), h.store, "spayouts:"+id.ID, &mine)
	if len(mine) >= 20 {
		writeFail(w, http.StatusUnprocessableEntity, "Đã đạt số lệnh rút tối đa trong ngày")
		return
	}
	rec := payoutRec{ID: newID("po"), Amount: in.Amount, Status: "PROCESSING", CreatedAt: h.now()}
	mine = append(mine, rec)
	if err := setJSON(r.Context(), h.store, "spayouts:"+id.ID, mine); err != nil {
		h.fail500(w, err)
		return
	}
	h.audit(r.Context(), id, "PAYOUT_REQUESTED", rec.ID)
	writeOK(w, http.StatusAccepted, rec)
}

// ---- settings ------------------------------------------------------------------

type sellerSettings struct {
	ShopName       string `json:"shopName"`
	Description    string `json:"description"`
	Phone          string `json:"phone"`
	ReturnDays     int    `json:"returnDays"`
	VacationMode   bool   `json:"vacationMode"`
	NotifyOrders   bool   `json:"notifyOrders"`
	NotifyMessages bool   `json:"notifyMessages"`
}

func defaultSettings() sellerSettings {
	return sellerSettings{ShopName: "Cửa hàng của tôi", Description: "Chuyên phụ kiện công nghệ chính hãng.", Phone: "0900 000 000", ReturnDays: 7, NotifyOrders: true, NotifyMessages: true}
}

func (h *Handler) sellerSettingsGet(w http.ResponseWriter, r *http.Request, id Identity) {
	s := defaultSettings()
	if _, err := getJSON(r.Context(), h.store, "ssettings:"+id.ID, &s); err != nil {
		h.fail500(w, err)
		return
	}
	writeOK(w, http.StatusOK, s)
}

func (h *Handler) sellerSettingsPut(w http.ResponseWriter, r *http.Request, id Identity) {
	var in sellerSettings
	if !decode(w, r, &in) {
		return
	}
	in.ShopName, in.Description = strings.TrimSpace(in.ShopName), strings.TrimSpace(in.Description)
	switch {
	case len([]rune(in.ShopName)) < 2 || len([]rune(in.ShopName)) > 60:
		writeFail(w, http.StatusUnprocessableEntity, "Tên shop cần từ 2 đến 60 ký tự")
		return
	case len([]rune(in.Description)) > 300:
		writeFail(w, http.StatusUnprocessableEntity, "Mô tả tối đa 300 ký tự")
		return
	case in.Phone != "" && !phonePattern.MatchString(in.Phone):
		writeFail(w, http.StatusUnprocessableEntity, "Số điện thoại không hợp lệ")
		return
	case in.ReturnDays < 0 || in.ReturnDays > 30:
		writeFail(w, http.StatusUnprocessableEntity, "Thời gian đổi trả từ 0 đến 30 ngày")
		return
	}
	if err := setJSON(r.Context(), h.store, "ssettings:"+id.ID, in); err != nil {
		h.fail500(w, err)
		return
	}
	h.audit(r.Context(), id, "SHOP_SETTINGS_UPDATED", in.ShopName)
	writeOK(w, http.StatusOK, in)
}

// ---- dashboard ------------------------------------------------------------------

func dayRand(seed string) *rand.Rand { return rand.New(rand.NewSource(int64(hashOf(seed)))) }

func (h *Handler) sellerDashboard(w http.ResponseWriter, r *http.Request, id Identity) {
	orders, err := h.sellerOrderViews(r.Context(), id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	inventory, err := h.inventoryViews(r.Context(), id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	returns, err := h.loadReturns(r.Context())
	if err != nil {
		h.fail500(w, err)
		return
	}
	now := h.now()
	type point struct {
		Date    string `json:"date"`
		Revenue int64  `json:"revenue"`
		Orders  int    `json:"orders"`
	}
	series := make([]point, 0, 7)
	var revenue int64
	var orderCount int
	for d := 6; d >= 0; d-- {
		day := now.AddDate(0, 0, -d).Format("2006-01-02")
		rng := dayRand(id.ID + day)
		rev := int64(1_200_000+rng.Intn(2_600_000)) / 1000 * 1000
		n := 2 + int(rev/700_000)
		series = append(series, point{Date: day, Revenue: rev, Orders: n})
		revenue += rev
		orderCount += n
	}
	views := orderCount * 38
	newOrders, lowStock, openReturns := 0, 0, 0
	for _, o := range orders {
		if o.Status == "NEW" {
			newOrders++
		}
	}
	for _, i := range inventory {
		if i.Low {
			lowStock++
		}
	}
	for _, rec := range returns {
		if rec.Status == "REQUESTED" {
			openReturns++
		}
	}
	top := map[string]*struct {
		Name    string `json:"name"`
		Sold    int    `json:"sold"`
		Revenue int64  `json:"revenue"`
	}{}
	for _, o := range orders {
		for _, item := range o.Items {
			entry := top[item.Name]
			if entry == nil {
				entry = &struct {
					Name    string `json:"name"`
					Sold    int    `json:"sold"`
					Revenue int64  `json:"revenue"`
				}{Name: item.Name}
				top[item.Name] = entry
			}
			entry.Sold += item.Qty
			entry.Revenue += int64(item.Qty) * item.Price
		}
	}
	topList := make([]any, 0, len(top))
	names := make([]string, 0, len(top))
	for name := range top {
		names = append(names, name)
	}
	sort.Slice(names, func(i, j int) bool {
		if top[names[i]].Revenue != top[names[j]].Revenue {
			return top[names[i]].Revenue > top[names[j]].Revenue
		}
		return names[i] < names[j]
	})
	for _, name := range names[:min(5, len(names))] {
		topList = append(topList, top[name])
	}
	writeOK(w, http.StatusOK, map[string]any{
		"kpis":        map[string]any{"revenue7d": revenue, "orders7d": orderCount, "views7d": views, "conversion": float64(orderCount) / float64(views), "rating": 4.8},
		"series":      series,
		"todo":        map[string]int{"newOrders": newOrders, "lowStock": lowStock, "openReturns": openReturns},
		"topProducts": topList,
	})
}
