package mechbase

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func newTestServer(t *testing.T, h http.HandlerFunc) (*Client, func()) {
	t.Helper()
	srv := httptest.NewServer(h)
	c := New("tok", srv.URL)
	return c, srv.Close
}

func assertAuth(t *testing.T, r *http.Request) {
	t.Helper()
	if got := r.Header.Get("Authorization"); got != "Bearer tok" {
		t.Fatalf("authorization header = %q", got)
	}
	if got := r.Header.Get("User-Agent"); got != "mechbase-go/0.1" {
		t.Fatalf("user-agent = %q", got)
	}
}

func TestMe(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		assertAuth(t, r)
		if r.URL.Path != "/api/me/" {
			t.Fatalf("path = %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{
			"user": {"id":1,"username":"u","full_name":"U U","email":"u@u"},
			"installations": [{"installation_id":2012,"name":"Plant"}],
			"current_installation_id": 2012
		}`))
	})
	defer stop()

	me, err := c.Me(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if me.User.Username != "u" {
		t.Errorf("username = %s", me.User.Username)
	}
	if me.CurrentInstallationID != 2012 {
		t.Errorf("current installation = %d", me.CurrentInstallationID)
	}
	if len(me.Installations) != 1 || me.Installations[0].Name != "Plant" {
		t.Errorf("installations = %+v", me.Installations)
	}
}

func TestListAssets(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/installations/2012/assets" {
			t.Fatalf("path = %s", r.URL.Path)
		}
		_, _ = w.Write([]byte(`{
			"items":[{"uuid":"u-1","asset_id":1,"name":"Pump 1","zone_id":1,"machine_class":"II","status":1}],
			"total":1,"limit":50,"offset":0
		}`))
	})
	defer stop()

	assets, err := c.ForInstallation(2012).Assets.List(context.Background(), ListAssetsOptions{})
	if err != nil {
		t.Fatal(err)
	}
	if len(assets) != 1 || assets[0].Name != "Pump 1" {
		t.Fatalf("assets = %+v", assets)
	}
}

func TestCreateMeasurementJSON(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/installations/2012/measurements/" {
			t.Fatalf("path = %s", r.URL.Path)
		}
		if ct := r.Header.Get("Content-Type"); ct != "application/json" {
			t.Fatalf("content-type = %s", ct)
		}
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		if body["measurement_point_id"].(float64) != 1 {
			t.Fatalf("point id = %v", body["measurement_point_id"])
		}
		w.WriteHeader(201)
		_, _ = w.Write([]byte(`{
			"uuid":"m-1","measurement_point_id":1,"point_sequence":5,
			"data":{"rms":2.3},"status":"good","notes":"",
			"created_at":"2026-04-08T10:00:00Z","file_url":null
		}`))
	})
	defer stop()

	m, err := c.ForInstallation(2012).Measurements.Create(context.Background(), CreateMeasurementInput{
		PointID: 1,
		Data:    map[string]any{"rms": 2.3},
	})
	if err != nil {
		t.Fatal(err)
	}
	if m.PointSequence != 5 || m.Status != "good" {
		t.Fatalf("measurement = %+v", m)
	}
}

func TestStartExecutionAndRespond(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/api/installations/2012/routes/r-uuid/executions" && r.Method == "POST":
			w.WriteHeader(201)
			_, _ = w.Write([]byte(`{
				"uuid":"exec-uuid","route_uuid":"r-uuid","status":"in_progress",
				"started_at":"2026-04-08T10:00:00Z","completed_at":null,"session_id":"sess-uuid"
			}`))
		case r.URL.Path == "/api/installations/2012/executions/exec-uuid/responses" && r.Method == "POST":
			w.WriteHeader(201)
			_, _ = w.Write([]byte(`{
				"uuid":"resp-uuid","route_item_uuid":"item-uuid",
				"data":{"passed":true},"notes":"","status":1,
				"created_at":"2026-04-08T10:00:01Z"
			}`))
		default:
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
	})
	defer stop()

	exec, err := c.ForInstallation(2012).Routes.Start(context.Background(), "r-uuid")
	if err != nil {
		t.Fatal(err)
	}
	if exec.UUID != "exec-uuid" {
		t.Fatalf("exec uuid = %s", exec.UUID)
	}
	resp, err := exec.Respond(context.Background(), RespondInput{
		RouteItemUUID: "item-uuid",
		Data:          map[string]any{"passed": true},
	})
	if err != nil {
		t.Fatal(err)
	}
	if resp.Status != 1 {
		t.Fatalf("resp status = %d", resp.Status)
	}
}

func TestAuthErrorIsErrAuth(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(401)
		_, _ = w.Write([]byte(`{"detail":"nope"}`))
	})
	defer stop()

	_, err := c.Me(context.Background())
	if err == nil {
		t.Fatal("expected error")
	}
	if !errors.Is(err, ErrAuth) {
		t.Fatalf("expected ErrAuth, got %v", err)
	}
	var apiErr *APIError
	if !errors.As(err, &apiErr) || apiErr.Status != 401 || !strings.Contains(apiErr.Detail, "nope") {
		t.Fatalf("unexpected api error: %+v", apiErr)
	}
}
