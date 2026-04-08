package mechbase

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
)

// Measurements is the measurements resource for one installation.
type Measurements struct {
	client *Client
	iid    int
}

// CreateMeasurementInput is the payload for Measurements.Create.
type CreateMeasurementInput struct {
	PointID   int
	Data      map[string]any
	Notes     string
	SessionID string
	Timestamp string
	// File, if non-nil, switches the request to multipart upload.
	File     io.Reader
	FileName string
}

// Create posts a single measurement. When File is nil it sends JSON; when set
// it sends multipart with the canonical "payload" JSON field.
func (m *Measurements) Create(ctx context.Context, in CreateMeasurementInput) (*Measurement, error) {
	payload := map[string]any{
		"measurement_point_id": in.PointID,
		"data":                 in.Data,
		"notes":                in.Notes,
	}
	if in.SessionID != "" {
		payload["session_id"] = in.SessionID
	}
	if in.Timestamp != "" {
		payload["timestamp"] = in.Timestamp
	}

	var out Measurement
	if in.File == nil {
		if err := m.client.doJSON(ctx, http.MethodPost, pathf(m.iid, "/measurements/"), nil, payload, &out); err != nil {
			return nil, err
		}
		return &out, nil
	}

	encoded, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("mechbase: marshal payload: %w", err)
	}
	name := in.FileName
	if name == "" {
		name = "attachment"
	}
	files := []filePart{{Field: "file", Filename: name, Reader: in.File}}
	fields := map[string]string{"payload": string(encoded)}
	if err := m.client.doMultipart(ctx, pathf(m.iid, "/measurements/upload/"), fields, files, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ListForPoint returns the measurement history for a specific point.
func (m *Measurements) ListForPoint(ctx context.Context, pointID, limit, offset int) ([]Measurement, error) {
	q := url.Values{}
	addPaging(q, limit, offset)
	var env listEnvelope[Measurement]
	path := pathf(m.iid, fmt.Sprintf("/measurement-points/%d/measurements/", pointID))
	if err := m.client.doJSON(ctx, http.MethodGet, path, q, nil, &env); err != nil {
		return nil, err
	}
	return env.Items, nil
}
