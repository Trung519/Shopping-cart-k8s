package mock

import (
	"net/http"
	"regexp"
	"sort"
	"strings"
	"time"
)

var phonePattern = regexp.MustCompile(`^[0-9+ ]{9,15}$`)

// ---- addresses ------------------------------------------------------------

type address struct {
	ID        string `json:"id"`
	FullName  string `json:"fullName"`
	Phone     string `json:"phone"`
	Province  string `json:"province"`
	District  string `json:"district"`
	Ward      string `json:"ward"`
	Street    string `json:"street"`
	IsDefault bool   `json:"isDefault"`
}

type addressInput struct {
	FullName  string `json:"fullName"`
	Phone     string `json:"phone"`
	Province  string `json:"province"`
	District  string `json:"district"`
	Ward      string `json:"ward"`
	Street    string `json:"street"`
	IsDefault bool   `json:"isDefault"`
}

func (in addressInput) validate() string {
	for _, field := range []struct{ name, value string }{{"Họ và tên", in.FullName}, {"Tỉnh / thành phố", in.Province}, {"Quận / huyện", in.District}, {"Phường / xã", in.Ward}, {"Địa chỉ cụ thể", in.Street}} {
		if strings.TrimSpace(field.value) == "" || len(field.value) > 120 {
			return field.name + " không hợp lệ"
		}
	}
	if !phonePattern.MatchString(in.Phone) {
		return "Số điện thoại không hợp lệ"
	}
	return ""
}

func (h *Handler) loadAddresses(r *http.Request, id Identity) ([]address, error) {
	var list []address
	_, err := getJSON(r.Context(), h.store, "addresses:"+id.ID, &list)
	if list == nil {
		list = []address{}
	}
	return list, err
}

func (h *Handler) saveAddresses(r *http.Request, id Identity, list []address) error {
	return setJSON(r.Context(), h.store, "addresses:"+id.ID, list)
}

func (h *Handler) listAddresses(w http.ResponseWriter, r *http.Request, id Identity) {
	list, err := h.loadAddresses(r, id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	writeOK(w, http.StatusOK, list)
}

func (h *Handler) createAddress(w http.ResponseWriter, r *http.Request, id Identity) {
	var in addressInput
	if !decode(w, r, &in) {
		return
	}
	if msg := in.validate(); msg != "" {
		writeFail(w, http.StatusUnprocessableEntity, msg)
		return
	}
	list, err := h.loadAddresses(r, id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	if len(list) >= 10 {
		writeFail(w, http.StatusUnprocessableEntity, "Tối đa 10 địa chỉ")
		return
	}
	created := address{ID: newID("addr"), FullName: strings.TrimSpace(in.FullName), Phone: in.Phone, Province: in.Province, District: in.District, Ward: in.Ward, Street: in.Street, IsDefault: in.IsDefault || len(list) == 0}
	if created.IsDefault {
		for i := range list {
			list[i].IsDefault = false
		}
	}
	list = append(list, created)
	if err := h.saveAddresses(r, id, list); err != nil {
		h.fail500(w, err)
		return
	}
	writeOK(w, http.StatusCreated, created)
}

func (h *Handler) updateAddress(w http.ResponseWriter, r *http.Request, id Identity) {
	var in addressInput
	if !decode(w, r, &in) {
		return
	}
	if msg := in.validate(); msg != "" {
		writeFail(w, http.StatusUnprocessableEntity, msg)
		return
	}
	list, err := h.loadAddresses(r, id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	for i := range list {
		if list[i].ID != r.PathValue("id") {
			continue
		}
		wasDefault := list[i].IsDefault
		list[i] = address{ID: list[i].ID, FullName: strings.TrimSpace(in.FullName), Phone: in.Phone, Province: in.Province, District: in.District, Ward: in.Ward, Street: in.Street, IsDefault: wasDefault || in.IsDefault}
		if in.IsDefault {
			for j := range list {
				list[j].IsDefault = j == i
			}
		}
		if err := h.saveAddresses(r, id, list); err != nil {
			h.fail500(w, err)
			return
		}
		writeOK(w, http.StatusOK, list[i])
		return
	}
	writeFail(w, http.StatusNotFound, "Không tìm thấy địa chỉ")
}

func (h *Handler) deleteAddress(w http.ResponseWriter, r *http.Request, id Identity) {
	list, err := h.loadAddresses(r, id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	kept := make([]address, 0, len(list))
	removedDefault, found := false, false
	for _, item := range list {
		if item.ID == r.PathValue("id") {
			found, removedDefault = true, item.IsDefault
			continue
		}
		kept = append(kept, item)
	}
	if !found {
		writeFail(w, http.StatusNotFound, "Không tìm thấy địa chỉ")
		return
	}
	if removedDefault && len(kept) > 0 {
		kept[0].IsDefault = true
	}
	if err := h.saveAddresses(r, id, kept); err != nil {
		h.fail500(w, err)
		return
	}
	writeOK(w, http.StatusOK, kept)
}

func (h *Handler) defaultAddress(w http.ResponseWriter, r *http.Request, id Identity) {
	list, err := h.loadAddresses(r, id)
	if err != nil {
		h.fail500(w, err)
		return
	}
	found := false
	for i := range list {
		list[i].IsDefault = list[i].ID == r.PathValue("id")
		found = found || list[i].IsDefault
	}
	if !found {
		writeFail(w, http.StatusNotFound, "Không tìm thấy địa chỉ")
		return
	}
	if err := h.saveAddresses(r, id, list); err != nil {
		h.fail500(w, err)
		return
	}
	writeOK(w, http.StatusOK, list)
}

// ---- vouchers -------------------------------------------------------------

type voucherView struct {
	Code        string `json:"code"`
	Title       string `json:"title"`
	Description string `json:"description"`
	Kind        string `json:"kind"`
	MinSpend    int64  `json:"minSpend"`
	Eligible    bool   `json:"eligible"`
	Reason      string `json:"reason,omitempty"`
}

func (v voucherFx) evaluate(subtotal int64) (discount, shipping int64, reason string) {
	switch {
	case v.Expired:
		return 0, 0, "Mã đã hết hạn"
	case subtotal < v.MinSpend:
		return 0, 0, "Đơn hàng chưa đạt giá trị tối thiểu"
	}
	switch v.Kind {
	case "amount":
		discount = v.Value
	case "percent":
		discount = subtotal * v.Value / 100
		if v.Cap > 0 && discount > v.Cap {
			discount = v.Cap
		}
	case "freeship":
		shipping = v.Value
	}
	if discount > subtotal {
		discount = subtotal
	}
	return discount, shipping, ""
}

func (h *Handler) listVouchers(w http.ResponseWriter, r *http.Request, _ Identity) {
	var subtotal int64
	if raw := r.URL.Query().Get("subtotal"); raw != "" {
		for _, c := range raw {
			if c < '0' || c > '9' {
				writeFail(w, http.StatusBadRequest, "subtotal không hợp lệ")
				return
			}
			subtotal = subtotal*10 + int64(c-'0')
			if subtotal > 1_000_000_000_000 {
				break
			}
		}
	}
	out := make([]voucherView, 0, len(h.fx.Vouchers))
	for _, v := range h.fx.Vouchers {
		_, _, reason := v.evaluate(subtotal)
		out = append(out, voucherView{Code: v.Code, Title: v.Title, Description: v.Description, Kind: v.Kind, MinSpend: v.MinSpend, Eligible: reason == "", Reason: reason})
	}
	writeOK(w, http.StatusOK, out)
}

func (h *Handler) applyVoucher(w http.ResponseWriter, r *http.Request, _ Identity) {
	var in struct {
		Code     string `json:"code"`
		Subtotal int64  `json:"subtotal"`
	}
	if !decode(w, r, &in) {
		return
	}
	code := strings.ToUpper(strings.TrimSpace(in.Code))
	for _, v := range h.fx.Vouchers {
		if v.Code != code {
			continue
		}
		discount, shipping, reason := v.evaluate(in.Subtotal)
		if reason != "" {
			writeFail(w, http.StatusUnprocessableEntity, reason)
			return
		}
		writeOK(w, http.StatusOK, map[string]any{"code": v.Code, "title": v.Title, "discount": discount, "shippingDiscount": shipping})
		return
	}
	writeFail(w, http.StatusUnprocessableEntity, "Mã giảm giá không tồn tại")
}

// ---- reviews and product extras -------------------------------------------

type reviewView struct {
	ID        string    `json:"id"`
	Author    string    `json:"author"`
	Rating    int       `json:"rating"`
	Comment   string    `json:"comment"`
	CreatedAt time.Time `json:"createdAt"`
	Verified  bool      `json:"verified"`
	Mine      bool      `json:"mine"`
}

type userReview struct {
	ID        string    `json:"id"`
	UserID    string    `json:"userId"`
	Author    string    `json:"author"`
	Rating    int       `json:"rating"`
	Comment   string    `json:"comment"`
	CreatedAt time.Time `json:"createdAt"`
}

// productReviews picks a stable subset of the fixture reviews per product so
// different products do not all show the same wall of text.
func (h *Handler) productReviews(productID string, now time.Time) []reviewView {
	n := len(h.fx.Reviews)
	count := 4 + int(hashOf(productID)%uint32(n-3))
	offset := int(hashOf(productID+"o") % uint32(n))
	out := make([]reviewView, 0, count)
	for i := 0; i < count; i++ {
		fx := h.fx.Reviews[(offset+i)%n]
		out = append(out, reviewView{ID: "seed-" + fx.Author, Author: fx.Author, Rating: fx.Rating, Comment: fx.Comment, CreatedAt: now.AddDate(0, 0, -fx.DaysAgo), Verified: fx.Verified})
	}
	return out
}

func (h *Handler) listReviews(w http.ResponseWriter, r *http.Request, id Identity) {
	productID := r.PathValue("id")
	now := h.now()
	items := h.productReviews(productID, now)
	var mine []userReview
	if _, err := getJSON(r.Context(), h.store, "reviews:"+productID, &mine); err != nil {
		h.fail500(w, err)
		return
	}
	for _, m := range mine {
		items = append(items, reviewView{ID: m.ID, Author: m.Author, Rating: m.Rating, Comment: m.Comment, CreatedAt: m.CreatedAt, Verified: true, Mine: m.UserID == id.ID})
	}
	sort.SliceStable(items, func(i, j int) bool { return items[i].CreatedAt.After(items[j].CreatedAt) })
	distribution := map[int]int{1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
	total := 0
	for _, item := range items {
		distribution[item.Rating]++
		total += item.Rating
	}
	average := 0.0
	if len(items) > 0 {
		average = float64(total*10/len(items)) / 10
	}
	writeOK(w, http.StatusOK, map[string]any{"summary": map[string]any{"average": average, "count": len(items), "distribution": distribution}, "items": items})
}

func (h *Handler) createReview(w http.ResponseWriter, r *http.Request, id Identity) {
	var in struct {
		Rating  int    `json:"rating"`
		Comment string `json:"comment"`
	}
	if !decode(w, r, &in) {
		return
	}
	comment := strings.TrimSpace(in.Comment)
	if in.Rating < 1 || in.Rating > 5 {
		writeFail(w, http.StatusUnprocessableEntity, "Số sao phải từ 1 đến 5")
		return
	}
	if len([]rune(comment)) < 5 || len([]rune(comment)) > 500 {
		writeFail(w, http.StatusUnprocessableEntity, "Nhận xét cần từ 5 đến 500 ký tự")
		return
	}
	productID := r.PathValue("id")
	var mine []userReview
	if _, err := getJSON(r.Context(), h.store, "reviews:"+productID, &mine); err != nil {
		h.fail500(w, err)
		return
	}
	for _, m := range mine {
		if m.UserID == id.ID {
			writeFail(w, http.StatusConflict, "Bạn đã đánh giá sản phẩm này")
			return
		}
	}
	author := id.Name
	if author == "" {
		author = "Người mua"
	}
	review := userReview{ID: newID("rev"), UserID: id.ID, Author: author, Rating: in.Rating, Comment: comment, CreatedAt: h.now()}
	mine = append(mine, review)
	if err := setJSON(r.Context(), h.store, "reviews:"+productID, mine); err != nil {
		h.fail500(w, err)
		return
	}
	writeOK(w, http.StatusCreated, reviewView{ID: review.ID, Author: author, Rating: review.Rating, Comment: comment, CreatedAt: review.CreatedAt, Verified: true, Mine: true})
}

var colorPalette = []struct{ ID, Label, Hex string }{
	{"den", "Đen than", "#1F2328"}, {"kem", "Kem", "#E9DFC9"}, {"xanh", "Xanh rêu", "#3F5B4A"}, {"xam", "Xám bạc", "#A9AEB4"},
}

func (h *Handler) getExtras(w http.ResponseWriter, r *http.Request, _ Identity) {
	productID := r.PathValue("id")
	sum := hashOf(productID)
	colorCount := 2 + int(sum%3)
	colors := make([]map[string]any, 0, colorCount)
	for i := 0; i < colorCount; i++ {
		c := colorPalette[(int(sum)+i)%len(colorPalette)]
		colors = append(colors, map[string]any{"id": c.ID, "label": c.Label, "hex": c.Hex, "priceDelta": int64(i) * 20000, "stock": 3 + int((sum>>uint(i))%40)})
	}
	sizes := []string{}
	if sum%2 == 0 {
		sizes = []string{"S", "M", "L", "XL"}
	}
	views := []string{"Mặt trước", "Mặt sau", "Cận cảnh", "Đóng gói"}
	gallery := make([]map[string]any, len(views))
	for i, label := range views {
		gallery[i] = map[string]any{"id": i + 1, "label": label}
	}
	writeOK(w, http.StatusOK, map[string]any{"colors": colors, "sizes": sizes, "gallery": gallery})
}
