package mock

import "encoding/json"

type voucherFx struct {
	Code        string `json:"code"`
	Title       string `json:"title"`
	Description string `json:"description"`
	Kind        string `json:"kind"`
	Value       int64  `json:"value"`
	Cap         int64  `json:"cap"`
	MinSpend    int64  `json:"minSpend"`
	Expired     bool   `json:"expired"`
}

type reviewFx struct {
	Author   string `json:"author"`
	Rating   int    `json:"rating"`
	Comment  string `json:"comment"`
	DaysAgo  int    `json:"daysAgo"`
	Verified bool   `json:"verified"`
}

type notificationFx struct {
	Type       string `json:"type"`
	Title      string `json:"title"`
	Text       string `json:"text"`
	MinutesAgo int    `json:"minutesAgo"`
}

type sellerOrderItemFx struct {
	Name  string `json:"name"`
	Qty   int    `json:"qty"`
	Price int64  `json:"price"`
}

type sellerOrderFx struct {
	ID         string              `json:"id"`
	Buyer      string              `json:"buyer"`
	City       string              `json:"city"`
	Items      []sellerOrderItemFx `json:"items"`
	Status     string              `json:"status"`
	MinutesAgo int                 `json:"minutesAgo"`
}

type inventoryFx struct {
	SKU          string `json:"sku"`
	Name         string `json:"name"`
	Stock        int    `json:"stock"`
	Reserved     int    `json:"reserved"`
	LowThreshold int    `json:"lowThreshold"`
}

type threadMessageFx struct {
	From       string `json:"from"`
	Text       string `json:"text"`
	MinutesAgo int    `json:"minutesAgo"`
}

type threadFx struct {
	ID       string            `json:"id"`
	Buyer    string            `json:"buyer"`
	Product  string            `json:"product"`
	Messages []threadMessageFx `json:"messages"`
}

type financeTxFx struct {
	ID      string `json:"id"`
	Type    string `json:"type"`
	Ref     string `json:"ref"`
	Amount  int64  `json:"amount"`
	DaysAgo int    `json:"daysAgo"`
}

type payoutSeedFx struct {
	ID      string `json:"id"`
	Amount  int64  `json:"amount"`
	Status  string `json:"status"`
	DaysAgo int    `json:"daysAgo"`
}

type sellerFinanceFx struct {
	CommissionRate   float64        `json:"commissionRate"`
	Transactions     []financeTxFx  `json:"transactions"`
	AvailableBalance int64          `json:"availableBalance"`
	PendingBalance   int64          `json:"pendingBalance"`
	SeedPayouts      []payoutSeedFx `json:"seedPayouts"`
}

type promotionFx struct {
	ID       string `json:"id"`
	Name     string `json:"name"`
	Kind     string `json:"kind"`
	Value    int64  `json:"value"`
	MinSpend int64  `json:"minSpend"`
	Status   string `json:"status"`
	Used     int    `json:"used"`
}

type returnFx struct {
	ID       string `json:"id"`
	UserID   string `json:"userId"`
	OrderRef string `json:"orderRef"`
	Buyer    string `json:"buyer"`
	Shop     string `json:"shop"`
	Reason   string `json:"reason"`
	Note     string `json:"note"`
	Amount   int64  `json:"amount"`
	Status   string `json:"status"`
	DaysAgo  int    `json:"daysAgo"`
}

type settlementFx struct {
	ID         string `json:"id"`
	Shop       string `json:"shop"`
	Period     string `json:"period"`
	Gross      int64  `json:"gross"`
	Commission int64  `json:"commission"`
	Net        int64  `json:"net"`
	Status     string `json:"status"`
}

type auditFx struct {
	Actor      string `json:"actor"`
	Action     string `json:"action"`
	Target     string `json:"target"`
	MinutesAgo int    `json:"minutesAgo"`
}

type fixtures struct {
	Vouchers      []voucherFx
	Reviews       []reviewFx
	Notifications []notificationFx
	LiveEvents    []notificationFx
	SellerOrders  []sellerOrderFx
	Inventory     []inventoryFx
	Threads       []threadFx
	Finance       sellerFinanceFx
	Promotions    []promotionFx
	Returns       []returnFx
	Settlements   []settlementFx
	Audit         []auditFx
}

// loadFixtures panics on bad JSON on purpose: the files are embedded, so a
// parse error is a build-time bug that tests catch, never a runtime condition.
func loadFixtures() fixtures {
	var fx fixtures
	load := func(name string, out any) {
		data, err := fixtureFS.ReadFile("fixtures/" + name)
		if err != nil {
			panic("mock fixture missing: " + name)
		}
		if err := json.Unmarshal(data, out); err != nil {
			panic("mock fixture invalid: " + name + ": " + err.Error())
		}
	}
	load("vouchers.json", &fx.Vouchers)
	load("reviews.json", &fx.Reviews)
	load("notifications.json", &fx.Notifications)
	load("live_events.json", &fx.LiveEvents)
	load("seller_orders.json", &fx.SellerOrders)
	load("seller_inventory.json", &fx.Inventory)
	load("seller_messages.json", &fx.Threads)
	load("seller_finance.json", &fx.Finance)
	load("seller_promotions.json", &fx.Promotions)
	load("admin_returns.json", &fx.Returns)
	load("admin_settlements.json", &fx.Settlements)
	load("admin_audit.json", &fx.Audit)
	return fx
}
