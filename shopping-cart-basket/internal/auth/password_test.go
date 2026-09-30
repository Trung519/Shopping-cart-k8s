package auth

import "testing"

func TestHashAndVerifyPassword(t *testing.T) {
	hash, err := HashPassword("correct-horse-battery-staple")
	if err != nil {
		t.Fatalf("HashPassword() error = %v", err)
	}
	if hash == "correct-horse-battery-staple" {
		t.Fatal("HashPassword() returned plaintext")
	}
	if !VerifyPassword(hash, "", "correct-horse-battery-staple") {
		t.Fatal("VerifyPassword() rejected a valid password")
	}
	if VerifyPassword(hash, "", "wrong") {
		t.Fatal("VerifyPassword() accepted an invalid password")
	}
}

func TestVerifyPasswordSupportsLegacyMigration(t *testing.T) {
	if !VerifyPassword("", "legacy-password", "legacy-password") {
		t.Fatal("VerifyPassword() rejected a matching legacy password")
	}
	if VerifyPassword("", "legacy-password", "other-password") {
		t.Fatal("VerifyPassword() accepted a mismatched legacy password")
	}
}
