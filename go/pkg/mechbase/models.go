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
	UUID          string  `json:"uuid"`
	AssetID       *int    `json:"asset_id"`
	Name          string  `json:"name"`
	SectionID     *int    `json:"section_id"`
	ZoneID        *int    `json:"zone_id"`
	MachineClass  string  `json:"machine_class"`
	EquipmentType string  `json:"equipment_type"`
	Status        int     `json:"status"`
	ExternalID    *string `json:"external_id"`
}

// MeasurementPoint is a measurement location on an asset.
type MeasurementPoint struct {
	UUID                string  `json:"uuid"`
	PointID             *int    `json:"point_id"`
	Name                string  `json:"name"`
	AssetID             *int    `json:"asset_id"`
	TransducerType      string  `json:"transducer_type"`
	MeasurementUnitCode string  `json:"measurement_unit_code"`
	Location            string  `json:"location"`
	Status              int     `json:"status"`
	ExternalID          *string `json:"external_id"`
	// Instructions is the effective working instruction (the point's override,
	// else the transducer-type default) as sanitized HTML; embedded image URLs
	// are absolute. The server always populates it.
	Instructions string `json:"instructions"`
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
	ExternalID         *string        `json:"external_id"`
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
	UUID        string           `json:"uuid"`
	Name        string           `json:"name"`
	Description string           `json:"description"`
	Items       []map[string]any `json:"items"`
	Extra       map[string]any   `json:"-"`
}

// Section is a registry section.
type Section struct {
	UUID       string  `json:"uuid"`
	SectionID  *int    `json:"section_id"`
	Name       string  `json:"name"`
	ExternalID *string `json:"external_id"`
}

// Zone is a registry zone within a section.
type Zone struct {
	UUID       string  `json:"uuid"`
	ZoneID     *int    `json:"zone_id"`
	Name       string  `json:"name"`
	SectionID  *int    `json:"section_id"`
	ExternalID *string `json:"external_id"`
}

// DeleteResult is returned by DELETE endpoints.
type DeleteResult struct {
	Deleted bool   `json:"deleted"`
	UUID    string `json:"uuid"`
}

// BatchItemResult is the per-item outcome of a measurement batch.
type BatchItemResult struct {
	Index              int     `json:"index"`
	Status             string  `json:"status"`
	MeasurementPointID *int    `json:"measurement_point_id"`
	PointSequence      *int    `json:"point_sequence"`
	UUID               *string `json:"uuid"`
	ExternalID         *string `json:"external_id"`
	Detail             *string `json:"detail"`
}

// BatchResult is the response from a measurement batch push.
type BatchResult struct {
	Created    int               `json:"created"`
	Duplicates int               `json:"duplicates"`
	Errors     int               `json:"errors"`
	Results    []BatchItemResult `json:"results"`
}

// FileAttachment is a file attached to a measurement.
type FileAttachment struct {
	UUID      string `json:"uuid"`
	Name      string `json:"name"`
	Kind      string `json:"kind"`
	FileURL   string `json:"file_url"`
	CreatedAt time.Time `json:"created_at"`
}

// MeasurementResult is the per-item outcome of a maintnode measurement push.
type MeasurementResult struct {
	MappingUUID     string  `json:"mapping_uuid"`
	OK              bool    `json:"ok"`
	MeasurementUUID *string `json:"measurement_uuid"`
	LocalUUID       string  `json:"local_uuid"`
	Error           string  `json:"error"`
}

// cursorEnvelope is the cursor-paginated wrapper for history iteration.
type cursorEnvelope[T any] struct {
	Items      []T     `json:"items"`
	NextCursor *string `json:"next_cursor"`
}
