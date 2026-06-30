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
	// IdempotencyKey, when set, is sent as the X-Idempotency-Key header so the
	// server dedupes a retried create.
	IdempotencyKey string
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
	headers := idempotencyHeaders(in.IdempotencyKey)
	if in.File == nil {
		if err := m.client.doJSONH(ctx, http.MethodPost, pathf(m.iid, "/measurements/"), nil, headers, payload, &out); err != nil {
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
	if err := m.client.doMultipartH(ctx, pathf(m.iid, "/measurements/upload/"), headers, fields, files, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ListForPointOptions filters ListForPoint. Zero values are omitted.
type ListForPointOptions struct {
	Limit       int
	Offset      int
	CreatedFrom string
	CreatedTo   string
}

// ListForPoint returns one offset page of a point's history.
func (m *Measurements) ListForPoint(ctx context.Context, pointID int, opts ListForPointOptions) ([]Measurement, error) {
	q := url.Values{}
	addPaging(q, opts.Limit, opts.Offset)
	if opts.CreatedFrom != "" {
		q.Set("created_from", opts.CreatedFrom)
	}
	if opts.CreatedTo != "" {
		q.Set("created_to", opts.CreatedTo)
	}
	var env listEnvelope[Measurement]
	path := pathf(m.iid, fmt.Sprintf("/measurement-points/%d/measurements/", pointID))
	if err := m.client.doJSON(ctx, http.MethodGet, path, q, nil, &env); err != nil {
		return nil, err
	}
	return env.Items, nil
}

// MeasurementInput is one item in a measurement batch. Supply exactly one of
// PointID / PointExternalID. Nil fields are omitted.
type MeasurementInput struct {
	MeasurementPointID         *int           `json:"measurement_point_id,omitempty"`
	MeasurementPointExternalID *string        `json:"measurement_point_external_id,omitempty"`
	Data                       map[string]any `json:"data"`
	Notes                      *string        `json:"notes,omitempty"`
	SessionID                  *string        `json:"session_id,omitempty"`
	Timestamp                  *string        `json:"timestamp,omitempty"`
	ExternalID                 *string        `json:"external_id,omitempty"`
}

// CreateBatch pushes many measurements in one request.
func (m *Measurements) CreateBatch(ctx context.Context, items []MeasurementInput) (*BatchResult, error) {
	body := map[string]any{"items": items}
	var out BatchResult
	if err := m.client.doJSON(ctx, http.MethodPost, pathf(m.iid, "/measurements/batch/"), nil, body, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// AddFile attaches a file to an existing measurement (multipart).
func (m *Measurements) AddFile(ctx context.Context, measurementUUID, filename string, file io.Reader) (*FileAttachment, error) {
	if filename == "" {
		filename = "attachment"
	}
	files := []filePart{{Field: "file", Filename: filename, Reader: file}}
	var out FileAttachment
	if err := m.client.doMultipart(ctx, pathf(m.iid, fmt.Sprintf("/measurements/%s/files/", measurementUUID)), nil, files, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// IterOptions configures IterForPoint.
type IterOptions struct {
	CreatedFrom string
	CreatedTo   string
	PageSize    int
}

// IterForPoint streams the full history for a point, following cursor pages.
// The callback is invoked per measurement; return an error to stop.
func (m *Measurements) IterForPoint(ctx context.Context, pointID int, opts IterOptions, fn func(Measurement) error) error {
	cursor := ""
	path := pathf(m.iid, fmt.Sprintf("/measurement-points/%d/measurements/", pointID))
	for {
		q := url.Values{}
		q.Set("cursor", cursor)
		if opts.PageSize > 0 {
			q.Set("limit", fmt.Sprintf("%d", opts.PageSize))
		}
		if opts.CreatedFrom != "" {
			q.Set("created_from", opts.CreatedFrom)
		}
		if opts.CreatedTo != "" {
			q.Set("created_to", opts.CreatedTo)
		}
		var env cursorEnvelope[Measurement]
		if err := m.client.doJSON(ctx, http.MethodGet, path, q, nil, &env); err != nil {
			return err
		}
		for _, item := range env.Items {
			if err := fn(item); err != nil {
				return err
			}
		}
		if env.NextCursor == nil || *env.NextCursor == "" {
			return nil
		}
		cursor = *env.NextCursor
	}
}
