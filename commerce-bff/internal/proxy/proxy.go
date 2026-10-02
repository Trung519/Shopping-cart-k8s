package proxy

import (
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"

	"github.com/wilddog64/commerce-bff/internal/session"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
)

type Target struct {
	PublicPrefix, UpstreamPrefix string
	URL                          *url.URL
	PublicRead                   bool
	AllowedRoles                 []string
}

func NewTarget(publicPrefix, upstreamPrefix, rawURL string, publicRead bool, allowedRoles []string) (Target, error) {
	targetURL, err := url.Parse(rawURL)
	if err != nil {
		return Target{}, err
	}
	return Target{PublicPrefix: publicPrefix, UpstreamPrefix: upstreamPrefix, URL: targetURL, PublicRead: publicRead, AllowedRoles: allowedRoles}, nil
}

func (t Target) ServeHTTP(w http.ResponseWriter, r *http.Request, authSession *session.Session) {
	upstream := httputil.NewSingleHostReverseProxy(t.URL)
	upstream.Transport = otelhttp.NewTransport(http.DefaultTransport)
	originalDirector := upstream.Director
	upstream.Director = func(req *http.Request) {
		originalDirector(req)
		req.URL.Path = t.UpstreamPrefix + strings.TrimPrefix(r.URL.Path, t.PublicPrefix)
		req.Host = t.URL.Host
		if authSession != nil {
			req.Header.Set("Authorization", "Bearer "+authSession.AccessToken)
			req.Header.Set("X-User-ID", authSession.User.ID)
			req.Header.Set("X-User-Roles", strings.Join(authSession.User.Roles, ","))
		}
	}
	upstream.ErrorHandler = func(writer http.ResponseWriter, _ *http.Request, _ error) {
		writer.Header().Set("Content-Type", "application/json")
		writer.WriteHeader(http.StatusBadGateway)
		writer.Write([]byte(`{"success":false,"message":"Dịch vụ tạm thời không khả dụng"}`))
	}
	upstream.ServeHTTP(w, r)
}
