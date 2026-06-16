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

// PointInput is the create/upsert/update body for measurement points.
type PointInput struct {
	Name                *string `json:"name,omitempty"`
	ExternalID          *string `json:"external_id,omitempty"`
	AssetID             *int    `json:"asset_id,omitempty"`
	AssetExternalID     *string `json:"asset_external_id,omitempty"`
	TransducerType      *string `json:"transducer_type,omitempty"`
	MeasurementUnitCode *string `json:"measurement_unit_code,omitempty"`
	Location            *string `json:"location,omitempty"`
	BodySegment         *int    `json:"body_segment,omitempty"`
	BodyAngle           *int    `json:"body_angle,omitempty"`
	MachineClass        *string `json:"machine_class,omitempty"`
}

// Create creates a measurement point.
func (m *MeasurementPoints) Create(ctx context.Context, in PointInput) (*MeasurementPoint, error) {
	var out MeasurementPoint
	if err := m.client.doJSON(ctx, http.MethodPost, pathf(m.iid, "/measurement-points"), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Upsert creates or updates a measurement point, matched by external_id.
func (m *MeasurementPoints) Upsert(ctx context.Context, in PointInput) (*MeasurementPoint, error) {
	var out MeasurementPoint
	if err := m.client.doJSON(ctx, http.MethodPut, pathf(m.iid, "/measurement-points"), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Update partially updates a measurement point by numeric id.
func (m *MeasurementPoints) Update(ctx context.Context, pointID int, in PointInput) (*MeasurementPoint, error) {
	var out MeasurementPoint
	if err := m.client.doJSON(ctx, http.MethodPatch, pathf(m.iid, fmt.Sprintf("/measurement-points/%d", pointID)), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Delete removes a measurement point; cascade also removes children.
func (m *MeasurementPoints) Delete(ctx context.Context, pointID int, cascade bool) (*DeleteResult, error) {
	q := url.Values{}
	if cascade {
		q.Set("cascade", "true")
	}
	var out DeleteResult
	if err := m.client.doJSON(ctx, http.MethodDelete, pathf(m.iid, fmt.Sprintf("/measurement-points/%d", pointID)), q, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
