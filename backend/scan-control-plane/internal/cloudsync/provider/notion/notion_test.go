package notion

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/lazymind/scan_control_plane/internal/cloudsync/provider"
)

func TestValidateTargetPage(t *testing.T) {
	p := newTestProvider(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/pages/root" {
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}
		if got := r.Header.Get("Authorization"); got != "Bearer token" {
			t.Fatalf("expected authorization bearer token, got %q", got)
		}
		writeJSON(w, notionPage("root", "Root", "2026-06-01T12:00:00Z"))
	})

	if err := p.ValidateTarget(context.Background(), provider.ListRequest{
		AccessToken: "token",
		TargetType:  "notion_page",
		TargetRef:   "root",
	}); err != nil {
		t.Fatalf("ValidateTarget failed: %v", err)
	}
}

func TestListObjectsPageWalksChildPagesAndDatabases(t *testing.T) {
	p := newTestProvider(t, func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/pages/root":
			writeJSON(w, notionPage("root", "Root", "2026-06-01T12:00:00Z"))
		case "/blocks/root/children":
			writeJSON(w, `{"object":"list","results":[
				{"object":"block","id":"child","type":"child_page","has_children":false,"child_page":{"title":"Child"}},
				{"object":"block","id":"db","type":"child_database","has_children":true,"child_database":{"title":"DB"}}
			],"has_more":false,"next_cursor":null}`)
		case "/pages/child":
			writeJSON(w, notionPage("child", "Child", "2026-06-01T12:01:00Z"))
		case "/blocks/child/children":
			writeJSON(w, `{"object":"list","results":[],"has_more":false,"next_cursor":null}`)
		case "/databases/db":
			writeJSON(w, notionDatabase("db", "DB", "2026-06-01T12:02:00Z"))
		case "/databases/db/query":
			if r.Method != http.MethodPost {
				t.Fatalf("expected POST, got %s", r.Method)
			}
			writeJSON(w, `{"object":"list","results":[`+notionPage("row", "Row", "2026-06-01T12:03:00Z")+`],"has_more":false,"next_cursor":null}`)
		case "/pages/row":
			writeJSON(w, notionPage("row", "Row", "2026-06-01T12:03:00Z"))
		case "/blocks/row/children":
			writeJSON(w, `{"object":"list","results":[],"has_more":false,"next_cursor":null}`)
		default:
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}
	})

	objects, err := p.ListObjects(context.Background(), provider.ListRequest{
		AccessToken: "token",
		TargetType:  "page",
		TargetRef:   "root",
	})
	if err != nil {
		t.Fatalf("ListObjects failed: %v", err)
	}
	if len(objects) != 4 {
		t.Fatalf("expected 4 objects, got %d: %#v", len(objects), objects)
	}
	assertObject(t, objects[0], "root", "", "Root", "Root", "notion_page")
	assertObject(t, objects[1], "child", "root", "Root/Child", "Child", "notion_page")
	assertObject(t, objects[2], "db", "root", "Root/DB", "DB", "notion_database")
	assertObject(t, objects[3], "row", "db", "Root/DB/Row", "Row", "notion_page")
	if hasChild, _ := objects[0].ProviderMeta["has_child"].(bool); !hasChild {
		t.Fatalf("expected root has_child=true")
	}
	wantModified := time.Date(2026, 6, 1, 12, 3, 0, 0, time.UTC)
	if objects[3].ExternalModifiedAt == nil || !objects[3].ExternalModifiedAt.Equal(wantModified) {
		t.Fatalf("unexpected row modified time: %v", objects[3].ExternalModifiedAt)
	}
}

func TestDownloadObjectPageRendersMarkdown(t *testing.T) {
	p := newTestProvider(t, func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/pages/root":
			writeJSON(w, notionPage("root", "Root", "2026-06-01T12:00:00Z"))
		case "/blocks/root/children":
			writeJSON(w, `{"object":"list","results":[
				{"object":"block","id":"h","type":"heading_2","has_children":false,"heading_2":{"rich_text":[{"plain_text":"Plan"}]}},
				{"object":"block","id":"p","type":"paragraph","has_children":false,"paragraph":{"rich_text":[{"plain_text":"Ship Notion connector."}]}},
				{"object":"block","id":"c","type":"code","has_children":false,"code":{"language":"go","rich_text":[{"plain_text":"fmt.Println(\"ok\")"}]}}
			],"has_more":false,"next_cursor":null}`)
		default:
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}
	})

	content, err := p.DownloadObject(context.Background(), "token", provider.RemoteObject{
		ExternalObjectID: "root",
		ExternalKind:     "notion_page",
		DownloadRef:      "root",
	})
	if err != nil {
		t.Fatalf("DownloadObject failed: %v", err)
	}
	text := string(content)
	for _, want := range []string{"# Root", "## Plan", "Ship Notion connector.", "```go", "fmt.Println(\"ok\")"} {
		if !strings.Contains(text, want) {
			t.Fatalf("expected markdown to contain %q, got:\n%s", want, text)
		}
	}
}

func TestNormalizeNotionTargetRef(t *testing.T) {
	tests := map[string]string{
		"373400a8299780fdb1a8de81728c58d3":                             "373400a8299780fdb1a8de81728c58d3",
		"373400a8-2997-80fd-b1a8-de81728c58d3":                         "373400a8299780fdb1a8de81728c58d3",
		"https://www.notion.so/Title-373400a8299780fdb1a8de81728c58d3": "373400a8299780fdb1a8de81728c58d3",
		"https://www.notion.so/foo?p=373400a8299780fdb1a8de81728c58d3": "373400a8299780fdb1a8de81728c58d3",
	}
	for input, want := range tests {
		if got := normalizeNotionTargetRef(input); got != want {
			t.Fatalf("normalizeNotionTargetRef(%q)=%q, want %q", input, got, want)
		}
	}
}

func newTestProvider(t *testing.T, handler http.HandlerFunc) *Provider {
	t.Helper()
	p := New(0)
	p.baseURL = "https://notion.test"
	p.client = &http.Client{
		Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			rec := httptest.NewRecorder()
			handler.ServeHTTP(rec, req)
			return rec.Result(), nil
		}),
	}
	return p
}

func notionPage(id, title, lastEdited string) string {
	return fmt.Sprintf(`{"object":"page","id":%q,"last_edited_time":%q,"url":"https://www.notion.so/%s","properties":{"title":{"id":"title","type":"title","title":[{"plain_text":%q}]}}}`, id, lastEdited, id, title)
}

func notionDatabase(id, title, lastEdited string) string {
	return fmt.Sprintf(`{"object":"database","id":%q,"last_edited_time":%q,"url":"https://www.notion.so/%s","title":[{"plain_text":%q}]}`, id, lastEdited, id, title)
}

func writeJSON(w http.ResponseWriter, body string) {
	w.Header().Set("Content-Type", "application/json")
	_, _ = fmt.Fprint(w, body)
}

func assertObject(t *testing.T, obj provider.RemoteObject, id, parentID, externalPath, name, kind string) {
	t.Helper()
	if obj.ExternalObjectID != id || obj.ExternalParentID != parentID || obj.ExternalPath != externalPath || obj.ExternalName != name || obj.ExternalKind != kind {
		t.Fatalf("unexpected object: %#v", obj)
	}
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (fn roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return fn(req)
}
