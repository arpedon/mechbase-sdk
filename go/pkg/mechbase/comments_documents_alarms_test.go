package mechbase

import (
	"context"
	"io"
	"mime"
	"mime/multipart"
	"net/http"
	"strings"
	"testing"
)

const cJSON = `{"id":9,"body":"<p>x</p>","body_text":"x","author_name":"A","created_at":"2026-01-01T00:00:00Z","edited_at":null,"references":[{"point_id":5,"point_sequence":null}],"is_finding":false,"editable":true}`
const ruleJSON = `{"uuid":"r1","scope":"point","method":"threshold","data_key":"","effective_data_key":"velocity","direction":"high","minor_threshold":2.5,"major_threshold":null,"threshold_mode":"absolute","source":null}`

func TestCommentsList(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		expect(t, r, "GET", iid+"/assets/3/comments", "limit=10&offset=20")
		_, _ = w.Write([]byte(`{"items":[` + cJSON + `],"total":21,"limit":10,"offset":20}`))
	})
	defer stop()
	out, err := inst(c).Comments.List(context.Background(), 3, 10, 20)
	if err != nil || out.Total != 21 || out.Items[0].ID != 9 || out.Items[0].EditedAt != nil || *out.Items[0].References[0].PointID != 5 || out.Items[0].References[0].PointSequence != nil {
		t.Fatalf("%v %+v", err, out)
	}
}

func TestCommentsCreateUpdateDelete(t *testing.T) {
	n := 0
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		n++
		switch n {
		case 1:
			b := expect(t, r, "POST", iid+"/assets/3/comments", "")
			if string(b) != `{"body":"hi","references":[{"point_id":5,"point_sequence":2}]}` {
				t.Fatalf("body %s", b)
			}
			w.WriteHeader(201)
			_, _ = w.Write([]byte(cJSON))
		case 2:
			b := expect(t, r, "PATCH", iid+"/assets/3/comments/9", "")
			if string(b) != `{"body":"yo","references":[]}` {
				t.Fatalf("body %s", b)
			}
			_, _ = w.Write([]byte(cJSON))
		case 3:
			expect(t, r, "DELETE", iid+"/assets/3/comments/9", "")
			w.WriteHeader(204)
		}
	})
	defer stop()
	ctx, seq := context.Background(), 2
	cm := inst(c).Comments
	if out, err := cm.Create(ctx, 3, "hi", []CommentReferenceIn{{PointID: 5, PointSequence: &seq}}); err != nil || !out.Editable {
		t.Fatalf("%v %+v", err, out)
	}
	if _, err := cm.Update(ctx, 3, 9, "yo", nil); err != nil {
		t.Fatal(err)
	}
	if err := cm.Delete(ctx, 3, 9); err != nil {
		t.Fatal(err)
	}
}

func TestDocuments(t *testing.T) {
	n := 0
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		n++
		doc := `{"uuid":"d1","name":"document.pdf","kind":"manual","url":"/d","created_at":"2026-01-01T00:00:00Z"}`
		switch n {
		case 1:
			expect(t, r, "GET", iid+"/assets/3/documents", "")
			_, _ = w.Write([]byte("[" + doc + "]"))
		case 2:
			assertAuth(t, r)
			if r.Method != "POST" || r.URL.Path != iid+"/assets/3/documents" {
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
				if p.FormName() == "file" {
					got["filename"] = p.FileName()
				}
			}
			if got["kind"] != "manual" || got["uuid"] != "d1" || got["file"] != "PDF" || got["filename"] != "document.pdf" {
				t.Fatalf("%v", got)
			}
			w.WriteHeader(201)
			_, _ = w.Write([]byte(doc))
		case 3:
			expect(t, r, "DELETE", iid+"/assets/3/documents/d1", "")
			w.WriteHeader(204)
		}
	})
	defer stop()
	ctx, d := context.Background(), inst(c).Documents
	if l, err := d.List(ctx, 3); err != nil || l[0].Kind != "manual" {
		t.Fatalf("%v %+v", err, l)
	}
	if out, err := d.Add(ctx, 3, strings.NewReader("PDF"), "", "manual", "d1"); err != nil || out.UUID != "d1" {
		t.Fatalf("%v %+v", err, out)
	}
	if err := d.Delete(ctx, 3, "d1"); err != nil {
		t.Fatal(err)
	}
}

func TestAlarmRules(t *testing.T) {
	n := 0
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		n++
		switch n {
		case 1:
			expect(t, r, "GET", iid+"/measurement-points/5/alarm-rules", "")
			_, _ = w.Write([]byte("[" + ruleJSON + "]"))
		case 2:
			b := expect(t, r, "POST", iid+"/measurement-points/5/alarm-rules", "")
			if string(b) != `{"data_key":"","direction":"high","major_threshold":4,"method":"threshold","minor_threshold":2.5}` {
				t.Fatalf("body %s", b)
			}
			w.WriteHeader(201)
			_, _ = w.Write([]byte(ruleJSON))
		case 3:
			b := expect(t, r, "PATCH", iid+"/measurement-points/5/alarm-rules/r1", "")
			if string(b) != `{"major_threshold":6}` {
				t.Fatalf("body %s", b)
			}
			_, _ = w.Write([]byte(ruleJSON))
		case 4:
			expect(t, r, "DELETE", iid+"/measurement-points/5/alarm-rules/r1", "")
			w.WriteHeader(204)
		}
	})
	defer stop()
	ctx, a, six := context.Background(), inst(c).AlarmRules, 6.0
	if l, err := a.List(ctx, 5); err != nil || l[0].Scope != "point" || *l[0].MinorThreshold != 2.5 || l[0].MajorThreshold != nil || l[0].Source != nil {
		t.Fatalf("%v %+v", err, l)
	}
	if _, err := a.Create(ctx, 5, 2.5, 4, "", ""); err != nil {
		t.Fatal(err)
	}
	if _, err := a.Update(ctx, 5, "r1", nil, &six, nil, nil); err != nil {
		t.Fatal(err)
	}
	if err := a.Delete(ctx, 5, "r1"); err != nil {
		t.Fatal(err)
	}
}
