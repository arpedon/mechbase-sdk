package mechbase

import (
	"bytes"
	"context"
	"errors"
	"io"
	"net/http"
	"strings"
	"testing"
)

const iid = "/api/installations/7"

// expect asserts method+path (+query) and returns the request body.
func expect(t *testing.T, r *http.Request, method, path, query string) []byte {
	t.Helper()
	assertAuth(t, r)
	if r.Method != method || r.URL.Path != path || r.URL.RawQuery != query {
		t.Fatalf("got %s %s?%s, want %s %s?%s", r.Method, r.URL.Path, r.URL.RawQuery, method, path, query)
	}
	b, _ := io.ReadAll(r.Body)
	return b
}

func inst(c *Client) *Installation_ { return c.ForInstallation(7) }

func TestMeUnitPrefs(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		expect(t, r, "GET", "/api/me/", "")
		_, _ = w.Write([]byte(`{"user":{"id":1},"unit_prefs":{"acceleration":"g","velocity":"mm/s","temperature":"C","pressure":"bar","frequency":"Hz"},"installations":[],"current_installation_id":null}`))
	})
	defer stop()
	me, err := c.Me(context.Background())
	if err != nil || me.UnitPrefs.Velocity != "mm/s" {
		t.Fatalf("%v %+v", err, me)
	}
}

func TestPointContext(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		expect(t, r, "GET", iid+"/measurement-points/5/context", "")
		_, _ = w.Write([]byte(`{"data_key":"velocity","unit":"mm/s","running":true,"limits":{"minor":2.5,"major":null},"week":[{"t":"2026-01-01T00:00:00Z","v":1.5}]}`))
	})
	defer stop()
	out, err := inst(c).MeasurementPoints.Context(context.Background(), 5)
	if err != nil || out.DataKey != "velocity" || *out.Running != true || *out.Limits.Minor != 2.5 || out.Limits.Major != nil || out.Week[0].V != 1.5 {
		t.Fatalf("%v %+v", err, out)
	}
}

func TestPointPhotoAddKeepReference(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		body := expect(t, r, "POST", iid+"/measurement-points/5/photos/", "")
		if !strings.HasPrefix(r.Header.Get("Content-Type"), "multipart/form-data") {
			t.Fatalf("content-type %q", r.Header.Get("Content-Type"))
		}
		for _, want := range []string{`name="uuid"`, "u-1", `name="keep_reference"`, "true", `name="file"; filename="a.jpg"`, "JPEG"} {
			if !bytes.Contains(body, []byte(want)) {
				t.Fatalf("body missing %q", want)
			}
		}
		w.WriteHeader(201)
		_, _ = w.Write([]byte(`{"uuid":"u-1","name":"a.jpg","kind":"photo","file_url":"/f","created_at":"2026-01-01T00:00:00Z"}`))
	})
	defer stop()
	out, err := inst(c).MeasurementPoints.AddPhoto(context.Background(), 5, "a.jpg", strings.NewReader("JPEG"), "u-1")
	if err != nil || out.UUID != "u-1" {
		t.Fatalf("%v %+v", err, out)
	}
}

func TestAssetPhotoAdd(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		body := expect(t, r, "POST", iid+"/assets/3/photos/", "")
		if bytes.Contains(body, []byte("keep_reference")) || !bytes.Contains(body, []byte("JPEG")) {
			t.Fatalf("body %s", body)
		}
		w.WriteHeader(201)
		_, _ = w.Write([]byte(`{"uuid":"p","name":"photo","kind":"photo","file_url":"/f","created_at":"2026-01-01T00:00:00Z"}`))
	})
	defer stop()
	out, err := inst(c).Assets.AddPhoto(context.Background(), 3, "", strings.NewReader("JPEG"), "")
	if err != nil || out.UUID != "p" {
		t.Fatalf("%v %+v", err, out)
	}
}

func TestPhotoDeletes(t *testing.T) {
	var got []string
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		expect(t, r, "DELETE", r.URL.Path, "")
		got = append(got, r.URL.Path)
		w.WriteHeader(204)
	})
	defer stop()
	ctx := context.Background()
	if err := inst(c).Assets.DeletePhoto(ctx, 3, "pu"); err != nil {
		t.Fatal(err)
	}
	if err := inst(c).MeasurementPoints.DeletePhoto(ctx, 5, "pu"); err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 || got[0] != iid+"/assets/3/photos/pu" || got[1] != iid+"/measurement-points/5/photos/pu" {
		t.Fatalf("paths %v", got)
	}
}

func TestSetReferencePhoto(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		body := expect(t, r, "PUT", iid+"/measurement-points/5/reference-photo", "")
		if strings.TrimSpace(string(body)) != `{"uuid":"pu"}` {
			t.Fatalf("body %s", body)
		}
		_, _ = w.Write([]byte(`{"uuid":"x","name":"P","reference_photo_uuid":"pu","photos":[{"uuid":"pu","url":"/u"}],"display_units":{"velocity":{"native":"mm/s","unit":"in/s","scale":0.0394,"offset":0}}}`))
	})
	defer stop()
	out, err := inst(c).MeasurementPoints.SetReferencePhoto(context.Background(), 5, "pu")
	if err != nil || *out.ReferencePhotoUUID != "pu" || out.Photos[0].URL != "/u" || out.DisplayUnits["velocity"].Unit != "in/s" {
		t.Fatalf("%v %+v", err, out)
	}
}

func TestLegacyRedirects(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		expect(t, r, "GET", iid+"/legacy-redirects", "")
		_, _ = w.Write([]byte(`{"items":[{"legacy_url":"/old","mp_uuid":"m","mp_path":"/new","installation_id":7,"asset_id":1,"point_id":null}],"total":1}`))
	})
	defer stop()
	out, err := inst(c).LegacyRedirects(context.Background())
	if err != nil || out.Total != 1 || out.Items[0].MPPath != "/new" || out.Items[0].PointID != nil {
		t.Fatalf("%v %+v", err, out)
	}
}

func TestExecutionCancel(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		expect(t, r, "POST", iid+"/executions/e-1/cancel", "")
		_, _ = w.Write([]byte(`{"uuid":"e-1","route_uuid":"r","status":"cancelled"}`))
	})
	defer stop()
	out, err := inst(c).Routes.Execution("e-1").Cancel(context.Background())
	if err != nil || out.Status != "cancelled" {
		t.Fatalf("%v %+v", err, out)
	}
}

func TestExecutionCancelConflict(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(409)
		_, _ = w.Write([]byte(`{"detail":"has answers"}`))
	})
	defer stop()
	_, err := inst(c).Routes.Execution("e-1").Cancel(context.Background())
	if !errors.Is(err, ErrConflict) {
		t.Fatalf("err = %v", err)
	}
}

func TestFindingsList(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		expect(t, r, "GET", iid+"/findings/", "asset_id=2&cursor=c1&limit=10&point_external_id=P-1&status=open")
		_, _ = w.Write([]byte(`{"items":[{"uuid":"f1","status":"open","fault_type":"imbalance","severity":"high","evidence":{"k":1},"due_by":"2026-02-01","created_at":"2026-01-01T00:00:00Z"}],"next_cursor":"c2"}`))
	})
	defer stop()
	out, err := inst(c).Findings.List(context.Background(), ListFindingsOptions{Cursor: "c1", Limit: 10, Status: "open", AssetID: 2, PointExternalID: "P-1"})
	if err != nil || len(out.Items) != 1 || out.Items[0].FaultType != "imbalance" || *out.NextCursor != "c2" || *out.Items[0].DueBy != "2026-02-01" {
		t.Fatalf("%v %+v", err, out)
	}
}

func TestFindingGet(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		expect(t, r, "GET", iid+"/findings/f1/", "")
		_, _ = w.Write([]byte(`{"uuid":"f1","status":"open","web_url":"/w"}`))
	})
	defer stop()
	out, err := inst(c).Findings.Get(context.Background(), "f1")
	if err != nil || out.WebURL != "/w" {
		t.Fatalf("%v %+v", err, out)
	}
}

func TestFindingSetStatus(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		body := expect(t, r, "POST", iid+"/findings/f1/status/", "")
		if strings.TrimSpace(string(body)) != `{"status":"closed","work_order_ref":"WO-9"}` {
			t.Fatalf("body %s", body)
		}
		_, _ = w.Write([]byte(`{"uuid":"f1","status":"closed","work_order_ref":"WO-9"}`))
	})
	defer stop()
	out, err := inst(c).Findings.SetStatus(context.Background(), "f1", "closed", "WO-9")
	if err != nil || out.Status != "closed" {
		t.Fatalf("%v %+v", err, out)
	}
}

func TestExportCreate(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		body := expect(t, r, "POST", iid+"/analytics/exports/", "")
		if strings.TrimSpace(string(body)) != `{"dataset":"measurements","filters":{"asset_id":4}}` {
			t.Fatalf("body %s", body)
		}
		w.WriteHeader(202)
		_, _ = w.Write([]byte(`{"job_uuid":"j1","state":"queued","status_url":"/s"}`))
	})
	defer stop()
	id := 4
	out, err := inst(c).Exports.Create(context.Background(), ExportInput{Dataset: "measurements", Filters: &ExportFilters{AssetID: &id}})
	if err != nil || out.JobUUID != "j1" || out.State != "queued" {
		t.Fatalf("%v %+v", err, out)
	}
}

func TestExportStatus(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		expect(t, r, "GET", iid+"/analytics/exports/j1/", "")
		_, _ = w.Write([]byte(`{"job_uuid":"j1","dataset":"measurements","file_format":"csv","state":"done","row_count":3,"byte_size":99,"download_url":"/d?sig=abc","created_at":"2026-01-01T00:00:00Z"}`))
	})
	defer stop()
	out, err := inst(c).Exports.Status(context.Background(), "j1")
	if err != nil || out.State != "done" || *out.RowCount != 3 || *out.DownloadURL != "/d?sig=abc" {
		t.Fatalf("%v %+v", err, out)
	}
}

func TestExportDownload(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == iid+"/analytics/exports/j1/" {
			_, _ = w.Write([]byte(`{"job_uuid":"j1","dataset":"measurements","file_format":"csv","state":"done","download_url":"https://elsewhere.test/d?sig=abc","created_at":"2026-01-01T00:00:00Z"}`))
			return
		}
		expect(t, r, "GET", iid+"/analytics/exports/j1/download/", "sig=abc")
		_, _ = w.Write([]byte("a,b\n1,2\n"))
	})
	defer stop()
	var buf bytes.Buffer
	n, err := inst(c).Exports.Download(context.Background(), "j1", &buf)
	if err != nil || n != 8 || buf.String() != "a,b\n1,2\n" {
		t.Fatalf("%v %d %q", err, n, buf.String())
	}
}

func TestExportDownloadGone(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == iid+"/analytics/exports/j1/" {
			_, _ = w.Write([]byte(`{"job_uuid":"j1","dataset":"measurements","file_format":"csv","state":"done","download_url":"/d?sig=x","created_at":"2026-01-01T00:00:00Z"}`))
			return
		}
		w.WriteHeader(410)
		_, _ = w.Write([]byte(`{"detail":"expired"}`))
	})
	defer stop()
	_, err := inst(c).Exports.Download(context.Background(), "j1", io.Discard)
	var ae *APIError
	if !errors.As(err, &ae) || ae.Status != 410 || ae.Detail != "expired" {
		t.Fatalf("err = %v", err)
	}
}

func TestSetHotspots(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		body := expect(t, r, "PATCH", iid+"/measurements/m1/hotspots/", "")
		if strings.TrimSpace(string(body)) != `{"hot_clusters":[{"cx_pct":10,"cy_pct":20,"max_temp_c":90.5,"delta_t_c":15,"severity":2,"source":"manual"}]}` {
			t.Fatalf("body %s", body)
		}
		_, _ = w.Write([]byte(`{"uuid":"m1","measurement_point_id":5,"point_sequence":1,"data":{},"status":"ok","notes":"","created_at":"2026-01-01T00:00:00Z"}`))
	})
	defer stop()
	out, err := inst(c).Measurements.SetHotspots(context.Background(), "m1", []HotCluster{{CxPct: 10, CyPct: 20, MaxTempC: 90.5, DeltaTC: 15, Severity: 2, Source: "manual"}})
	if err != nil || out.UUID != "m1" {
		t.Fatalf("%v %+v", err, out)
	}
}

func TestRevokeToken(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		expect(t, r, "POST", "/api/auth/token/revoke", "")
		_, _ = w.Write([]byte(`{"revoked":true}`))
	})
	defer stop()
	if err := c.RevokeToken(context.Background()); err != nil {
		t.Fatal(err)
	}
}
