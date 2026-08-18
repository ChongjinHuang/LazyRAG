package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/gorilla/mux"

	"lazymind/core/skillv2/testutil"
	"lazymind/core/store"
)

const cangjieDistillBuiltinUID = "bsk_01K2CANGJIEDISTILL7M4N8P9Q"

func TestCangjieDistillIsListedExternalAndDisabledByDefault(t *testing.T) {
	setCangjieDistillBuiltinRoot(t)
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
				Name      string `json:"name"`
				Category  string `json:"category"`
				Installed bool   `json:"installed"`
			} `json:"items"`
		} `json:"data"`
	}
	if err := json.NewDecoder(rec.Body).Decode(&response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	for _, item := range response.Data.Items {
		if item.UID == cangjieDistillBuiltinUID {
			if item.Name != "拆书成技能" || item.Category != "external" || item.Installed {
				t.Fatalf("unexpected cangjie-distill state: %#v", item)
			}
			return
		}
	}
	t.Fatal("cangjie-distill not listed")
}

func TestEnableCangjieDistillInstallsCompleteEnabledCopy(t *testing.T) {
	setCangjieDistillBuiltinRoot(t)
	db := testutil.NewTestDB(t)
	store.Init(db.DB, nil, nil)
	t.Cleanup(func() { store.Init(nil, nil, nil) })

	req := httptest.NewRequest(http.MethodPost, "/api/core/builtin-skills/"+cangjieDistillBuiltinUID+":enable", nil)
	req.Header.Set("X-User-Id", "user_001")
	req = mux.SetURLVars(req, map[string]string{"builtin_skill_uid": cangjieDistillBuiltinUID + ":enable"})
	rec := httptest.NewRecorder()
	EnableBuiltinSkill(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s, want 200", rec.Code, rec.Body.String())
	}
	var response struct {
		Data struct {
			ID        string `json:"id"`
			Name      string `json:"name"`
			Category  string `json:"category"`
			IsEnabled bool   `json:"is_enabled"`
		} `json:"data"`
	}
	if err := json.NewDecoder(rec.Body).Decode(&response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if response.Data.ID == "" || response.Data.Name != "拆书成技能" || response.Data.Category != "external" || !response.Data.IsEnabled {
		t.Fatalf("unexpected enabled skill: %#v", response.Data)
	}
	if got := testutil.CountRows(t, db, "skill_revision_entries", "revision_id IN (SELECT head_revision_id FROM skills WHERE id = ?) AND entry_type = 'file'", response.Data.ID); got != 19 {
		t.Fatalf("installed cangjie-distill has %d files, want 19", got)
	}
}

func setCangjieDistillBuiltinRoot(t *testing.T) {
	t.Helper()
	builtinRoot, err := filepath.Abs("../../../../skills")
	if err != nil {
		t.Fatalf("resolve builtin skills root: %v", err)
	}
	t.Setenv("LAZYMIND_BUILTIN_SKILLS_DIR", builtinRoot)
}
