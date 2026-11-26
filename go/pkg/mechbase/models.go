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
	UnitPrefs             UnitPrefs      `json:"unit_prefs"`
}

// UnitPrefs holds the user's preferred display unit per quantity.
type UnitPrefs struct {
	Acceleration string `json:"acceleration"`
	Velocity     string `json:"velocity"`
	Temperature  string `json:"temperature"`
	Pressure     string `json:"pressure"`
	Frequency    string `json:"frequency"`
}

// PhotoRef is a gallery photo on an asset or measurement point.
type PhotoRef struct {
	UUID string `json:"uuid"`
	URL  string `json:"url"`
}

// DisplayUnit converts a point's native unit to the user's display unit:
// display = native*Scale + Offset.
type DisplayUnit struct {
	Native string  `json:"native"`
	Unit   string  `json:"unit"`
	Scale  float64 `json:"scale"`
	Offset float64 `json:"offset"`
}

// Asset is a tracked machine.
type Asset struct {
	UUID          string     `json:"uuid"`
	AssetID       *int       `json:"asset_id"`
	Name          string     `json:"name"`
	SectionID     *int       `json:"section_id"`
	ZoneID        *int       `json:"zone_id"`
	MachineClass  string     `json:"machine_class"`
	EquipmentType string     `json:"equipment_type"`
	Status        int        `json:"status"`
	ExternalID    *string    `json:"external_id"`
	ImageURLs     []string   `json:"image_urls"`
	Photos        []PhotoRef `json:"photos"`
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
	Instructions string     `json:"instructions"`
	ImageURLs    []string   `json:"image_urls"`
	Photos       []PhotoRef `json:"photos"`
	// ReferencePhotoUUID is the explicit reference photo; nil means the first photo.
	ReferencePhotoUUID *string `json:"reference_photo_uuid"`
	// DisplayUnits is keyed by data key (e.g. "velocity").
	DisplayUnits map[string]DisplayUnit `json:"display_units"`
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
	UUID      string    `json:"uuid"`
	Name      string    `json:"name"`
	Kind      string    `json:"kind"`
	FileURL   string    `json:"file_url"`
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

// PointLimits are a point's alarm thresholds; nil means unset.
type PointLimits struct {
	Minor *float64 `json:"minor"`
	Major *float64 `json:"major"`
}

// TrendBin is one time-bucketed value of a point's trend.
type TrendBin struct {
	T time.Time `json:"t"`
	V float64   `json:"v"`
}

// PointContext is the trend/limits/running context for a measurement point.
type PointContext struct {
	DataKey    string       `json:"data_key"`
	Unit       string       `json:"unit"`
	Running    *bool        `json:"running"`
	RunningAt  *time.Time   `json:"running_at"`
	StaleSince *time.Time   `json:"stale_since"`
	Limits     *PointLimits `json:"limits"`
	Week       []TrendBin   `json:"week"`
}

// LegacyRedirect maps a legacy URL to a measurement point.
type LegacyRedirect struct {
	LegacyURL      string `json:"legacy_url"`
	MPUUID         string `json:"mp_uuid"`
	MPPath         string `json:"mp_path"`
	InstallationID int    `json:"installation_id"`
	AssetID        *int   `json:"asset_id"`
	PointID        *int   `json:"point_id"`
}

// LegacyRedirects is the response of LegacyRedirects.
type LegacyRedirects struct {
	Items []LegacyRedirect `json:"items"`
	Total int              `json:"total"`
}

// Finding is a diagnostic finding.
type Finding struct {
	UUID                  string         `json:"uuid"`
	Status                string         `json:"status"`
	FaultType             string         `json:"fault_type"`
	FaultTypeDisplay      string         `json:"fault_type_display"`
	Severity              string         `json:"severity"`
	RecommendedAction     string         `json:"recommended_action"`
	DueBy                 *string        `json:"due_by"`
	Comment               string         `json:"comment"`
	Evidence              map[string]any `json:"evidence"`
	WorkOrderRef          string         `json:"work_order_ref"`
	AcknowledgedAt        *time.Time     `json:"acknowledged_at"`
	ClosedAt              *time.Time     `json:"closed_at"`
	CreatedAt             time.Time      `json:"created_at"`
	UpdatedAt             time.Time      `json:"updated_at"`
	CreatedBy             *string        `json:"created_by"`
	AssetID               *int           `json:"asset_id"`
	AssetExternalID       *string        `json:"asset_external_id"`
	AssetName             string         `json:"asset_name"`
	PointID               *int           `json:"point_id"`
	PointExternalID       *string        `json:"point_external_id"`
	PointName             string         `json:"point_name"`
	PointLocation         string         `json:"point_location"`
	MeasurementUUID       *string        `json:"measurement_uuid"`
	MeasurementExternalID *string        `json:"measurement_external_id"`
	MeasurementTimestamp  *time.Time     `json:"measurement_timestamp"`
	WebURL                string         `json:"web_url"`
}

// FindingsPage is one cursor page of findings.
type FindingsPage struct {
	Items      []Finding `json:"items"`
	NextCursor *string   `json:"next_cursor"`
}

// ExportCreated is the 202 response of Exports.Create.
type ExportCreated struct {
	JobUUID   string `json:"job_uuid"`
	State     string `json:"state"`
	StatusURL string `json:"status_url"`
}

// ExportStatus is the state of an analytics export job.
type ExportStatus struct {
	JobUUID     string     `json:"job_uuid"`
	Dataset     string     `json:"dataset"`
	FileFormat  string     `json:"file_format"`
	State       string     `json:"state"`
	RowCount    *int       `json:"row_count"`
	ByteSize    *int       `json:"byte_size"`
	DownloadURL *string    `json:"download_url"`
	ExpiresAt   *time.Time `json:"expires_at"`
	Error       string     `json:"error"`
	CreatedAt   time.Time  `json:"created_at"`
}
