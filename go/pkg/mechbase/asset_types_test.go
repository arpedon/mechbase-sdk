package mechbase

import (
	"context"
	"encoding/json"
	"io"
	"mime"
	"mime/multipart"
	"net/http"
	"strings"
	"testing"
)

const atJSON = `{"uuid":"u1","code":"ABB-1","name":"Motor","manufacturer":"ABB","checklist":[{"item_type":"pass_fail"}],"external_id":null,"asset_count":2,"document_count":1}`

func TestAssetTypes(t *testing.T) {
	n := 0
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		n++
		switch n {
		case 1:
			expect(t, r, "GET", iid+"/asset-types", "")
			_, _ = w.Write([]byte("[" + atJSON + "]"))
		case 2:
			expect(t, r, "GET", iid+"/asset-types/ABB-1", "")
			_, _ = w.Write([]byte(atJSON))
		case 3:
			if b := expect(t, r, "PUT", iid+"/asset-types", ""); string(b) != `{"code":"ABB-1","name":"Motor"}` {
				t.Fatalf("body %s", b)
			}
			_, _ = w.Write([]byte(atJSON))
		case 4:
			if b := expect(t, r, "PATCH", iid+"/asset-types/ABB-1", ""); string(b) != `{"manufacturer":"ABB"}` {
				t.Fatalf("body %s", b)
			}
			_, _ = w.Write([]byte(atJSON))
		case 5:
			expect(t, r, "DELETE", iid+"/asset-types/ABB-1", "")
			_, _ = w.Write([]byte(`{"deleted":true,"uuid":"u1"}`))
		case 6:
			expect(t, r, "GET", iid+"/asset-types/ABB-1/documents", "")
			_, _ = w.Write([]byte(`[{"uuid":"d1","name":"m.pdf","kind":"manual","url":"/d","created_at":"2026-01-01T00:00:00Z"}]`))
		case 7:
			assertAuth(t, r)
			if r.Method != "POST" || r.URL.Path != iid+"/asset-types/ABB-1/documents" {
				t.Fatalf("%s %s", r.Method, r.URL.Path)
			}
			_, params, _ := mime.ParseMediaType(r.Header.Get("Content-Type"))
			mr := multipart.NewReader(r.Body, params["boundary"])
			got := map[string]string{}
			for {
				p, err := mr.NextPart()
				if err != nil {
					break
				}
				b, _ := io.ReadAll(p)
				got[p.FormName()] = string(b)
			}
			if got["kind"] != "manual" || got["uuid"] != "d1" || got["file"] != "PDF" {
				t.Fatalf("%v", got)
			}
			w.WriteHeader(201)
			_, _ = w.Write([]byte(`{"uuid":"d1","name":"document.pdf","kind":"manual","url":"/d","created_at":"2026-01-01T00:00:00Z"}`))
		case 8:
			expect(t, r, "DELETE", iid+"/asset-types/ABB-1/documents/d1", "")
			w.WriteHeader(204)
		}
	})
	defer stop()
	ctx, a := context.Background(), inst(c).AssetTypes
	if l, err := a.List(ctx); err != nil || l[0].Code != "ABB-1" || l[0].AssetCount != 2 || len(l[0].Checklist) != 1 {
		t.Fatalf("%v %+v", err, l)
	}
	if g, err := a.Get(ctx, "ABB-1"); err != nil || g.Name != "Motor" {
		t.Fatalf("%v %+v", err, g)
	}
	if _, err := a.Upsert(ctx, AssetTypeInput{Code: ptr("ABB-1"), Name: ptr("Motor")}); err != nil {
		t.Fatal(err)
	}
	if _, err := a.Update(ctx, "ABB-1", AssetTypeInput{Manufacturer: ptr("ABB")}); err != nil {
		t.Fatal(err)
	}
	if d, err := a.Delete(ctx, "ABB-1"); err != nil || !d.Deleted {
		t.Fatalf("%v %+v", err, d)
	}
	if l, err := a.Documents(ctx, "ABB-1"); err != nil || l[0].Kind != "manual" {
		t.Fatalf("%v %+v", err, l)
	}
	if d, err := a.AddDocument(ctx, "ABB-1", strings.NewReader("PDF"), "", "manual", "d1"); err != nil || d.UUID != "d1" {
		t.Fatalf("%v %+v", err, d)
	}
	if err := a.DeleteDocument(ctx, "ABB-1", "d1"); err != nil {
		t.Fatal(err)
	}
}

func TestAssetTypeNullableAndChecklist(t *testing.T) {
	n := 0
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		n++
		asset := `{"uuid":"a","asset_id":7,"name":"P","machine_class":"","equipment_type":"","status":1,"asset_type":"ABB-1"}`
		switch n {
		case 1:
			if b := expect(t, r, "PATCH", iid+"/assets/7", ""); string(b) != `{"asset_type":null}` {
				t.Fatalf("clear: %s", b)
			}
			_, _ = w.Write([]byte(`{"uuid":"a","asset_id":7,"name":"P","status":1,"asset_type":null}`))
		case 2:
			if b := expect(t, r, "PATCH", iid+"/assets/7", ""); string(b) != `{"asset_type":"ABB-1"}` {
				t.Fatalf("set: %s", b)
			}
			_, _ = w.Write([]byte(asset))
		case 3:
			if b := expect(t, r, "PATCH", iid+"/assets/7", ""); string(b) != `{"name":"x"}` {
				t.Fatalf("omit: %s", b)
			}
			_, _ = w.Write([]byte(asset))
		case 4:
			expect(t, r, "POST", iid+"/assets/7/checklist", "")
			_, _ = w.Write([]byte(`{"route_uuid":"r1","created":true}`))
		case 5:
			if b := expect(t, r, "PATCH", iid+"/zones/2", ""); string(b) != `{"guest_view":false}` {
				t.Fatalf("zone: %s", b)
			}
			_, _ = w.Write([]byte(`{"uuid":"z","name":"Z","guest_view":false}`))
		}
	})
	defer stop()
	ctx, as := context.Background(), inst(c).Assets
	if a, err := as.Update(ctx, 7, AssetInput{ClearAssetType: true}); err != nil || a.AssetType != nil {
		t.Fatalf("%v %+v", err, a)
	}
	if a, err := as.Update(ctx, 7, AssetInput{AssetType: ptr("ABB-1")}); err != nil || *a.AssetType != "ABB-1" {
		t.Fatalf("%v %+v", err, a)
	}
	if _, err := as.Update(ctx, 7, AssetInput{Name: ptr("x")}); err != nil {
		t.Fatal(err)
	}
	if cl, err := as.EnsureChecklist(ctx, 7); err != nil || cl.RouteUUID != "r1" || !cl.Created {
		t.Fatalf("%v %+v", err, cl)
	}
	f := false
	if z, err := inst(c).Zones.Update(ctx, 2, ZoneInput{GuestView: &f}); err != nil || z.GuestView {
		t.Fatalf("%v %+v", err, z)
	}
}

func TestAssetTypeEscapedCodeAndClearChecklist(t *testing.T) {
	n := 0
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		n++
		if r.URL.EscapedPath() != iid+"/asset-types/QB%23old" || r.URL.RawQuery != "" {
			t.Fatalf("path: %s ?%s", r.URL.EscapedPath(), r.URL.RawQuery)
		}
		if b, _ := io.ReadAll(r.Body); string(b) != `{"checklist":[]}` {
			t.Fatalf("body: %s", b)
		}
		_, _ = w.Write([]byte(atJSON))
	})
	defer stop()
	empty := []map[string]any{}
	if _, err := inst(c).AssetTypes.Update(context.Background(), "QB#old", AssetTypeInput{Checklist: &empty}); err != nil {
		t.Fatal(err)
	}
	if n != 1 {
		t.Fatalf("requests: %d", n)
	}
}

func TestAssetInputFedFromOmitSetClear(t *testing.T) {
	for want, in := range map[string]AssetInput{
		`{}`:                                  AssetInput{},
		`{"fed_from":7}`:                      AssetInput{FedFrom: ptr(7)},
		`{"fed_from":null}`:                   AssetInput{ClearFedFrom: true},
		`{"asset_type":null,"fed_from":null}`: AssetInput{ClearAssetType: true, ClearFedFrom: true},
	} {
		if b, err := json.Marshal(in); err != nil || string(b) != want {
			t.Fatalf("got %s (%v), want %s", b, err, want)
		}
	}
}
