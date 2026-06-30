package mechbase

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// Issue #190 parity: the SDK sends X-Idempotency-Key on create + respond when
// IdempotencyKey is set, and omits it otherwise.
func TestIdempotencyKeyHeader(t *testing.T) {
	var createKey, respondKey string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case strings.HasSuffix(r.URL.Path, "/measurements/"):
			createKey = r.Header.Get("X-Idempotency-Key")
			w.WriteHeader(http.StatusCreated)
			_, _ = w.Write([]byte(`{"uuid":"m1","measurement_point_id":5,"point_sequence":1,"data":{"rms":1.2},"status":"good","notes":"","created_at":"2026-01-01T00:00:00Z"}`))
		case strings.HasSuffix(r.URL.Path, "/responses"):
			respondKey = r.Header.Get("X-Idempotency-Key")
			w.WriteHeader(http.StatusCreated)
			_, _ = w.Write([]byte(`{"uuid":"r1","route_item_uuid":"item-1","data":{"passed":true},"notes":"","status":1,"created_at":"2026-01-01T00:00:01Z"}`))
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer srv.Close()

	inst := New("t", srv.URL).ForInstallation(2012)
	ctx := context.Background()

	if _, err := inst.Measurements.Create(ctx, CreateMeasurementInput{
		PointID: 5, Data: map[string]any{"rms": 1.2}, IdempotencyKey: "k",
	}); err != nil {
		t.Fatal(err)
	}
	if createKey != "k" {
		t.Fatalf("create X-Idempotency-Key = %q, want %q", createKey, "k")
	}

	if _, err := inst.Routes.Execution("exec-1").Respond(ctx, RespondInput{
		RouteItemUUID: "item-1", Data: map[string]any{"passed": true}, IdempotencyKey: "k",
	}); err != nil {
		t.Fatal(err)
	}
	if respondKey != "k" {
		t.Fatalf("respond X-Idempotency-Key = %q, want %q", respondKey, "k")
	}

	// No key -> header absent.
	if _, err := inst.Measurements.Create(ctx, CreateMeasurementInput{
		PointID: 5, Data: map[string]any{"rms": 1.2},
	}); err != nil {
		t.Fatal(err)
	}
	if createKey != "" {
		t.Fatalf("unkeyed create should send no header, got %q", createKey)
	}
}
