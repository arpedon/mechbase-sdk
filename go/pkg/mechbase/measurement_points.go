package mechbase

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
)

// MeasurementPoints is the measurement-point registry resource.
type MeasurementPoints struct {
	client *Client
	iid    int
}

// ListMeasurementPointsOptions filters the list query. Zero values are omitted.
type ListMeasurementPointsOptions struct {
	Q              string
	AssetID        int
	TransducerType string
	Limit          int
	Offset         int
}

// List returns a page of measurement points.
func (m *MeasurementPoints) List(ctx context.Context, opts ListMeasurementPointsOptions) ([]MeasurementPoint, error) {
	q := url.Values{}
	if opts.Q != "" {
		q.Set("q", opts.Q)
	}
	if opts.AssetID != 0 {
		q.Set("asset_id", fmt.Sprintf("%d", opts.AssetID))
	}
	if opts.TransducerType != "" {
		q.Set("transducer_type", opts.TransducerType)
	}
	addPaging(q, opts.Limit, opts.Offset)
	var env listEnvelope[MeasurementPoint]
	if err := m.client.doJSON(ctx, http.MethodGet, pathf(m.iid, "/measurement-points"), q, nil, &env); err != nil {
		return nil, err
	}
	return env.Items, nil
}

// Get fetches one measurement point by numeric id.
func (m *MeasurementPoints) Get(ctx context.Context, pointID int) (*MeasurementPoint, error) {
	var out MeasurementPoint
	if err := m.client.doJSON(ctx, http.MethodGet, pathf(m.iid, fmt.Sprintf("/measurement-points/%d", pointID)), nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
