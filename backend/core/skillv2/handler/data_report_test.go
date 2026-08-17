package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"lazymind/core/skillv2/testutil"
	"lazymind/core/store"
)

func TestDataReportIsListedExternalAndDisabledByDefault(t *testing.T) {
	builtinRoot, err := filepath.Abs("../../../../skills")
	if err != nil {
		t.Fatalf("resolve builtin skills root: %v", err)
	}
	t.Setenv("LAZYMIND_BUILTIN_SKILLS_DIR", builtinRoot)
	db := testutil.NewTestDB(t)
	store.Init(db.DB, nil, nil)
	t.Cleanup(func() { store.Init(nil, nil, nil) })

	req := httptest.NewRequest(http.MethodGet, "/api/core/builtin-skills", nil)
	req.Header.Set("X-User-Id", "user_001")
	rec := httptest.NewRecorder()
	ListBuiltinSkills(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s, want 200", rec.Code, rec.Body.String())
	}
	var response struct {
		Data struct {
			Items []struct {
				UID       string `json:"builtin_skill_uid"`
				Category  string `json:"category"`
				Installed bool   `json:"installed"`
			} `json:"items"`
		} `json:"data"`
	}
	if err := json.NewDecoder(rec.Body).Decode(&response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	for _, item := range response.Data.Items {
		if item.UID == "bsk_01K2A3B4C5D6E7F8G9HJKMNPQR" {
			if item.Category != "external" || item.Installed {
				t.Fatalf("unexpected data-report state: %#v", item)
			}
			return
		}
	}
	t.Fatal("data-report not listed")
}
