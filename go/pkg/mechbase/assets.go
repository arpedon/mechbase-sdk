package mechbase

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
)

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
