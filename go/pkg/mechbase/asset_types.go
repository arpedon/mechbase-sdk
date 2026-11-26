package mechbase

import (
	"context"
	"fmt"
	"io"
	"net/http"
)

// AssetTypes is the asset type (template) resource, addressed by code.
type AssetTypes struct {
	client *Client
	iid    int
}

// AssetTypeInput is the upsert/update body. Nil fields are omitted.
type AssetTypeInput struct {
	Code         *string          `json:"code,omitempty"`
	Name         *string          `json:"name,omitempty"`
	Manufacturer *string          `json:"manufacturer,omitempty"`
	Checklist    []map[string]any `json:"checklist,omitempty"`
	ExternalID   *string          `json:"external_id,omitempty"`
}

func (a *AssetTypes) path(suffix string) string {
	return pathf(a.iid, "/asset-types"+suffix)
}

// List returns all asset types.
func (a *AssetTypes) List(ctx context.Context) ([]AssetType, error) {
	var out []AssetType
	if err := a.client.doJSON(ctx, http.MethodGet, a.path(""), nil, nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// Get fetches one type by code.
func (a *AssetTypes) Get(ctx context.Context, code string) (*AssetType, error) {
	var out AssetType
	if err := a.client.doJSON(ctx, http.MethodGet, a.path("/"+code), nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Upsert creates or updates a type keyed on in.Code.
func (a *AssetTypes) Upsert(ctx context.Context, in AssetTypeInput) (*AssetType, error) {
	var out AssetType
	if err := a.client.doJSON(ctx, http.MethodPut, a.path(""), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Update partially updates a type by code.
func (a *AssetTypes) Update(ctx context.Context, code string, in AssetTypeInput) (*AssetType, error) {
	var out AssetType
	if err := a.client.doJSON(ctx, http.MethodPatch, a.path("/"+code), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Delete removes a type by code.
func (a *AssetTypes) Delete(ctx context.Context, code string) (*DeleteResult, error) {
	var out DeleteResult
	if err := a.client.doJSON(ctx, http.MethodDelete, a.path("/"+code), nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Documents lists a type's documents.
func (a *AssetTypes) Documents(ctx context.Context, code string) ([]Document, error) {
	var out []Document
	if err := a.client.doJSON(ctx, http.MethodGet, a.path("/"+code+"/documents"), nil, nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// AddDocument uploads a document; empty filename/kind default to
// "document.pdf"/"attachment"; a non-empty uuid makes retries idempotent.
func (a *AssetTypes) AddDocument(ctx context.Context, code string, file io.Reader, filename, kind, uuid string) (*Document, error) {
	if filename == "" {
		filename = "document.pdf"
	}
	if kind == "" {
		kind = "attachment"
	}
	fields := map[string]string{"kind": kind}
	if uuid != "" {
		fields["uuid"] = uuid
	}
	var out Document
	if err := a.client.doMultipart(ctx, a.path("/"+code+"/documents"), fields, []filePart{{Field: "file", Filename: filename, Reader: file}}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// DeleteDocument removes a type document by uuid.
func (a *AssetTypes) DeleteDocument(ctx context.Context, code, uuid string) error {
	return a.client.doJSON(ctx, http.MethodDelete, a.path(fmt.Sprintf("/%s/documents/%s", code, uuid)), nil, nil, nil)
}
