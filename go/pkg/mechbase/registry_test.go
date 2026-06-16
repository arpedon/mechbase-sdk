package mechbase

import (
	"context"
	"errors"
	"net/http"
	"testing"
)

func TestAssetCRUD(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == "POST" && r.URL.Path == "/api/installations/2012/assets":
			w.WriteHeader(201)
			_, _ = w.Write([]byte(`{"uuid":"a-1","asset_id":7,"name":"Pump 7","section_id":3,"zone_id":2,"machine_class":"II","equipment_type":"pump","status":1,"external_id":"P-7"}`))
		case r.Method == "PATCH" && r.URL.Path == "/api/installations/2012/assets/7":
			_, _ = w.Write([]byte(`{"uuid":"a-1","asset_id":7,"name":"Pump 7c","section_id":3,"zone_id":2,"machine_class":"II","equipment_type":"pump","status":1,"external_id":"P-7"}`))
		case r.Method == "DELETE" && r.URL.Path == "/api/installations/2012/assets/7":
			if r.URL.Query().Get("cascade") != "true" {
				t.Fatalf("cascade=%s", r.URL.Query().Get("cascade"))
			}
			_, _ = w.Write([]byte(`{"deleted":true,"uuid":"a-1"}`))
		default:
			t.Fatalf("unexpected %s %s", r.Method, r.URL.Path)
		}
	})
	defer stop()

	assets := c.ForInstallation(2012).Assets
	created, err := assets.Create(context.Background(), AssetInput{Name: ptr("Pump 7"), ExternalID: ptr("P-7")})
	if err != nil || created.EquipmentType != "pump" {
		t.Fatalf("create: %+v %v", created, err)
	}
	updated, err := assets.Update(context.Background(), 7, AssetInput{Name: ptr("Pump 7c")})
	if err != nil || updated.Name != "Pump 7c" {
		t.Fatalf("update: %+v %v", updated, err)
	}
	del, err := assets.Delete(context.Background(), 7, true)
	if err != nil || !del.Deleted {
		t.Fatalf("delete: %+v %v", del, err)
	}
}

func TestConflictIsErrConflict(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(409)
		_, _ = w.Write([]byte(`{"detail":"dup"}`))
	})
	defer stop()
	_, err := c.ForInstallation(2012).Assets.Create(context.Background(), AssetInput{ExternalID: ptr("P-7")})
	if !errors.Is(err, ErrConflict) {
		t.Fatalf("want ErrConflict, got %v", err)
	}
}

func TestCreateBatch(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/installations/2012/measurements/batch/" {
			t.Fatalf("path %s", r.URL.Path)
		}
		_, _ = w.Write([]byte(`{"created":1,"duplicates":0,"errors":0,"results":[{"index":0,"status":"created","measurement_point_id":1,"point_sequence":5,"uuid":"m-1","external_id":"E-0","detail":null}]}`))
	})
	defer stop()
	res, err := c.ForInstallation(2012).Measurements.CreateBatch(context.Background(), []MeasurementInput{
		{MeasurementPointID: ptr(1), Data: map[string]any{"rms": 2.3}, ExternalID: ptr("E-0")},
	})
	if err != nil || res.Created != 1 || res.Results[0].Status != "created" {
		t.Fatalf("batch: %+v %v", res, err)
	}
}

func TestIterForPoint(t *testing.T) {
	page := 0
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		page++
		if page == 1 {
			_, _ = w.Write([]byte(`{"items":[{"uuid":"m-1","measurement_point_id":42,"point_sequence":1,"data":{},"status":"good","notes":"","created_at":"2026-01-01T00:00:01Z"}],"next_cursor":"CUR2"}`))
		} else {
			_, _ = w.Write([]byte(`{"items":[{"uuid":"m-2","measurement_point_id":42,"point_sequence":2,"data":{},"status":"good","notes":"","created_at":"2026-01-01T00:00:02Z"}],"next_cursor":null}`))
		}
	})
	defer stop()
	var got []string
	err := c.ForInstallation(2012).Measurements.IterForPoint(context.Background(), 42, IterOptions{PageSize: 1}, func(m Measurement) error {
		got = append(got, m.UUID)
		return nil
	})
	if err != nil || len(got) != 2 || got[1] != "m-2" {
		t.Fatalf("iter: %v %v", got, err)
	}
}

func ptr[T any](v T) *T { return &v }
