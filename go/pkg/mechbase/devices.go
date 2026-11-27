package mechbase

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"time"
)

// DeviceChannel is one mapped channel of a MaintNode group.
type DeviceChannel struct {
	UUID       string     `json:"uuid"`
	Channel    *int       `json:"channel"`
	PointID    int        `json:"point_id"`
	PointName  string     `json:"point_name"`
	AssetID    int        `json:"asset_id"`
	AssetName  string     `json:"asset_name"`
	Sensor     string     `json:"sensor"`
	LastSeenAt *time.Time `json:"last_seen_at"`
	StaleSince *time.Time `json:"stale_since"`
	State      string     `json:"state"` // ok | stale | waiting
}

// DeviceGroup is one acquisition group on a MaintNode.
type DeviceGroup struct {
	UUID           string          `json:"uuid"`
	Name           string          `json:"name"`
	HardwareType   string          `json:"hardware_type"`
	HardwareConfig map[string]any  `json:"hardware_config"`
	Interval       int             `json:"interval"`
	SampleRate     *int            `json:"sample_rate"`
	Samples        *int            `json:"samples"`
	Channels       []DeviceChannel `json:"channels"`
}

// Tunnel is remote access to a service on a device's site. An http tunnel opens
// in a browser at WebURL; an stcp one needs frpc and the visitor file (staff).
type Tunnel struct {
	UUID       string  `json:"uuid"`
	Name       string  `json:"name"`
	Label      string  `json:"label"`
	Kind       string  `json:"kind"` // http | stcp
	StaffOnly  bool    `json:"staff_only"`
	WebURL     *string `json:"web_url"`
	LocalPort  *int    `json:"local_port"`
	VisitorURL *string `json:"visitor_url"`
}

// StaffTunnel is a Tunnel in the staff list across installations.
type StaffTunnel struct {
	Tunnel
	InstallationID   *int    `json:"installation_id"`
	InstallationName *string `json:"installation_name"`
	NodeUUID         string  `json:"node_uuid"`
	DeviceName       string  `json:"device_name"`
}

// Device is a MaintNode with its groups, channels and the tunnels you may open.
type Device struct {
	NodeUUID       string         `json:"node_uuid"`
	Name           string         `json:"name"`
	IsOnline       bool           `json:"is_online"`
	LastSeenAt     *time.Time     `json:"last_seen_at"`
	ClaimedAt      *time.Time     `json:"claimed_at"`
	Health         map[string]any `json:"health"`
	HealthWarnings []string       `json:"health_warnings"`
	HealthURL      *string        `json:"health_url"` // staff only
	Groups         []DeviceGroup  `json:"groups"`
	Tunnels        []Tunnel       `json:"tunnels"`
}

// SourceGroup names the group a MaintNode source reads through.
type SourceGroup struct {
	UUID         string `json:"uuid"`
	Name         string `json:"name"`
	HardwareType string `json:"hardware_type"`
}

// Source is one data source feeding a measurement point.
type Source struct {
	UUID         string         `json:"uuid"`
	SourceType   string         `json:"source_type"` // mqtt | maintnode
	DeviceID     string         `json:"device_id"`
	DeviceName   *string        `json:"device_name"`
	Group        *SourceGroup   `json:"group"`
	Channel      *int           `json:"channel"`
	Sensor       string         `json:"sensor"`
	SensorConfig map[string]any `json:"sensor_config"`
	IsActive     bool           `json:"is_active"`
	LastSeenAt   *time.Time     `json:"last_seen_at"`
	StaleSince   *time.Time     `json:"stale_since"`
}

// Devices is the installation's MaintNode devices resource.
type Devices struct {
	client *Client
	iid    int
}

// List returns the devices, those needing attention first.
func (d *Devices) List(ctx context.Context) ([]Device, error) {
	var out []Device
	if err := d.client.doJSON(ctx, http.MethodGet, pathf(d.iid, "/devices"), nil, nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (d *Devices) one(ctx context.Context, method, suffix string, body any) (*Device, error) {
	var out Device
	if err := d.client.doJSON(ctx, method, pathf(d.iid, "/devices/"+suffix), nil, body, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Get returns one device by node uuid.
func (d *Devices) Get(ctx context.Context, nodeUUID string) (*Device, error) {
	return d.one(ctx, http.MethodGet, nodeUUID, nil)
}

// Rename renames a device.
func (d *Devices) Rename(ctx context.Context, nodeUUID, name string) (*Device, error) {
	return d.one(ctx, http.MethodPatch, nodeUUID, map[string]string{"name": name})
}

// UpdateGroup changes a group's settings (the group edit page's fields:
// name, interval, sample_rate, samples, hardware_id, hardware_address, Modbus
// connection fields); fields left out keep their value. Returns the device.
func (d *Devices) UpdateGroup(ctx context.Context, nodeUUID, groupUUID string, fields map[string]any) (*Device, error) {
	return d.one(ctx, http.MethodPatch, nodeUUID+"/groups/"+groupUUID, fields)
}

// Sources is a measurement point's data sources resource. Fields are the
// add-source page's (source_type, mqtt_device_id, device, group, group_name,
// hardware_type, mn_channel, register_address, sensor, sensitivity, …).
type Sources struct {
	client *Client
	iid    int
}

func (s *Sources) path(pointID int, suffix string) string {
	return pathf(s.iid, fmt.Sprintf("/measurement-points/%d/sources%s", pointID, suffix))
}

// List returns a point's sources.
func (s *Sources) List(ctx context.Context, pointID int) ([]Source, error) {
	var out []Source
	if err := s.client.doJSON(ctx, http.MethodGet, s.path(pointID, ""), nil, nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// Create adds a source; omitted fields take the page's defaults. A MaintNode
// source with no group creates one.
func (s *Sources) Create(ctx context.Context, pointID int, fields map[string]any) (*Source, error) {
	var out Source
	if err := s.client.doJSON(ctx, http.MethodPost, s.path(pointID, ""), nil, fields, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Update changes a source; fields left out keep their value, and its type,
// device and group stay.
func (s *Sources) Update(ctx context.Context, pointID int, sourceUUID string, fields map[string]any) (*Source, error) {
	var out Source
	if err := s.client.doJSON(ctx, http.MethodPatch, s.path(pointID, "/"+sourceUUID), nil, fields, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Delete removes a source.
func (s *Sources) Delete(ctx context.Context, pointID int, sourceUUID string) error {
	return s.client.doJSON(ctx, http.MethodDelete, s.path(pointID, "/"+sourceUUID), nil, nil, nil)
}

// Tunnels lists every installation's tunnels (staff only).
func (c *Client) Tunnels(ctx context.Context) ([]StaffTunnel, error) {
	var out []StaffTunnel
	if err := c.doJSON(ctx, http.MethodGet, "/api/tunnels", nil, nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// TunnelVisitorFile returns an stcp tunnel's frpc config (staff only): run
// `frpc -c <file>`, then connect to 127.0.0.1:<local_port>. It holds secrets.
func (c *Client) TunnelVisitorFile(ctx context.Context, tunnelUUID string) ([]byte, error) {
	req, err := c.newRequest(ctx, http.MethodGet, "/api/tunnels/"+tunnelUUID+"/visitor.toml", nil, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "*/*")
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("mechbase: http do: %w", err)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("mechbase: read body: %w", err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, newAPIError(resp.StatusCode, raw)
	}
	return raw, nil
}
