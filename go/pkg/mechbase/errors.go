package mechbase

import (
	"errors"
	"fmt"
)

// Sentinel errors. Use errors.Is to detect them.
var (
	ErrAuth       = errors.New("mechbase: authentication failed")
	ErrNotFound   = errors.New("mechbase: not found")
	ErrValidation = errors.New("mechbase: validation failed")
)

// APIError is returned for non-2xx responses from the Mechbase API.
type APIError struct {
	Status int
	Detail string
	Body   []byte
}

func (e *APIError) Error() string {
	return fmt.Sprintf("mechbase: api error %d: %s", e.Status, e.Detail)
}

// Unwrap maps common HTTP statuses to sentinel errors so callers can use errors.Is.
func (e *APIError) Unwrap() error {
	switch e.Status {
	case 401, 403:
		return ErrAuth
	case 404:
		return ErrNotFound
	case 422:
		return ErrValidation
	}
	return nil
}
