package mechbase

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
)

// Sections is the section registry resource.
type Sections struct {
	client *Client
	iid    int
}

// SectionInput is the create/upsert/update body for sections.
type SectionInput struct {
	Name       *string `json:"name,omitempty"`
	ExternalID *string `json:"external_id,omitempty"`
}

// ListSectionsOptions filters Sections.List. Zero values are omitted.
type ListSectionsOptions struct {
	Q      string
	Limit  int
	Offset int
}

// List returns a page of sections.
func (s *Sections) List(ctx context.Context, opts ListSectionsOptions) ([]Section, error) {
	q := url.Values{}
	if opts.Q != "" {
		q.Set("q", opts.Q)
	}
	addPaging(q, opts.Limit, opts.Offset)
	var env listEnvelope[Section]
	if err := s.client.doJSON(ctx, http.MethodGet, pathf(s.iid, "/sections"), q, nil, &env); err != nil {
		return nil, err
	}
	return env.Items, nil
}

// Get fetches one section by numeric id.
func (s *Sections) Get(ctx context.Context, sectionID int) (*Section, error) {
	var out Section
	if err := s.client.doJSON(ctx, http.MethodGet, pathf(s.iid, fmt.Sprintf("/sections/%d", sectionID)), nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Create creates a section.
func (s *Sections) Create(ctx context.Context, in SectionInput) (*Section, error) {
	var out Section
	if err := s.client.doJSON(ctx, http.MethodPost, pathf(s.iid, "/sections"), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Upsert creates or updates a section, matched by external_id.
func (s *Sections) Upsert(ctx context.Context, in SectionInput) (*Section, error) {
	var out Section
	if err := s.client.doJSON(ctx, http.MethodPut, pathf(s.iid, "/sections"), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Update partially updates a section by numeric id.
func (s *Sections) Update(ctx context.Context, sectionID int, in SectionInput) (*Section, error) {
	var out Section
	if err := s.client.doJSON(ctx, http.MethodPatch, pathf(s.iid, fmt.Sprintf("/sections/%d", sectionID)), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Delete removes a section; cascade also removes children.
func (s *Sections) Delete(ctx context.Context, sectionID int, cascade bool) (*DeleteResult, error) {
	q := url.Values{}
	if cascade {
		q.Set("cascade", "true")
	}
	var out DeleteResult
	if err := s.client.doJSON(ctx, http.MethodDelete, pathf(s.iid, fmt.Sprintf("/sections/%d", sectionID)), q, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
