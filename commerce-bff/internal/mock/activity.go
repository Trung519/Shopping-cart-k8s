package mock

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"strings"
	"time"
)

// ---- returns (buyer creates, admin reviews) --------------------------------

type returnRec struct {
	ID        string    `json:"id"`
	UserID    string    `json:"userId"`
	OrderRef  string    `json:"orderRef"`
	Buyer     string    `json:"buyer"`
	Shop      string    `json:"shop"`
	Reason    string    `json:"reason"`
	Note      string    `json:"note"`
	Amount    int64     `json:"amount"`
	Status    string    `json:"status"` // REQUESTED, APPROVED, REJECTED, REFUNDED
	CreatedAt time.Time `json:"createdAt"`
	UpdatedAt time.Time `json:"updatedAt"`
}

var returnReasons = map[string]bool{"DEFECTIVE": true, "NOT_AS_DESCRIBED": true, "WRONG_ITEM": true, "CHANGED_MIND": true}

// loadReturns seeds the shared list from fixtures the first time it is read so
// the admin queue is never empty on a fresh Redis.
func (h *Handler) loadReturns(ctx context.Context) ([]returnRec, error) {
	var list []returnRec
	found, err := getJSON(ctx, h.store, "returns:all", &list)
	if err != nil || found {
		return list, err
	}
	now := h.now()
	for _, fx := range h.fx.Returns {
		at := now.AddDate(0, 0, -fx.DaysAgo)
		list = append(list, returnRec{ID: fx.ID, UserID: fx.UserID, OrderRef: fx.OrderRef, Buyer: fx.Buyer, Shop: fx.Shop, Reason: fx.Reason, Note: fx.Note, Amount: fx.Amount, Status: fx.Status, CreatedAt: at, UpdatedAt: at})
	}
	data, _ := json.Marshal(list)
	if _, err := h.store.SetNX(ctx, "returns:all", data, ttl); err != nil {
		return nil, err
	}
	_, err = getJSON(ctx, h.store, "returns:all", &list)
	return list, err
}

func (h *Handler) listReturns(w http.ResponseWriter, r *http.Request, id Identity) {
	all, err := h.loadReturns(r.Context())
	if err != nil {
		h.fail500(w, err)
		return
	}
	mine := []returnRec{}
	for _, rec := range all {
		if rec.UserID == id.ID {
			mine = append(mine, rec)
		}
	}
	writeOK(w, http.StatusOK, mine)
}

func (h *Handler) createReturn(w http.ResponseWriter, r *http.Request, id Identity) {
	var in struct {
		OrderID string `json:"orderId"`
		Reason  string `json:"reason"`
		Note    string `json:"note"`
		Amount  int64  `json:"amount"`
	}
	if !decode(w, r, &in) {
		return
	}
	in.Reason = strings.ToUpper(strings.TrimSpace(in.Reason))
	if strings.TrimSpace(in.OrderID) == "" || len(in.OrderID) > 64 {
		writeFail(w, http.StatusUnprocessableEntity, "Thiếu mã đơn hàng")
		return
	}
	if !returnReasons[in.Reason] {
		writeFail(w, http.StatusUnprocessableEntity, "Lý do đổi trả không hợp lệ")
		return
	}
	if len([]rune(in.Note)) > 500 || in.Amount < 0 {
		writeFail(w, http.StatusUnprocessableEntity, "Ghi chú hoặc số tiền không hợp lệ")
		return
	}
	all, err := h.loadReturns(r.Context())
	if err != nil {
		h.fail500(w, err)
		return
	}
	for _, rec := range all {
		if rec.UserID == id.ID && rec.OrderRef == in.OrderID && rec.Status != "REJECTED" {
			writeFail(w, http.StatusConflict, "Đơn hàng này đã có yêu cầu đổi trả")
			return
		}
	}
	now := h.now()
	buyer := id.Name
	if buyer == "" {
		buyer = "Người mua"
	}
	rec := returnRec{ID: newID("rt"), UserID: id.ID, OrderRef: in.OrderID, Buyer: buyer, Shop: "Cửa hàng đối tác", Reason: in.Reason, Note: strings.TrimSpace(in.Note), Amount: in.Amount, Status: "REQUESTED", CreatedAt: now, UpdatedAt: now}
	all = append([]returnRec{rec}, all...)
	if err := setJSON(r.Context(), h.store, "returns:all", all); err != nil {
		h.fail500(w, err)
		return
	}
	h.audit(r.Context(), id, "RETURN_REQUESTED", in.OrderID)
	writeOK(w, http.StatusCreated, rec)
}

func (h *Handler) adminReturns(w http.ResponseWriter, r *http.Request, _ Identity) {
	all, err := h.loadReturns(r.Context())
	if err != nil {
		h.fail500(w, err)
		return
	}
	status := strings.ToUpper(r.URL.Query().Get("status"))
	counts := map[string]int{"REQUESTED": 0, "APPROVED": 0, "REJECTED": 0, "REFUNDED": 0}
	items := []returnRec{}
	for _, rec := range all {
		counts[rec.Status]++
		if status == "" || rec.Status == status {
			items = append(items, rec)
		}
	}
	writeOK(w, http.StatusOK, map[string]any{"items": items, "counts": counts})
}

func (h *Handler) adminReturnAction(w http.ResponseWriter, r *http.Request, id Identity) {
	var in struct {
		Action string `json:"action"`
	}
	if !decode(w, r, &in) {
		return
	}
	next := map[string]struct{ from, to string }{
		"approve": {"REQUESTED", "APPROVED"},
		"reject":  {"REQUESTED", "REJECTED"},
		"refund":  {"APPROVED", "REFUNDED"},
	}
	rule, ok := next[strings.ToLower(in.Action)]
	if !ok {
		writeFail(w, http.StatusUnprocessableEntity, "Thao tác không hợp lệ")
		return
	}
	all, err := h.loadReturns(r.Context())
	if err != nil {
		h.fail500(w, err)
		return
	}
	for i := range all {
		if all[i].ID != r.PathValue("id") {
			continue
		}
		if all[i].Status != rule.from {
			writeFail(w, http.StatusConflict, "Trạng thái hiện tại không cho phép thao tác này")
			return
		}
		all[i].Status, all[i].UpdatedAt = rule.to, h.now()
		if err := setJSON(r.Context(), h.store, "returns:all", all); err != nil {
			h.fail500(w, err)
			return
		}
		h.audit(r.Context(), id, "RETURN_"+rule.to, all[i].ID)
		writeOK(w, http.StatusOK, all[i])
		return
	}
	writeFail(w, http.StatusNotFound, "Không tìm thấy yêu cầu đổi trả")
}

// ---- audit log --------------------------------------------------------------

type auditEntry struct {
	ID     string    `json:"id"`
	Actor  string    `json:"actor"`
	Action string    `json:"action"`
	Target string    `json:"target"`
	At     time.Time `json:"at"`
}

// audit records a mock mutation so the admin audit page shows real activity.
func (h *Handler) audit(ctx context.Context, id Identity, action, target string) {
	actor := id.Name
	if actor == "" {
		actor = id.ID
	}
	var list []auditEntry
	_, _ = getJSON(ctx, h.store, "audit:all", &list)
	list = append([]auditEntry{{ID: newID("au"), Actor: actor, Action: action, Target: target, At: h.now()}}, list...)
	if len(list) > 200 {
		list = list[:200]
	}
	_ = setJSON(ctx, h.store, "audit:all", list)
}

func (h *Handler) adminAudit(w http.ResponseWriter, r *http.Request, _ Identity) {
	var list []auditEntry
	if _, err := getJSON(r.Context(), h.store, "audit:all", &list); err != nil {
		h.fail500(w, err)
		return
	}
	now := h.now()
	for i, fx := range h.fx.Audit {
		list = append(list, auditEntry{ID: fmt.Sprintf("seed-%d", i), Actor: fx.Actor, Action: fx.Action, Target: fx.Target, At: now.Add(-time.Duration(fx.MinutesAgo) * time.Minute)})
	}
	sort.SliceStable(list, func(i, j int) bool { return list[i].At.After(list[j].At) })
	q := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("q")))
	out := make([]auditEntry, 0, len(list))
	for _, e := range list {
		if q == "" || strings.Contains(strings.ToLower(e.Actor+" "+e.Action+" "+e.Target), q) {
			out = append(out, e)
		}
		if len(out) == 100 {
			break
		}
	}
	writeOK(w, http.StatusOK, out)
}

// ---- notifications ------------------------------------------------------------

type notificationView struct {
	ID     string    `json:"id"`
	Type   string    `json:"type"`
	Title  string    `json:"title"`
	Text   string    `json:"text"`
	At     time.Time `json:"at"`
	Unread bool      `json:"unread"`
}

var methodNames = map[string]string{"momo": "MoMo", "vnpay": "VNPay", "zalopay": "ZaloPay", "cod": "COD"}

func (h *Handler) listNotifications(w http.ResponseWriter, r *http.Request, id Identity) {
	ctx, now := r.Context(), h.now()
	var lastRead time.Time
	_, _ = getJSON(ctx, h.store, "notifread:"+id.ID, &lastRead)

	items := make([]notificationView, 0, len(h.fx.Notifications)+8)
	for i, fx := range h.fx.Notifications {
		items = append(items, notificationView{ID: fmt.Sprintf("seed-%d", i), Type: fx.Type, Title: fx.Title, Text: fx.Text, At: now.Add(-time.Duration(fx.MinutesAgo) * time.Minute)})
	}
	var paymentIDs []string
	if _, err := getJSON(ctx, h.store, "payments:"+id.ID, &paymentIDs); err != nil {
		h.fail500(w, err)
		return
	}
	for _, pid := range paymentIDs {
		var p payment
		if ok, _ := getJSON(ctx, h.store, "payment:"+pid, &p); !ok {
			continue
		}
		name := methodNames[p.Method]
		switch p.status(now) {
		case "SUCCESS":
			items = append(items, notificationView{ID: "pay-" + p.ID, Type: "order", Title: "Thanh toán " + name + " thành công", Text: "Đơn " + p.OrderID + " đã được ghi nhận thanh toán.", At: p.CreatedAt.Add(p.delay())})
		case "FAILED":
			items = append(items, notificationView{ID: "pay-" + p.ID, Type: "order", Title: "Thanh toán " + name + " thất bại", Text: "Đơn " + p.OrderID + " chưa được thanh toán, bạn có thể thử lại.", At: p.CreatedAt.Add(p.delay())})
		}
	}
	unread := 0
	for i := range items {
		items[i].Unread = items[i].At.After(lastRead)
		if items[i].Unread {
			unread++
		}
	}
	sort.SliceStable(items, func(i, j int) bool { return items[i].At.After(items[j].At) })
	writeOK(w, http.StatusOK, map[string]any{"items": items, "unread": unread})
}

func (h *Handler) readNotifications(w http.ResponseWriter, r *http.Request, id Identity) {
	if err := setJSON(r.Context(), h.store, "notifread:"+id.ID, h.now()); err != nil {
		h.fail500(w, err)
		return
	}
	writeOK(w, http.StatusOK, map[string]any{"unread": 0})
}

// events pushes a fixture notification every EventInterval over Server-Sent
// Events. It closes itself after five minutes so idle tabs cannot pile up
// long-lived connections on a small lab cluster; EventSource reconnects.
func (h *Handler) events(w http.ResponseWriter, r *http.Request, _ Identity) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		writeFail(w, http.StatusInternalServerError, "Máy chủ không hỗ trợ SSE")
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(http.StatusOK)
	_, _ = fmt.Fprint(w, "retry: 5000\n: connected\n\n")
	flusher.Flush()

	events := time.NewTicker(h.cfg.EventInterval)
	heartbeat := time.NewTicker(15 * time.Second)
	limit := time.NewTimer(5 * time.Minute)
	defer events.Stop()
	defer heartbeat.Stop()
	defer limit.Stop()
	for sent := 0; ; {
		select {
		case <-r.Context().Done():
			return
		case <-limit.C:
			return
		case <-heartbeat.C:
			_, _ = fmt.Fprint(w, ": ping\n\n")
		case <-events.C:
			fx := h.fx.LiveEvents[sent%len(h.fx.LiveEvents)]
			sent++
			payload, _ := json.Marshal(notificationView{ID: newID("ev"), Type: fx.Type, Title: fx.Title, Text: fx.Text, At: h.now(), Unread: true})
			_, _ = fmt.Fprintf(w, "event: notification\ndata: %s\n\n", payload)
		}
		flusher.Flush()
	}
}
