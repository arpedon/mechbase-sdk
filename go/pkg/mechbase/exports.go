package mechbase

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/url"
)

// Exports is the analytics bulk-export resource.
type Exports struct {
	client *Client
	iid    int
}

// ExportFilters is the union of feed filters; nil fields are omitted. The
// server uses the subset relevant to the dataset.
type ExportFilters struct {
	AssetID         *int    `json:"asset_id,omitempty"`
	AssetExternalID *string `json:"asset_external_id,omitempty"`
	PointID         *int    `json:"point_id,omitempty"`
	PointExternalID *string `json:"point_external_id,omitempty"`
	TransducerType  *string `json:"transducer_type,omitempty"`
	Status          *string `json:"status,omitempty"`
	Action          *string `json:"action,omitempty"`
	RouteID         *string `json:"route_id,omitempty"`
	CreatedFrom     *string `json:"created_from,omitempty"`
	CreatedTo       *string `json:"created_to,omitempty"`
	UpdatedSince    *string `json:"updated_since,omitempty"`
}

// ExportInput is the Exports.Create body. Format defaults to "csv" server-side.
type ExportInput struct {
	Dataset string         `json:"dataset"`
	Format  string         `json:"format,omitempty"`
	Filters *ExportFilters `json:"filters,omitempty"`
}

// Create queues an export job (202).
func (e *Exports) Create(ctx context.Context, in ExportInput) (*ExportCreated, error) {
	var out ExportCreated
	if err := e.client.doJSON(ctx, http.MethodPost, pathf(e.iid, "/analytics/exports/"), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Status returns the state of an export job.
func (e *Exports) Status(ctx context.Context, jobUUID string) (*ExportStatus, error) {
	var out ExportStatus
	if err := e.client.doJSON(ctx, http.MethodGet, pathf(e.iid, fmt.Sprintf("/analytics/exports/%s/", jobUUID)), nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Download streams a finished export's bytes to w and returns the byte count.
// It reads the job's signed download link from Status, so the job must be done.
// The client's timeout does not apply here (large files); bound it with ctx.
func (e *Exports) Download(ctx context.Context, jobUUID string, w io.Writer) (int64, error) {
	st, err := e.Status(ctx, jobUUID)
	if err != nil {
		return 0, err
	}
	if st.DownloadURL == nil || *st.DownloadURL == "" {
		return 0, fmt.Errorf("mechbase: export %s has no file yet (state %s)", jobUUID, st.State)
	}
	link, err := url.Parse(*st.DownloadURL)
	if err != nil {
		return 0, fmt.Errorf("mechbase: bad download url: %w", err)
	}
	// Keep only the signature; the path resolves against the client's base URL.
	q := url.Values{"sig": {link.Query().Get("sig")}}
	req, err := e.client.newRequest(ctx, http.MethodGet, pathf(e.iid, fmt.Sprintf("/analytics/exports/%s/download/", jobUUID)), q, nil)
	if err != nil {
		return 0, err
	}
	req.Header.Set("Accept", "*/*")
	noTimeout := *e.client.http
	noTimeout.Timeout = 0
	resp, err := noTimeout.Do(req)
	if err != nil {
		return 0, fmt.Errorf("mechbase: http do: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		raw, _ := io.ReadAll(resp.Body)
		return 0, newAPIError(resp.StatusCode, raw)
	}
	return io.Copy(w, resp.Body)
}
