package mock

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"strconv"
	"strings"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

var qrMethods = map[string]bool{"momo": true, "vnpay": true, "zalopay": true}

type payment struct {
	ID          string    `json:"id"`
	UserID      string    `json:"userId"`
	OrderID     string    `json:"orderId"`
	Method      string    `json:"method"`
	Amount      int64     `json:"amount"`
	Outcome     string    `json:"outcome"` // SUCCESS or FAILED, decided at creation
	DelayMillis int64     `json:"delayMillis"`
	CreatedAt   time.Time `json:"createdAt"`
	Cancelled   bool      `json:"cancelled"`
	TraceID     string    `json:"traceId,omitempty"`
	SpanID      string    `json:"spanId,omitempty"`
}

type paymentView struct {
	ID               string     `json:"id"`
	OrderID          string     `json:"orderId"`
	Method           string     `json:"method"`
	Amount           int64      `json:"amount"`
	Status           string     `json:"status"` // PENDING, SUCCESS, FAILED, CANCELLED
	RemainingSeconds int        `json:"remainingSeconds"`
	ExpiresInSeconds float64    `json:"expiresInSeconds"`
	CreatedAt        time.Time  `json:"createdAt"`
	PaidAt           *time.Time `json:"paidAt,omitempty"`
	QR               *qrCode    `json:"qr,omitempty"`
}

type qrCode struct {
	Payload string   `json:"payload"`
	Matrix  []string `json:"matrix"`
	Notice  string   `json:"notice"`
}

func (p payment) delay() time.Duration { return time.Duration(p.DelayMillis) * time.Millisecond }

// status derives the state from the clock, so no timer or goroutine is needed
// and every replica agrees on the answer.
func (p payment) status(now time.Time) string {
	switch {
	case p.Cancelled:
		return "CANCELLED"
	case now.Sub(p.CreatedAt) >= p.delay():
		return p.Outcome
	default:
		return "PENDING"
	}
}

func (p payment) view(now time.Time) paymentView {
	status := p.status(now)
	v := paymentView{ID: p.ID, OrderID: p.OrderID, Method: p.Method, Amount: p.Amount, Status: status, CreatedAt: p.CreatedAt, ExpiresInSeconds: p.delay().Seconds()}
	if status == "PENDING" {
		v.RemainingSeconds = ceilSeconds(p.delay() - now.Sub(p.CreatedAt))
	}
	if status == "SUCCESS" {
		paidAt := p.CreatedAt.Add(p.delay())
		v.PaidAt = &paidAt
	}
	if qrMethods[p.Method] {
		v.QR = makeQR(p)
	}
	return v
}

func (h *Handler) createPayment(w http.ResponseWriter, r *http.Request, id Identity) {
	var in struct {
		OrderID string `json:"orderId"`
		Method  string `json:"method"`
		Amount  int64  `json:"amount"`
		Outcome string `json:"outcome"`
	}
	if !decode(w, r, &in) {
		return
	}
	in.Method = strings.ToLower(strings.TrimSpace(in.Method))
	if !qrMethods[in.Method] && in.Method != "cod" {
		writeFail(w, http.StatusUnprocessableEntity, "Phương thức thanh toán không được hỗ trợ")
		return
	}
	if strings.TrimSpace(in.OrderID) == "" || len(in.OrderID) > 64 {
		writeFail(w, http.StatusUnprocessableEntity, "Thiếu mã đơn hàng")
		return
	}
	if in.Amount <= 0 {
		writeFail(w, http.StatusUnprocessableEntity, "Số tiền phải lớn hơn 0")
		return
	}
	q := r.URL.Query()
	outcome := "SUCCESS"
	if strings.EqualFold(in.Outcome, "fail") || strings.EqualFold(q.Get("outcome"), "fail") {
		outcome = "FAILED"
	}
	delay := h.cfg.PaymentDelay
	if raw := q.Get("payDelay"); raw != "" {
		if seconds, err := strconv.ParseFloat(raw, 64); err == nil && seconds >= 0 && seconds <= 60 {
			delay = time.Duration(seconds * float64(time.Second))
		}
	}
	if in.Method == "cod" {
		delay, outcome = 0, "SUCCESS" // cash on delivery needs no QR step
	}
	p := payment{ID: newID("mpay"), UserID: id.ID, OrderID: in.OrderID, Method: in.Method, Amount: in.Amount, Outcome: outcome, DelayMillis: delay.Milliseconds(), CreatedAt: h.now()}
	if sc := trace.SpanContextFromContext(r.Context()); sc.IsValid() {
		p.TraceID, p.SpanID = sc.TraceID().String(), sc.SpanID().String()
	}
	ctx := r.Context()
	if err := setJSON(ctx, h.store, "payment:"+p.ID, p); err != nil {
		h.fail500(w, err)
		return
	}
	if err := setJSON(ctx, h.store, "payorder:"+id.ID+":"+p.OrderID, p.ID); err != nil {
		h.fail500(w, err)
		return
	}
	var mine []string
	_, _ = getJSON(ctx, h.store, "payments:"+id.ID, &mine)
	mine = append(mine, p.ID)
	if len(mine) > 50 {
		mine = mine[len(mine)-50:]
	}
	if err := setJSON(ctx, h.store, "payments:"+id.ID, mine); err != nil {
		h.fail500(w, err)
		return
	}
	status := http.StatusAccepted
	if in.Method == "cod" {
		status = http.StatusCreated
	}
	writeOK(w, status, p.view(h.now()))
}

func (h *Handler) loadPayment(r *http.Request, id Identity, paymentID string) (payment, bool, error) {
	var p payment
	found, err := getJSON(r.Context(), h.store, "payment:"+paymentID, &p)
	if err != nil || !found || p.UserID != id.ID {
		return payment{}, false, err
	}
	return p, true, nil
}

func (h *Handler) getPayment(w http.ResponseWriter, r *http.Request, id Identity) {
	p, found, err := h.loadPayment(r, id, r.PathValue("id"))
	if err != nil {
		h.fail500(w, err)
		return
	}
	if !found {
		writeFail(w, http.StatusNotFound, "Không tìm thấy giao dịch")
		return
	}
	view := p.view(h.now())
	if view.Status == "SUCCESS" || view.Status == "FAILED" {
		h.emitCallbackSpan(r.Context(), p, view.Status)
	}
	writeOK(w, http.StatusOK, view)
}

func (h *Handler) cancelPayment(w http.ResponseWriter, r *http.Request, id Identity) {
	p, found, err := h.loadPayment(r, id, r.PathValue("id"))
	if err != nil {
		h.fail500(w, err)
		return
	}
	if !found {
		writeFail(w, http.StatusNotFound, "Không tìm thấy giao dịch")
		return
	}
	if p.status(h.now()) != "PENDING" {
		writeFail(w, http.StatusConflict, "Giao dịch đã kết thúc, không thể huỷ")
		return
	}
	p.Cancelled = true
	if err := setJSON(r.Context(), h.store, "payment:"+p.ID, p); err != nil {
		h.fail500(w, err)
		return
	}
	writeOK(w, http.StatusOK, p.view(h.now()))
}

// emitCallbackSpan plays the part of the wallet provider's webhook: once, when
// the payment first reads as finished, it records a span linked back to the
// trace of the request that created the payment.
func (h *Handler) emitCallbackSpan(ctx context.Context, p payment, status string) {
	if p.TraceID == "" {
		return
	}
	first, err := h.store.SetNX(ctx, "callback:"+p.ID, []byte("1"), ttl)
	if err != nil || !first {
		return
	}
	traceID, errT := trace.TraceIDFromHex(p.TraceID)
	spanID, errS := trace.SpanIDFromHex(p.SpanID)
	if errT != nil || errS != nil {
		return
	}
	origin := trace.NewSpanContext(trace.SpanContextConfig{TraceID: traceID, SpanID: spanID, TraceFlags: trace.FlagsSampled, Remote: true})
	_, span := otel.Tracer("shopping/mock").Start(ctx, "mock.payment.callback",
		trace.WithLinks(trace.Link{SpanContext: origin}),
		trace.WithAttributes(attribute.Bool("mock", true), attribute.String("mock.scenario", "payments"), attribute.String("payment.method", p.Method), attribute.String("payment.status", status)))
	span.End()
}

// makeQR returns a 25x25 matrix with real-looking finder patterns and a
// deterministic fill. It is decoration only: it does not decode to anything.
func makeQR(p payment) *qrCode {
	const size = 25
	grid := make([][]byte, size)
	sum := sha256.Sum256([]byte(p.ID + p.Method))
	stream := hex.EncodeToString(sum[:]) + hex.EncodeToString(sum[:])
	for y := range grid {
		grid[y] = make([]byte, size)
		for x := range grid[y] {
			bit := (hashOf(stream) >> uint((x*7+y*3)%24)) & 1
			if stream[(y*size+x)%len(stream)]%2 == 0 {
				bit ^= 1
			}
			grid[y][x] = byte('0' + bit)
		}
	}
	finder := func(ox, oy int) {
		for y := -1; y <= 7; y++ {
			for x := -1; x <= 7; x++ {
				gx, gy := ox+x, oy+y
				if gx < 0 || gy < 0 || gx >= size || gy >= size {
					continue
				}
				ring := x == 0 || x == 6 || y == 0 || y == 6
				core := x >= 2 && x <= 4 && y >= 2 && y <= 4
				if x >= 0 && x <= 6 && y >= 0 && y <= 6 && (ring || core) {
					grid[gy][gx] = '1'
				} else {
					grid[gy][gx] = '0'
				}
			}
		}
	}
	finder(0, 0)
	finder(size-7, 0)
	finder(0, size-7)
	rows := make([]string, size)
	for i := range grid {
		rows[i] = string(grid[i])
	}
	return &qrCode{
		Payload: "MOCK|" + strings.ToUpper(p.Method) + "|" + p.ID + "|" + strconv.FormatInt(p.Amount, 10),
		Matrix:  rows,
		Notice:  "Mã QR giả lập, không quét được",
	}
}
