package com.shoppingcart.payment.config;

import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.springframework.core.convert.converter.Converter;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtGrantedAuthoritiesConverter;

/** Maps only existing payment roles from the validated realm JWT; retains scopes. */
public final class KeycloakRealmAuthoritiesConverter implements Converter<Jwt, Collection<GrantedAuthority>> {
    private static final Set<String> PAYMENT_ROLES = Set.of(
        "PAYMENT_USER", "PAYMENT_READ", "PAYMENT_WRITE", "PAYMENT_ADMIN", "PLATFORM_ADMIN");
    private final JwtGrantedAuthoritiesConverter scopes = new JwtGrantedAuthoritiesConverter();

    @Override
    public Collection<GrantedAuthority> convert(Jwt jwt) {
        Set<GrantedAuthority> authorities = new LinkedHashSet<>(scopes.convert(jwt));
        Object realmAccess = jwt.getClaims().get("realm_access");
        if (realmAccess instanceof Map<?, ?> realm && realm.get("roles") instanceof Collection<?> roles) {
            for (Object value : roles) {
                if (value instanceof String role) {
                    String normalized = role.toUpperCase(Locale.ROOT).replace('-', '_');
                    if (PAYMENT_ROLES.contains(normalized)) {
                        authorities.add(new SimpleGrantedAuthority("ROLE_" + normalized));
                    }
                }
            }
        }
        return authorities;
    }
}
