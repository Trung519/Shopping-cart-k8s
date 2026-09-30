package handler

import (
	"errors"
	"net/http"
	"slices"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/user/shopping-cart-basket/internal/auth"
	"github.com/user/shopping-cart-basket/internal/model"
	"github.com/user/shopping-cart-basket/internal/repository"
	"go.uber.org/zap"
)

type loginRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

type loginResponse struct {
	AccessToken string        `json:"accessToken"`
	TokenType   string        `json:"tokenType"`
	ExpiresIn   int64         `json:"expiresIn"`
	User        loginUserInfo `json:"user"`
}

type loginUserInfo struct {
	ID       string   `json:"id"`
	Username string   `json:"username"`
	Name     string   `json:"name"`
	Email    string   `json:"email"`
	Roles    []string `json:"roles"`
}

type userCreateRequest struct {
	Username string   `json:"username" binding:"required"`
	Password string   `json:"password" binding:"required"`
	Name     string   `json:"name" binding:"required"`
	Email    string   `json:"email" binding:"required,email"`
	Roles    []string `json:"roles" binding:"required"`
}

type userUpdateRequest struct {
	Username *string   `json:"username"`
	Password *string   `json:"password"`
	Name     *string   `json:"name"`
	Email    *string   `json:"email"`
	Roles    *[]string `json:"roles"`
}

// AuthHandler handles local authentication endpoints.
type AuthHandler struct {
	tokenManager *auth.LocalTokenManager
	users        repository.LocalUserRepository
	logger       *zap.Logger
}

// NewAuthHandler builds a new local auth handler.
func NewAuthHandler(
	tokenManager *auth.LocalTokenManager,
	users repository.LocalUserRepository,
	logger *zap.Logger,
) *AuthHandler {
	return &AuthHandler{
		tokenManager: tokenManager,
		users:        users,
		logger:       logger,
	}
}

// Login handles POST /api/auth/login.
func (h *AuthHandler) Login(c *gin.Context) {
	var req loginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "BAD_REQUEST",
				"message": "Invalid login request",
			},
		})
		return
	}

	username := strings.ToLower(strings.TrimSpace(req.Username))
	password := strings.TrimSpace(req.Password)

	user, err := h.users.GetByUsername(c.Request.Context(), username)
	if err != nil || !auth.VerifyPassword(user.PasswordHash, user.Password, password) {
		c.JSON(http.StatusUnauthorized, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "UNAUTHORIZED",
				"message": "Invalid username or password",
			},
		})
		return
	}

	// Upgrade legacy plaintext Redis records in place after a successful login.
	if user.PasswordHash == "" && user.Password != "" {
		if err := h.users.Save(c.Request.Context(), *user); err != nil {
			h.logger.Error("failed to upgrade legacy password", zap.String("user_id", user.ID), zap.Error(err))
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": gin.H{"message": "Failed to secure account credentials"}})
			return
		}
	}

	token, expiresAt, err := h.tokenManager.GenerateToken(user.ID, user.Email, user.Name, user.Roles)
	if err != nil {
		h.logger.Error("failed to generate local auth token",
			zap.String("user", user.Username),
			zap.Error(err),
		)
		c.JSON(http.StatusInternalServerError, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "INTERNAL_ERROR",
				"message": "Failed to create login session",
			},
		})
		return
	}

	expiresIn := int64(time.Until(expiresAt).Seconds())
	if expiresIn < 0 {
		expiresIn = 0
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"data": loginResponse{
			AccessToken: token,
			TokenType:   "Bearer",
			ExpiresIn:   expiresIn,
			User:        toLoginUserInfo(*user),
		},
	})
}

// ListUsers handles GET /api/auth/users.
func (h *AuthHandler) ListUsers(c *gin.Context) {
	users, err := h.users.List(c.Request.Context())
	if err != nil {
		h.logger.Error("failed to list local users", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "INTERNAL_ERROR",
				"message": "Failed to load users",
			},
		})
		return
	}

	response := make([]loginUserInfo, 0, len(users))
	for _, user := range users {
		response = append(response, toLoginUserInfo(user))
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"data":    response,
	})
}

// CreateUser handles POST /api/auth/users.
func (h *AuthHandler) CreateUser(c *gin.Context) {
	var req userCreateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "BAD_REQUEST",
				"message": "Invalid user payload",
			},
		})
		return
	}

	user, err := buildUserFromCreate(req)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "BAD_REQUEST",
				"message": err.Error(),
			},
		})
		return
	}

	if _, err := h.users.GetByUsername(c.Request.Context(), user.Username); err == nil {
		c.JSON(http.StatusConflict, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "CONFLICT",
				"message": "Username already exists",
			},
		})
		return
	} else if !errors.Is(err, repository.ErrLocalUserNotFound) {
		h.logger.Error("failed to check existing local user", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "INTERNAL_ERROR",
				"message": "Failed to create user",
			},
		})
		return
	}

	if err := h.users.Save(c.Request.Context(), user); err != nil {
		h.logger.Error("failed to save local user", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "INTERNAL_ERROR",
				"message": "Failed to create user",
			},
		})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"success": true,
		"data":    toLoginUserInfo(user),
	})
}

// UpdateUser handles PUT /api/auth/users/:id.
func (h *AuthHandler) UpdateUser(c *gin.Context) {
	var req userUpdateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "BAD_REQUEST",
				"message": "Invalid user payload",
			},
		})
		return
	}

	id := strings.TrimSpace(c.Param("id"))
	user, err := h.users.GetByID(c.Request.Context(), id)
	if err != nil {
		statusCode := http.StatusInternalServerError
		message := "Failed to update user"
		if errors.Is(err, repository.ErrLocalUserNotFound) {
			statusCode = http.StatusNotFound
			message = "User not found"
		}
		c.JSON(statusCode, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "NOT_FOUND",
				"message": message,
			},
		})
		return
	}

	updatedUser, oldUsername, err := mergeUserUpdate(*user, req)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "BAD_REQUEST",
				"message": err.Error(),
			},
		})
		return
	}

	if updatedUser.Username != oldUsername {
		if existing, err := h.users.GetByUsername(c.Request.Context(), updatedUser.Username); err == nil && existing.ID != updatedUser.ID {
			c.JSON(http.StatusConflict, gin.H{
				"success": false,
				"error": gin.H{
					"code":    "CONFLICT",
					"message": "Username already exists",
				},
			})
			return
		} else if err != nil && !errors.Is(err, repository.ErrLocalUserNotFound) {
			h.logger.Error("failed to validate username change", zap.Error(err))
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"error": gin.H{
					"code":    "INTERNAL_ERROR",
					"message": "Failed to update user",
				},
			})
			return
		}
	}

	if updatedUser.Username != oldUsername {
		if err := h.users.DeleteByUsername(c.Request.Context(), oldUsername); err != nil {
			h.logger.Error("failed to replace local user username", zap.Error(err))
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"error": gin.H{
					"code":    "INTERNAL_ERROR",
					"message": "Failed to update user",
				},
			})
			return
		}
	}

	if err := h.users.Save(c.Request.Context(), updatedUser); err != nil {
		h.logger.Error("failed to update local user", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "INTERNAL_ERROR",
				"message": "Failed to update user",
			},
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"data":    toLoginUserInfo(updatedUser),
	})
}

// DeleteUser handles DELETE /api/auth/users/:id.
func (h *AuthHandler) DeleteUser(c *gin.Context) {
	id := strings.TrimSpace(c.Param("id"))
	if id == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "BAD_REQUEST",
				"message": "User ID is required",
			},
		})
		return
	}

	currentUserID := getCustomerID(c)
	if currentUserID != "" && currentUserID == id {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "BAD_REQUEST",
				"message": "You cannot delete the currently signed-in admin",
			},
		})
		return
	}

	user, err := h.users.GetByID(c.Request.Context(), id)
	if err != nil {
		statusCode := http.StatusInternalServerError
		message := "Failed to delete user"
		if errors.Is(err, repository.ErrLocalUserNotFound) {
			statusCode = http.StatusNotFound
			message = "User not found"
		}
		c.JSON(statusCode, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "NOT_FOUND",
				"message": message,
			},
		})
		return
	}

	if err := h.users.DeleteByUsername(c.Request.Context(), user.Username); err != nil {
		h.logger.Error("failed to delete local user", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"success": false,
			"error": gin.H{
				"code":    "INTERNAL_ERROR",
				"message": "Failed to delete user",
			},
		})
		return
	}

	c.Status(http.StatusNoContent)
}

func DefaultLocalUsers() []model.LocalUser {
	return []model.LocalUser{
		{
			ID:       "demo-user",
			Username: "demo",
			Password: "demo123",
			Name:     "Demo User",
			Email:    "demo@shopcart.local",
			Roles:    []string{"cart-user"},
		},
		{
			ID:       "admin-user",
			Username: "admin",
			Password: "admin123",
			Name:     "Admin User",
			Email:    "admin@shopcart.local",
			Roles:    []string{"cart-user", "cart-admin", "admin", "catalog-admin"},
		},
	}
}

func toLoginUserInfo(user model.LocalUser) loginUserInfo {
	return loginUserInfo{
		ID:       user.ID,
		Username: user.Username,
		Name:     user.Name,
		Email:    user.Email,
		Roles:    user.Roles,
	}
}

func buildUserFromCreate(req userCreateRequest) (model.LocalUser, error) {
	username := strings.ToLower(strings.TrimSpace(req.Username))
	password := strings.TrimSpace(req.Password)
	name := strings.TrimSpace(req.Name)
	email := strings.ToLower(strings.TrimSpace(req.Email))
	roles := normalizeRoles(req.Roles)

	switch {
	case username == "":
		return model.LocalUser{}, errors.New("username is required")
	case password == "":
		return model.LocalUser{}, errors.New("password is required")
	case name == "":
		return model.LocalUser{}, errors.New("name is required")
	case email == "":
		return model.LocalUser{}, errors.New("email is required")
	case len(roles) == 0:
		return model.LocalUser{}, errors.New("at least one role is required")
	}

	return model.LocalUser{
		ID:       username + "-user",
		Username: username,
		Password: password,
		Name:     name,
		Email:    email,
		Roles:    roles,
	}, nil
}

func mergeUserUpdate(user model.LocalUser, req userUpdateRequest) (model.LocalUser, string, error) {
	oldUsername := user.Username

	if req.Username != nil {
		username := strings.ToLower(strings.TrimSpace(*req.Username))
		if username == "" {
			return model.LocalUser{}, oldUsername, errors.New("username cannot be empty")
		}
		user.Username = username
	}
	if req.Password != nil {
		password := strings.TrimSpace(*req.Password)
		if password == "" {
			return model.LocalUser{}, oldUsername, errors.New("password cannot be empty")
		}
		user.Password = password
	}
	if req.Name != nil {
		name := strings.TrimSpace(*req.Name)
		if name == "" {
			return model.LocalUser{}, oldUsername, errors.New("name cannot be empty")
		}
		user.Name = name
	}
	if req.Email != nil {
		email := strings.ToLower(strings.TrimSpace(*req.Email))
		if email == "" {
			return model.LocalUser{}, oldUsername, errors.New("email cannot be empty")
		}
		user.Email = email
	}
	if req.Roles != nil {
		roles := normalizeRoles(*req.Roles)
		if len(roles) == 0 {
			return model.LocalUser{}, oldUsername, errors.New("at least one role is required")
		}
		user.Roles = roles
	}

	return user, oldUsername, nil
}

func normalizeRoles(roles []string) []string {
	normalized := make([]string, 0, len(roles))
	for _, role := range roles {
		trimmed := strings.ToLower(strings.TrimSpace(role))
		if trimmed == "" || slices.Contains(normalized, trimmed) {
			continue
		}
		normalized = append(normalized, trimmed)
	}
	return normalized
}
