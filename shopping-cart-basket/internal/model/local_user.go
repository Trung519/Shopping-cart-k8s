package model

// LocalUser represents a locally managed username/password account.
type LocalUser struct {
	ID           string   `json:"id"`
	Username     string   `json:"username"`
	Password     string   `json:"password,omitempty"`
	PasswordHash string   `json:"passwordHash,omitempty"`
	Name         string   `json:"name"`
	Email        string   `json:"email"`
	Roles        []string `json:"roles"`
}
