package mechbase

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

// Execution is a handle for operating on an existing route execution.
type Execution struct {
	client    *Client
	iid       int
	UUID      string
	Execution RouteExecution
}

// Photo is an in-memory or streaming photo attachment.
type Photo struct {
	Name   string
	Reader io.Reader
}

// RespondInput is the payload for a route-item response.
type RespondInput struct {
	RouteItemUUID string
	Data          map[string]any
	Notes         string
}

// FieldItemInput is the payload for adding an ad-hoc field item to an execution.
type FieldItemInput struct {
	Label    string
	ItemType string // defaults to "pass_fail"
	Data     map[string]any
	ZoneID   *int
	AssetID  *int
	Config   map[string]any
	Notes    string
}

func (e *Execution) url(suffix string) string {
	return pathf(e.iid, fmt.Sprintf("/executions/%s%s", e.UUID, suffix))
}

// Respond submits a JSON response to a route item.
func (e *Execution) Respond(ctx context.Context, in RespondInput) (*ItemResponse, error) {
	payload := map[string]any{
		"route_item_uuid": in.RouteItemUUID,
		"data":            in.Data,
		"notes":           in.Notes,
	}
	var out ItemResponse
	if err := e.client.doJSON(ctx, http.MethodPost, e.url("/responses"), nil, payload, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// RespondWithPhotos submits a route-item response together with photo attachments.
func (e *Execution) RespondWithPhotos(ctx context.Context, in RespondInput, photos []Photo) (*ItemResponse, error) {
	if len(photos) == 0 {
		return e.Respond(ctx, in)
	}
	payload := map[string]any{
		"route_item_uuid": in.RouteItemUUID,
		"data":            in.Data,
		"notes":           in.Notes,
	}
	encoded, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("mechbase: marshal payload: %w", err)
	}
	files := make([]filePart, 0, len(photos))
	for _, p := range photos {
		name := p.Name
		if name == "" {
			name = "photo"
		}
		files = append(files, filePart{Field: "files", Filename: name, Reader: p.Reader})
	}
	var out ItemResponse
	if err := e.client.doMultipart(ctx, e.url("/responses/upload"), map[string]string{"payload": string(encoded)}, files, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// AddFieldItem creates a new ad-hoc item against the running execution.
func (e *Execution) AddFieldItem(ctx context.Context, in FieldItemInput) (*ItemResponse, error) {
	itemType := in.ItemType
	if itemType == "" {
		itemType = "pass_fail"
	}
	data := in.Data
	if data == nil {
		data = map[string]any{}
	}
	cfg := in.Config
	if cfg == nil {
		cfg = map[string]any{}
	}
	payload := map[string]any{
		"label":     in.Label,
		"item_type": itemType,
		"data":      data,
		"zone_id":   in.ZoneID,
		"asset_id":  in.AssetID,
		"config":    cfg,
		"notes":     in.Notes,
	}
	var out ItemResponse
	if err := e.client.doJSON(ctx, http.MethodPost, e.url("/items"), nil, payload, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Triage links a route-item response to a particular asset (post-hoc triage).
func (e *Execution) Triage(ctx context.Context, routeItemUUID string, assetID int) (*ItemResponse, error) {
	payload := map[string]any{
		"route_item_uuid": routeItemUUID,
		"asset_id":        assetID,
	}
	var out ItemResponse
	if err := e.client.doJSON(ctx, http.MethodPost, e.url("/triage"), nil, payload, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Complete finalizes the execution.
func (e *Execution) Complete(ctx context.Context) (*RouteExecution, error) {
	var out RouteExecution
	if err := e.client.doJSON(ctx, http.MethodPost, e.url("/complete"), nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
