package auth

import (
	"crypto/subtle"

	"golang.org/x/crypto/bcrypt"
)

const passwordHashCost = 12

// HashPassword creates a one-way password hash suitable for local transition accounts.
func HashPassword(password string) (string, error) {
	hash, err := bcrypt.GenerateFromPassword([]byte(password), passwordHashCost)
	if err != nil {
		return "", err
	}
	return string(hash), nil
}

// VerifyPassword accepts bcrypt records and one-time legacy plaintext records.
func VerifyPassword(passwordHash, legacyPassword, candidate string) bool {
	if passwordHash != "" {
		return bcrypt.CompareHashAndPassword([]byte(passwordHash), []byte(candidate)) == nil
	}
	if legacyPassword == "" || len(legacyPassword) != len(candidate) {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(legacyPassword), []byte(candidate)) == 1
}
