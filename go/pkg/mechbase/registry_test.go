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

func ptr[T any](v T) *T { return &v }
