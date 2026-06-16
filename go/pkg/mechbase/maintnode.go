package mechbase

import (
	"context"
	"fmt"
	"io"
	"net/http"
)

// MaintNode is the device-facing client for the maintnode integration API.
// It sends no Authorization header; the node is identified by nodeUUID.
type MaintNode struct {
	client   *Client
	nodeUUID string
}

// NewMaintNode creates a tokenless maintnode client. Empty baseURL uses DefaultBaseURL.
func NewMaintNode(nodeUUID, baseURL string, opts ...Option) *MaintNode {
	return &MaintNode{client: New("", baseURL, opts...), nodeUUID: nodeUUID}
}

// MaintNodeMeasurementInput is one item in a maintnode measurement push.
type MaintNodeMeasurementInput struct {
	MappingUUID string         `json:"mapping_uuid"`
	Data        map[string]any `json:"data"`
	Timestamp   *string        `json:"timestamp,omitempty"`
	LocalUUID   string         `json:"local_uuid,omitempty"`
}

func (n *MaintNode) path(suffix string) string {
	return fmt.Sprintf("/api/maintnode/%s%s", n.nodeUUID, suffix)
}

// Config returns the raw node config blob.
func (n *MaintNode) Config(ctx context.Context) (string, error) {
	var out string
	if err := n.client.doJSON(ctx, http.MethodGet, n.path("/config/"), nil, nil, &out); err != nil {
		return "", err
	}
	return out, nil
}

// Heartbeat reports node liveness and returns the server's ack object.
func (n *MaintNode) Heartbeat(ctx context.Context, balenaUUID string, services map[string]any) (map[string]any, error) {
	body := map[string]any{"balena_uuid": balenaUUID, "services": services}
	var out map[string]any
	if err := n.client.doJSON(ctx, http.MethodPost, n.path("/heartbeat/"), nil, body, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// PushMeasurements submits measurements collected by the node.
func (n *MaintNode) PushMeasurements(ctx context.Context, items []MaintNodeMeasurementInput) ([]MeasurementResult, error) {
	body := map[string]any{"measurements": items}
	var out []MeasurementResult
	if err := n.client.doJSON(ctx, http.MethodPost, n.path("/measurements/"), nil, body, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// AddMeasurementFile attaches a file to a node measurement (multipart).
func (n *MaintNode) AddMeasurementFile(ctx context.Context, measurementUUID, filename string, file io.Reader) (map[string]any, error) {
	if filename == "" {
		filename = "attachment"
	}
	files := []filePart{{Field: "file", Filename: filename, Reader: file}}
	var out map[string]any
	if err := n.client.doMultipart(ctx, n.path(fmt.Sprintf("/measurements/%s/file/", measurementUUID)), nil, files, &out); err != nil {
		return nil, err
	}
	return out, nil
}
