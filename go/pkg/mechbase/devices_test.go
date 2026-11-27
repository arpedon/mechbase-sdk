package mechbase

import (
	"context"
	"net/http"
	"testing"
)

const devJSON = `{"node_uuid":"n1","name":"Node A","is_online":true,"last_seen_at":null,"claimed_at":null,"health":{"cpu_usage":95},"health_warnings":["CPU 95%"],"health_url":null,"groups":[{"uuid":"g1","name":"hat","hardware_type":"hat","hardware_config":{},"interval":600,"sample_rate":null,"samples":null,"channels":[{"uuid":"m1","channel":3,"point_id":1,"point_name":"DE","asset_id":1,"asset_name":"Pump","sensor":"accelerometer","last_seen_at":null,"stale_since":null,"state":"waiting"}]}],"tunnels":[{"uuid":"t1","name":"logo","label":"LOGO","kind":"http","staff_only":false,"web_url":"https://x/t1/","local_port":null,"visitor_url":null}]}`
const srcJSON = `{"uuid":"s1","source_type":"maintnode","device_id":"n1","device_name":"Node A","group":{"uuid":"g1","name":"hat","hardware_type":"hat"},"channel":3,"sensor":"accelerometer","sensor_config":{"sensitivity":100},"is_active":true,"last_seen_at":null,"stale_since":null}`

func TestDevicesListRenameGroup(t *testing.T) {
	n := 0
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		n++
		switch n {
		case 1:
			expect(t, r, "GET", iid+"/devices", "")
			_, _ = w.Write([]byte("[" + devJSON + "]"))
		case 2:
			if b := expect(t, r, "PATCH", iid+"/devices/n1", ""); string(b) != `{"name":"Boiler"}` {
				t.Fatalf("body %s", b)
			}
			_, _ = w.Write([]byte(devJSON))
		case 3:
			if b := expect(t, r, "PATCH", iid+"/devices/n1/groups/g1", ""); string(b) != `{"interval":120}` {
				t.Fatalf("body %s", b)
			}
			_, _ = w.Write([]byte(devJSON))
		}
	})
	defer stop()
	ctx := context.Background()
	l, err := inst(c).Devices.List(ctx)
	if err != nil || l[0].Groups[0].Channels[0].State != "waiting" || *l[0].Tunnels[0].WebURL != "https://x/t1/" || l[0].HealthURL != nil {
		t.Fatalf("%v %+v", err, l)
	}
	if _, err := inst(c).Devices.Rename(ctx, "n1", "Boiler"); err != nil {
		t.Fatal(err)
	}
	if _, err := inst(c).Devices.UpdateGroup(ctx, "n1", "g1", map[string]any{"interval": 120}); err != nil {
		t.Fatal(err)
	}
}

func TestSourcesCRUD(t *testing.T) {
	n := 0
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		n++
		switch n {
		case 1:
			expect(t, r, "GET", iid+"/measurement-points/1/sources", "")
			_, _ = w.Write([]byte("[" + srcJSON + "]"))
		case 2:
			if b := expect(t, r, "POST", iid+"/measurement-points/1/sources", ""); string(b) != `{"mqtt_device_id":"SN-1","source_type":"mqtt"}` {
				t.Fatalf("body %s", b)
			}
			w.WriteHeader(201)
			_, _ = w.Write([]byte(srcJSON))
		case 3:
			expect(t, r, "PATCH", iid+"/measurement-points/1/sources/s1", "")
			_, _ = w.Write([]byte(srcJSON))
		case 4:
			expect(t, r, "DELETE", iid+"/measurement-points/1/sources/s1", "")
			w.WriteHeader(204)
		}
	})
	defer stop()
	ctx := context.Background()
	s := inst(c).Sources
	l, err := s.List(ctx, 1)
	if err != nil || *l[0].Channel != 3 || l[0].Group.Name != "hat" {
		t.Fatalf("%v %+v", err, l)
	}
	if _, err := s.Create(ctx, 1, map[string]any{"source_type": "mqtt", "mqtt_device_id": "SN-1"}); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Update(ctx, 1, "s1", map[string]any{"sensitivity": 50}); err != nil {
		t.Fatal(err)
	}
	if err := s.Delete(ctx, 1, "s1"); err != nil {
		t.Fatal(err)
	}
}

func TestStaffTunnelsAndVisitorFile(t *testing.T) {
	n := 0
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		n++
		switch n {
		case 1:
			expect(t, r, "GET", "/api/tunnels", "")
			_, _ = w.Write([]byte(`[{"uuid":"t2","name":"ssh","label":"SSH","kind":"stcp","staff_only":true,"web_url":null,"local_port":22,"visitor_url":"https://x/v","installation_id":7,"installation_name":"Plant","node_uuid":"n1","device_name":"Node A"}]`))
		case 2:
			expect(t, r, "GET", "/api/tunnels/t2/visitor.toml", "")
			w.Header().Set("Content-Type", "application/toml")
			_, _ = w.Write([]byte("serverAddr = \"frp\"\n"))
		case 3:
			w.WriteHeader(403)
			_, _ = w.Write([]byte(`{"detail":"Staff only."}`))
		}
	})
	defer stop()
	ctx := context.Background()
	l, err := c.Tunnels(ctx)
	if err != nil || *l[0].LocalPort != 22 || l[0].DeviceName != "Node A" || *l[0].InstallationID != 7 {
		t.Fatalf("%v %+v", err, l)
	}
	b, err := c.TunnelVisitorFile(ctx, "t2")
	if err != nil || string(b) != "serverAddr = \"frp\"\n" {
		t.Fatalf("%v %q", err, b)
	}
	if _, err := c.TunnelVisitorFile(ctx, "t2"); err == nil {
		t.Fatal("want 403 error")
	}
}
