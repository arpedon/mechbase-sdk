package mechbase

import (
	"context"
	"fmt"
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
