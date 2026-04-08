// Package mechbase is a hand-written Go SDK for the Mechbase API.
package mechbase

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// userAgent identifies this SDK in API requests.
const userAgent = "mechbase-go/0.1"

// DefaultBaseURL is the hosted Mechbase service. Pass a different URL to New
// for self-hosted installations.
const DefaultBaseURL = "https://app.mechbase.io"

// Client is the top-level Mechbase API client.
type Client struct {
	token   string
	baseURL string
	http    *http.Client
}

// Option configures a Client.
type Option func(*Client)

// WithHTTPClient sets a custom *http.Client.
func WithHTTPClient(h *http.Client) Option {
	return func(c *Client) { c.http = h }
}

// WithTimeout sets the underlying http.Client timeout.
func WithTimeout(d time.Duration) Option {
	return func(c *Client) {
		if c.http == nil {
			c.http = &http.Client{}
		}
		c.http.Timeout = d
	}
}

// New creates a new Mechbase Client. Pass an empty baseURL to use DefaultBaseURL.
func New(token, baseURL string, opts ...Option) *Client {
	if baseURL == "" {
		baseURL = DefaultBaseURL
	}
	c := &Client{
		token:   token,
		baseURL: strings.TrimRight(baseURL, "/"),
		http:    &http.Client{Timeout: 30 * time.Second},
	}
	for _, o := range opts {
		o(c)
	}
	return c
}

// ForInstallation returns a handle scoped to one installation.
func (c *Client) ForInstallation(id int) *Installation_ {
	return &Installation_{
		client:            c,
		ID:                id,
		Assets:            &Assets{client: c, iid: id},
		MeasurementPoints: &MeasurementPoints{client: c, iid: id},
		Measurements:      &Measurements{client: c, iid: id},
		Routes:            &Routes{client: c, iid: id},
	}
}

// Installation_ groups installation-scoped resources. (Trailing underscore avoids
// colliding with the Installation model.)
type Installation_ struct {
	client            *Client
	ID                int
	Assets            *Assets
	MeasurementPoints *MeasurementPoints
	Measurements      *Measurements
	Routes            *Routes
}

// Me returns the authenticated user and accessible installations.
func (c *Client) Me(ctx context.Context) (*Me, error) {
	var out Me
	if err := c.doJSON(ctx, http.MethodGet, "/api/me", nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// pathf builds an installation-scoped API path.
func pathf(iid int, suffix string) string {
	return fmt.Sprintf("/api/installations/%d%s", iid, suffix)
}

// doJSON performs an API request with optional JSON body and query params and
// decodes the JSON response into out (pass nil to discard).
func (c *Client) doJSON(ctx context.Context, method, path string, query url.Values, body any, out any) error {
	var reader io.Reader
	if body != nil {
		buf, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("mechbase: marshal body: %w", err)
		}
		reader = bytes.NewReader(buf)
	}
	req, err := c.newRequest(ctx, method, path, query, reader)
	if err != nil {
		return err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	return c.do(req, out)
}

// doMultipart performs a multipart POST. fields are form fields; files are
// streamed parts. Decodes the JSON response into out.
type filePart struct {
	Field    string
	Filename string
	Reader   io.Reader
}

func (c *Client) doMultipart(ctx context.Context, path string, fields map[string]string, files []filePart, out any) error {
	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)
	for k, v := range fields {
		if err := mw.WriteField(k, v); err != nil {
			return fmt.Errorf("mechbase: multipart field: %w", err)
		}
	}
	for _, f := range files {
		w, err := mw.CreateFormFile(f.Field, f.Filename)
		if err != nil {
			return fmt.Errorf("mechbase: multipart file: %w", err)
		}
		if _, err := io.Copy(w, f.Reader); err != nil {
			return fmt.Errorf("mechbase: multipart copy: %w", err)
		}
	}
	if err := mw.Close(); err != nil {
		return fmt.Errorf("mechbase: multipart close: %w", err)
	}
	req, err := c.newRequest(ctx, http.MethodPost, path, nil, &buf)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", mw.FormDataContentType())
	return c.do(req, out)
}

func (c *Client) newRequest(ctx context.Context, method, path string, query url.Values, body io.Reader) (*http.Request, error) {
	u := c.baseURL + path
	if len(query) > 0 {
		u += "?" + query.Encode()
	}
	req, err := http.NewRequestWithContext(ctx, method, u, body)
	if err != nil {
		return nil, fmt.Errorf("mechbase: build request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.token)
	req.Header.Set("User-Agent", userAgent)
	req.Header.Set("Accept", "application/json")
	return req, nil
}

func (c *Client) do(req *http.Request, out any) error {
	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("mechbase: http do: %w", err)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("mechbase: read body: %w", err)
	}
	if resp.StatusCode == http.StatusNoContent {
		return nil
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		detail := string(raw)
		var maybe map[string]any
		if json.Unmarshal(raw, &maybe) == nil {
			if d, ok := maybe["detail"].(string); ok {
				detail = d
			}
		}
		return &APIError{Status: resp.StatusCode, Detail: detail, Body: raw}
	}
	if out == nil || len(raw) == 0 {
		return nil
	}
	if err := json.Unmarshal(raw, out); err != nil {
		return fmt.Errorf("mechbase: decode response: %w", err)
	}
	return nil
}

// listEnvelope is the standard paginated wrapper.
type listEnvelope[T any] struct {
	Items  []T `json:"items"`
	Total  int `json:"total"`
	Limit  int `json:"limit"`
	Offset int `json:"offset"`
}

// addPaging applies limit/offset to a query if non-zero.
func addPaging(q url.Values, limit, offset int) {
	if limit > 0 {
		q.Set("limit", fmt.Sprintf("%d", limit))
	}
	if offset > 0 {
		q.Set("offset", fmt.Sprintf("%d", offset))
	}
}
