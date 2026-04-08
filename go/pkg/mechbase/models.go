package mechbase

import "time"

// User represents an API user.
type User struct {
	ID       int    `json:"id"`
	Username string `json:"username"`
	FullName string `json:"full_name"`
	Email    string `json:"email"`
}

// Installation is a Mechbase installation (plant/site).
type Installation struct {
	InstallationID int    `json:"installation_id"`
	Name           string `json:"name"`
}

// Me describes the authenticated user and accessible installations.
type Me struct {
	User                  User           `json:"user"`
	Installations         []Installation `json:"installations"`
	CurrentInstallationID int            `json:"current_installation_id"`
}

// Asset is a tracked machine.
type Asset struct {
	UUID         string `json:"uuid"`
	AssetID      *int   `json:"asset_id"`
	Name         string `json:"name"`
	ZoneID       *int   `json:"zone_id"`
	MachineClass string `json:"machine_class"`
	Status       int    `json:"status"`
}

// MeasurementPoint is a measurement location on an asset.
type MeasurementPoint struct {
	UUID                string `json:"uuid"`
	PointID             *int   `json:"point_id"`
	Name                string `json:"name"`
	AssetID             *int   `json:"asset_id"`
	TransducerType      string `json:"transducer_type"`
	MeasurementUnitCode string `json:"measurement_unit_code"`
	Location            string `json:"location"`
	Status              int    `json:"status"`
}

// Measurement is a single reading at a point.
type Measurement struct {
	UUID               string         `json:"uuid"`
	MeasurementPointID int            `json:"measurement_point_id"`
	PointSequence      int            `json:"point_sequence"`
	Data               map[string]any `json:"data"`
	Status             string         `json:"status"`
	Notes              string         `json:"notes"`
	CreatedAt          time.Time      `json:"created_at"`
	FileURL            *string        `json:"file_url,omitempty"`
}

// Route is an inspection route definition.
type Route struct {
	UUID        string `json:"uuid"`
	Name        string `json:"name"`
	Description string `json:"description"`
}

// RouteExecution is a single run of a route.
type RouteExecution struct {
	UUID        string     `json:"uuid"`
	RouteUUID   string     `json:"route_uuid"`
	Status      string     `json:"status"`
	StartedAt   *time.Time `json:"started_at"`
	CompletedAt *time.Time `json:"completed_at"`
	SessionID   string     `json:"session_id"`
}

// ItemResponse is a response submitted against a route item during an execution.
type ItemResponse struct {
	UUID          string         `json:"uuid"`
	RouteItemUUID string         `json:"route_item_uuid"`
	Data          map[string]any `json:"data"`
	Notes         string         `json:"notes"`
	Status        int            `json:"status"`
	CreatedAt     time.Time      `json:"created_at"`
}

// RouteDetail is a raw route payload (items + metadata) returned by Routes.Get.
type RouteDetail struct {
	UUID        string         `json:"uuid"`
	Name        string         `json:"name"`
	Description string         `json:"description"`
	Items       []map[string]any `json:"items"`
	Extra       map[string]any `json:"-"`
}
