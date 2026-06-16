package mechbase

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
)

// Zones is the zone registry resource.
type Zones struct {
	client *Client
	iid    int
}

// ZoneInput is the create/upsert/update body for zones.
type ZoneInput struct {
	Name              *string `json:"name,omitempty"`
	ExternalID        *string `json:"external_id,omitempty"`
	SectionID         *int    `json:"section_id,omitempty"`
	SectionExternalID *string `json:"section_external_id,omitempty"`
}

// ListZonesOptions filters Zones.List. Zero values are omitted.
type ListZonesOptions struct {
	Q         string
	SectionID int
	Limit     int
	Offset    int
}

// List returns a page of zones.
func (z *Zones) List(ctx context.Context, opts ListZonesOptions) ([]Zone, error) {
	q := url.Values{}
	if opts.Q != "" {
		q.Set("q", opts.Q)
	}
	if opts.SectionID != 0 {
		q.Set("section_id", fmt.Sprintf("%d", opts.SectionID))
	}
	addPaging(q, opts.Limit, opts.Offset)
	var env listEnvelope[Zone]
	if err := z.client.doJSON(ctx, http.MethodGet, pathf(z.iid, "/zones"), q, nil, &env); err != nil {
		return nil, err
	}
	return env.Items, nil
}

// Get fetches one zone by numeric id.
func (z *Zones) Get(ctx context.Context, zoneID int) (*Zone, error) {
	var out Zone
	if err := z.client.doJSON(ctx, http.MethodGet, pathf(z.iid, fmt.Sprintf("/zones/%d", zoneID)), nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Create creates a zone.
func (z *Zones) Create(ctx context.Context, in ZoneInput) (*Zone, error) {
	var out Zone
	if err := z.client.doJSON(ctx, http.MethodPost, pathf(z.iid, "/zones"), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Upsert creates or updates a zone, matched by external_id.
func (z *Zones) Upsert(ctx context.Context, in ZoneInput) (*Zone, error) {
	var out Zone
	if err := z.client.doJSON(ctx, http.MethodPut, pathf(z.iid, "/zones"), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Update partially updates a zone by numeric id.
func (z *Zones) Update(ctx context.Context, zoneID int, in ZoneInput) (*Zone, error) {
	var out Zone
	if err := z.client.doJSON(ctx, http.MethodPatch, pathf(z.iid, fmt.Sprintf("/zones/%d", zoneID)), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Delete removes a zone; cascade also removes children.
func (z *Zones) Delete(ctx context.Context, zoneID int, cascade bool) (*DeleteResult, error) {
	q := url.Values{}
	if cascade {
		q.Set("cascade", "true")
	}
	var out DeleteResult
	if err := z.client.doJSON(ctx, http.MethodDelete, pathf(z.iid, fmt.Sprintf("/zones/%d", zoneID)), q, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
