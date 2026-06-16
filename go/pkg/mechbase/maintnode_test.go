package mechbase

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestMaintNodePush(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "" {
			t.Fatalf("unexpected auth header: %s", r.Header.Get("Authorization"))
		}
		switch r.URL.Path {
		case "/api/maintnode/node-1/config/":
			_, _ = w.Write([]byte(`"ssh: abc"`))
		case "/api/maintnode/node-1/measurements/":
			_, _ = w.Write([]byte(`[{"mapping_uuid":"map-1","ok":true,"measurement_uuid":"m-1","local_uuid":"L1","error":""}]`))
		default:
			t.Fatalf("unexpected %s", r.URL.Path)
		}
	}))
	defer srv.Close()

	node := NewMaintNode("node-1", srv.URL)
	cfg, err := node.Config(context.Background())
	if err != nil || cfg != "ssh: abc" {
		t.Fatalf("config: %q %v", cfg, err)
	}
	res, err := node.PushMeasurements(context.Background(), []MaintNodeMeasurementInput{
		{MappingUUID: "map-1", Data: map[string]any{"rms": 1.0}},
	})
	if err != nil || !res[0].OK {
		t.Fatalf("push: %+v %v", res, err)
	}
}
