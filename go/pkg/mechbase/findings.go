package mechbase

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
)

// Findings is the diagnostic findings resource.
type Findings struct {
	client *Client
	iid    int
}

// ListFindingsOptions filters Findings.List. Zero values are omitted.
type ListFindingsOptions struct {
	Cursor          string
	Limit           int
	Since           string // RFC 3339
	Status          string // open | acknowledged | closed
	AssetID         int
	AssetExternalID string
	PointID         int
	PointExternalID string
}

// List returns one cursor page of findings; pass FindingsPage.NextCursor as
// Cursor for the next page.
func (f *Findings) List(ctx context.Context, opts ListFindingsOptions) (*FindingsPage, error) {
	q := url.Values{}
	set := func(k, v string) {
		if v != "" {
			q.Set(k, v)
		}
	}
	set("cursor", opts.Cursor)
	set("since", opts.Since)
	set("status", opts.Status)
	set("asset_external_id", opts.AssetExternalID)
	set("point_external_id", opts.PointExternalID)
	if opts.Limit > 0 {
		q.Set("limit", fmt.Sprintf("%d", opts.Limit))
	}
	if opts.AssetID != 0 {
		q.Set("asset_id", fmt.Sprintf("%d", opts.AssetID))
	}
	if opts.PointID != 0 {
		q.Set("point_id", fmt.Sprintf("%d", opts.PointID))
	}
	var out FindingsPage
	if err := f.client.doJSON(ctx, http.MethodGet, pathf(f.iid, "/findings/"), q, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Get fetches one finding.
func (f *Findings) Get(ctx context.Context, findingUUID string) (*Finding, error) {
	var out Finding
	if err := f.client.doJSON(ctx, http.MethodGet, pathf(f.iid, fmt.Sprintf("/findings/%s/", findingUUID)), nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// SetStatus acknowledges or closes a finding. status is "acknowledged" or
// "closed". workOrderRef is required to acknowledge, optional to close.
func (f *Findings) SetStatus(ctx context.Context, findingUUID, status, workOrderRef string) (*Finding, error) {
	body := map[string]any{"status": status}
	if workOrderRef != "" {
		body["work_order_ref"] = workOrderRef
	}
	var out Finding
	if err := f.client.doJSON(ctx, http.MethodPost, pathf(f.iid, fmt.Sprintf("/findings/%s/status/", findingUUID)), nil, body, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
