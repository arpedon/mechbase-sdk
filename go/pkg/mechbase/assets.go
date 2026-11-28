package mechbase

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
)

// AssetInput is the create/upsert/update body. Nil fields are omitted.
type AssetInput struct {
	Name              *string `json:"name,omitempty"`
	ExternalID        *string `json:"external_id,omitempty"`
	SectionID         *int    `json:"section_id,omitempty"`
	SectionExternalID *string `json:"section_external_id,omitempty"`
	ZoneID            *int    `json:"zone_id,omitempty"`
	ZoneExternalID    *string `json:"zone_external_id,omitempty"`
	EquipmentType     *string `json:"equipment_type,omitempty"`
	MachineClass      *string `json:"machine_class,omitempty"`
	// AssetType is a type code. Nil leaves it untouched; set ClearAssetType to send null.
	AssetType      *string `json:"asset_type,omitempty"`
	ClearAssetType bool    `json:"-"`
	// FedFrom (update only) is the feeding asset's asset_id. Nil leaves it untouched; set ClearFedFrom to send null.
	FedFrom      *int `json:"fed_from,omitempty"`
	ClearFedFrom bool `json:"-"`
}

// MarshalJSON adds an explicit null for asset_type / fed_from when their Clear flag is set.
func (in AssetInput) MarshalJSON() ([]byte, error) {
	type plain AssetInput
	b, err := json.Marshal(plain(in))
	clearType, clearFed := in.ClearAssetType && in.AssetType == nil, in.ClearFedFrom && in.FedFrom == nil
	if err != nil || !(clearType || clearFed) {
		return b, err
	}
	var m map[string]json.RawMessage
	if err := json.Unmarshal(b, &m); err != nil {
		return nil, err
	}
	if clearType {
		m["asset_type"] = json.RawMessage("null")
	}
	if clearFed {
		m["fed_from"] = json.RawMessage("null")
	}
	return json.Marshal(m)
}

// Assets is the asset registry resource scoped to an installation.
type Assets struct {
	client *Client
	iid    int
}

// ListAssetsOptions filters Assets.List. Zero values are omitted.
type ListAssetsOptions struct {
	Q      string
	ZoneID int
	Limit  int
	Offset int
}

// List returns a page of assets.
func (a *Assets) List(ctx context.Context, opts ListAssetsOptions) ([]Asset, error) {
	q := url.Values{}
	if opts.Q != "" {
		q.Set("q", opts.Q)
	}
	if opts.ZoneID != 0 {
		q.Set("zone_id", fmt.Sprintf("%d", opts.ZoneID))
	}
	addPaging(q, opts.Limit, opts.Offset)
	var env listEnvelope[Asset]
	if err := a.client.doJSON(ctx, http.MethodGet, pathf(a.iid, "/assets"), q, nil, &env); err != nil {
		return nil, err
	}
	return env.Items, nil
}

// Get fetches one asset by numeric id.
func (a *Assets) Get(ctx context.Context, assetID int) (*Asset, error) {
	var out Asset
	if err := a.client.doJSON(ctx, http.MethodGet, pathf(a.iid, fmt.Sprintf("/assets/%d", assetID)), nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Create creates an asset.
func (a *Assets) Create(ctx context.Context, in AssetInput) (*Asset, error) {
	var out Asset
	if err := a.client.doJSON(ctx, http.MethodPost, pathf(a.iid, "/assets"), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Upsert creates or updates an asset, matched by external_id.
func (a *Assets) Upsert(ctx context.Context, in AssetInput) (*Asset, error) {
	var out Asset
	if err := a.client.doJSON(ctx, http.MethodPut, pathf(a.iid, "/assets"), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Update partially updates an asset by numeric id.
func (a *Assets) Update(ctx context.Context, assetID int, in AssetInput) (*Asset, error) {
	var out Asset
	if err := a.client.doJSON(ctx, http.MethodPatch, pathf(a.iid, fmt.Sprintf("/assets/%d", assetID)), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Delete removes an asset; cascade also removes children.
func (a *Assets) Delete(ctx context.Context, assetID int, cascade bool) (*DeleteResult, error) {
	q := url.Values{}
	if cascade {
		q.Set("cascade", "true")
	}
	var out DeleteResult
	if err := a.client.doJSON(ctx, http.MethodDelete, pathf(a.iid, fmt.Sprintf("/assets/%d", assetID)), q, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// AddPhoto appends a photo to the asset's gallery. A non-empty photoUUID is a
// client-minted id so a retry returns the same photo.
func (a *Assets) AddPhoto(ctx context.Context, assetID int, filename string, file io.Reader, photoUUID string) (*FileAttachment, error) {
	return a.client.addPhoto(ctx, pathf(a.iid, fmt.Sprintf("/assets/%d/photos/", assetID)), filename, file, photoUUID, nil)
}

// DeletePhoto removes a gallery photo by uuid.
func (a *Assets) DeletePhoto(ctx context.Context, assetID int, photoUUID string) error {
	return a.client.doJSON(ctx, http.MethodDelete, pathf(a.iid, fmt.Sprintf("/assets/%d/photos/%s", assetID, photoUUID)), nil, nil, nil)
}

// EnsureChecklist creates (or finds) the asset's checklist route from its type.
// 422 if the asset has no type or the type's checklist is empty.
func (a *Assets) EnsureChecklist(ctx context.Context, assetID int) (*Checklist, error) {
	var out Checklist
	if err := a.client.doJSON(ctx, http.MethodPost, pathf(a.iid, fmt.Sprintf("/assets/%d/checklist", assetID)), nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
