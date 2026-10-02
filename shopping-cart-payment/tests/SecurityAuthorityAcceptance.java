import com.shoppingcart.payment.config.KeycloakRealmAuthoritiesConverter;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;

/** Runs against the exact live Spring dependencies used by the overlay image. */
public class SecurityAuthorityAcceptance {
    public static void main(String[] args) {
        var converter = new KeycloakRealmAuthoritiesConverter();
        var admin = Jwt.withTokenValue("test").header("alg", "RS256")
            .claim("scope", "openid profile")
            .claim("realm_access", Map.of("roles", List.of("platform-admin", "payment-read", "unrelated-admin")))
            .build();
        Set<String> granted = converter.convert(admin).stream()
            .map(GrantedAuthority::getAuthority).collect(Collectors.toSet());
        if (!granted.equals(Set.of("SCOPE_openid", "SCOPE_profile", "ROLE_PLATFORM_ADMIN", "ROLE_PAYMENT_READ"))) {
            throw new AssertionError("Existing scopes/allowlisted realm roles mapping failed");
        }
        var denied = Jwt.withTokenValue("test").header("alg", "RS256")
            .claim("scope", "PAYMENT_READ")
            .claim("resource_access", Map.of("unrelated-client", Map.of("roles", List.of("platform-admin"))))
            .claim("realm_access", Map.of("roles", List.of("customer", 123)))
            .build();
        if (converter.convert(denied).stream().anyMatch(a -> a.getAuthority().startsWith("ROLE_"))) {
            throw new AssertionError("Unrelated scopes/client claims granted payment authority");
        }
        var malformed = Jwt.withTokenValue("test").header("alg", "RS256")
            .claim("realm_access", "invalid").build();
        if (!converter.convert(malformed).isEmpty()) throw new AssertionError("Malformed role claim granted authority");
        System.out.println("Payment authority positive/negative/malformed tests passed against live runtime dependencies.");
    }
}
