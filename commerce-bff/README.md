# Commerce BFF

Browser-facing API for ShopCart. It owns the OIDC Authorization Code + PKCE flow,
stores tokens server-side in Redis, and exposes only a signed HttpOnly session cookie.

All browser traffic uses `/api/v2`; internal service URLs stay inside the mesh.
