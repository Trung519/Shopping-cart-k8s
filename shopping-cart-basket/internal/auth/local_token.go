package auth

import (
	"errors"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

var (
	// ErrInvalidLocalToken is returned when a local auth token is invalid.
	ErrInvalidLocalToken = errors.New("invalid local auth token")
)

// LocalClaims defines claims for local authentication tokens.
type LocalClaims struct {
	Email string   `json:"email"`
	Name  string   `json:"name"`
	Roles []string `json:"roles"`
	jwt.RegisteredClaims
}

// LocalTokenManager handles local token creation and validation.
type LocalTokenManager struct {
	signingKey []byte
	tokenTTL   time.Duration
}

// NewLocalTokenManager returns a token manager for local auth.
func NewLocalTokenManager(secret string, tokenTTL time.Duration) *LocalTokenManager {
	return &LocalTokenManager{
		signingKey: []byte(secret),
		tokenTTL:   tokenTTL,
	}
}

// GenerateToken creates a signed JWT token for a local user.
func (m *LocalTokenManager) GenerateToken(userID, email, name string, roles []string) (string, time.Time, error) {
	now := time.Now()
	expiresAt := now.Add(m.tokenTTL)

	claims := LocalClaims{
		Email: email,
		Name:  name,
		Roles: roles,
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   userID,
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(expiresAt),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	signed, err := token.SignedString(m.signingKey)
	if err != nil {
		return "", time.Time{}, err
	}

	return signed, expiresAt, nil
}

// ParseToken validates and returns token claims.
func (m *LocalTokenManager) ParseToken(tokenString string) (*LocalClaims, error) {
	claims := &LocalClaims{}

	token, err := jwt.ParseWithClaims(tokenString, claims, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, ErrInvalidLocalToken
		}
		return m.signingKey, nil
	})
	if err != nil {
		return nil, ErrInvalidLocalToken
	}
	if !token.Valid || claims.Subject == "" {
		return nil, ErrInvalidLocalToken
	}

	return claims, nil
}
