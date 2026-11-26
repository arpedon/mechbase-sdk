package mechbase

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/url"
)

// Comments is the asset comment thread resource.
type Comments struct {
	client *Client
	iid    int
}

func (c *Comments) path(assetID int, suffix string) string {
	return pathf(c.iid, fmt.Sprintf("/assets/%d/comments%s", assetID, suffix))
}

// List returns one page of an asset's comments. Zero limit/offset are omitted.
func (c *Comments) List(ctx context.Context, assetID, limit, offset int) (*CommentsPage, error) {
	q := url.Values{}
	addPaging(q, limit, offset)
	var out CommentsPage
	if err := c.client.doJSON(ctx, http.MethodGet, c.path(assetID, ""), q, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func commentBody(body string, refs []CommentReferenceIn) map[string]any {
	if refs == nil {
		refs = []CommentReferenceIn{}
	}
	return map[string]any{"body": body, "references": refs}
}

// Create posts a comment (body is rich-text HTML).
func (c *Comments) Create(ctx context.Context, assetID int, body string, refs []CommentReferenceIn) (*Comment, error) {
	var out Comment
	if err := c.client.doJSON(ctx, http.MethodPost, c.path(assetID, ""), nil, commentBody(body, refs), &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Update replaces the body and the whole reference set. A 403 means you are not
// the author, or the comment is a finding's note.
func (c *Comments) Update(ctx context.Context, assetID, commentID int, body string, refs []CommentReferenceIn) (*Comment, error) {
	var out Comment
	if err := c.client.doJSON(ctx, http.MethodPatch, c.path(assetID, fmt.Sprintf("/%d", commentID)), nil, commentBody(body, refs), &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Delete removes a comment (same 403 rule as Update).
func (c *Comments) Delete(ctx context.Context, assetID, commentID int) error {
	return c.client.doJSON(ctx, http.MethodDelete, c.path(assetID, fmt.Sprintf("/%d", commentID)), nil, nil, nil)
}

// Documents is the asset documents resource.
type Documents struct {
	client *Client
	iid    int
}

// List returns an asset's documents.
func (d *Documents) List(ctx context.Context, assetID int) ([]Document, error) {
	var out []Document
	if err := d.client.doJSON(ctx, http.MethodGet, pathf(d.iid, fmt.Sprintf("/assets/%d/documents", assetID)), nil, nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// Add uploads a document. kind is attachment (default when empty) | drawing |
// datasheet | manual | check_sheet | test_report; filename defaults to
// "document.pdf" (the server rejects names without an extension); a non-empty
// uuid is a client-minted id so retries are idempotent.
func (d *Documents) Add(ctx context.Context, assetID int, file io.Reader, filename, kind, uuid string) (*Document, error) {
	if filename == "" {
		filename = "document.pdf"
	}
	if kind == "" {
		kind = "attachment"
	}
	fields := map[string]string{"kind": kind}
	if uuid != "" {
		fields["uuid"] = uuid
	}
	var out Document
	if err := d.client.doMultipart(ctx, pathf(d.iid, fmt.Sprintf("/assets/%d/documents", assetID)), fields, []filePart{{Field: "file", Filename: filename, Reader: file}}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Delete removes a document by uuid.
func (d *Documents) Delete(ctx context.Context, assetID int, uuid string) error {
	return d.client.doJSON(ctx, http.MethodDelete, pathf(d.iid, fmt.Sprintf("/assets/%d/documents/%s", assetID, uuid)), nil, nil, nil)
}

// AlarmRules is the measurement-point alarm rule resource. Only method=threshold
// point overrides are writable; installation defaults are read-only (403).
type AlarmRules struct {
	client *Client
	iid    int
}

func (a *AlarmRules) path(pointID int, suffix string) string {
	return pathf(a.iid, fmt.Sprintf("/measurement-points/%d/alarm-rules%s", pointID, suffix))
}

// List returns the rules in effect for a point.
func (a *AlarmRules) List(ctx context.Context, pointID int) ([]AlarmRule, error) {
	var out []AlarmRule
	if err := a.client.doJSON(ctx, http.MethodGet, a.path(pointID, ""), nil, nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// Create adds a point threshold override (409 if one exists). Empty direction
// means "high"; empty dataKey means the transducer type's default.
func (a *AlarmRules) Create(ctx context.Context, pointID int, minorThreshold, majorThreshold float64, dataKey, direction string) (*AlarmRule, error) {
	if direction == "" {
		direction = "high"
	}
	body := map[string]any{"method": "threshold", "data_key": dataKey, "direction": direction, "minor_threshold": minorThreshold, "major_threshold": majorThreshold}
	var out AlarmRule
	if err := a.client.doJSON(ctx, http.MethodPost, a.path(pointID, ""), nil, body, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Update sends only the non-nil fields.
func (a *AlarmRules) Update(ctx context.Context, pointID int, uuid string, minorThreshold, majorThreshold *float64, dataKey, direction *string) (*AlarmRule, error) {
	body := map[string]any{}
	if minorThreshold != nil {
		body["minor_threshold"] = *minorThreshold
	}
	if majorThreshold != nil {
		body["major_threshold"] = *majorThreshold
	}
	if dataKey != nil {
		body["data_key"] = *dataKey
	}
	if direction != nil {
		body["direction"] = *direction
	}
	var out AlarmRule
	if err := a.client.doJSON(ctx, http.MethodPatch, a.path(pointID, "/"+uuid), nil, body, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Delete removes a point override.
func (a *AlarmRules) Delete(ctx context.Context, pointID int, uuid string) error {
	return a.client.doJSON(ctx, http.MethodDelete, a.path(pointID, "/"+uuid), nil, nil, nil)
}
