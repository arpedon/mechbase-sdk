package mechbase

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
)

// Routes is the routes resource for one installation.
type Routes struct {
	client *Client
	iid    int
}

// ListRoutesOptions filters Routes.List. Zero values are omitted.
type ListRoutesOptions struct {
	Q      string
	Limit  int
	Offset int
}

// List returns a page of routes.
func (r *Routes) List(ctx context.Context, opts ListRoutesOptions) ([]Route, error) {
	q := url.Values{}
	if opts.Q != "" {
		q.Set("q", opts.Q)
	}
	addPaging(q, opts.Limit, opts.Offset)
	var env listEnvelope[Route]
	if err := r.client.doJSON(ctx, http.MethodGet, pathf(r.iid, "/routes"), q, nil, &env); err != nil {
		return nil, err
	}
	return env.Items, nil
}

// Get returns the full route detail (including items) as a raw struct.
func (r *Routes) Get(ctx context.Context, routeUUID string) (*RouteDetail, error) {
	var out RouteDetail
	if err := r.client.doJSON(ctx, http.MethodGet, pathf(r.iid, fmt.Sprintf("/routes/%s", routeUUID)), nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Start kicks off a new execution of a route and returns an Execution handle.
func (r *Routes) Start(ctx context.Context, routeUUID string) (*Execution, error) {
	var exec RouteExecution
	path := pathf(r.iid, fmt.Sprintf("/routes/%s/executions", routeUUID))
	if err := r.client.doJSON(ctx, http.MethodPost, path, nil, nil, &exec); err != nil {
		return nil, err
	}
	return &Execution{
		client:    r.client,
		iid:       r.iid,
		UUID:      exec.UUID,
		Execution: exec,
	}, nil
}

// Execution returns a handle for an existing execution UUID.
func (r *Routes) Execution(executionUUID string) *Execution {
	return &Execution{client: r.client, iid: r.iid, UUID: executionUUID}
}
