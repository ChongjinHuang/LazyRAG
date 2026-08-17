package builtin

import (
	"path/filepath"
	"testing"
)

func TestDataReportPackageIsShippedCompleteAndExternal(t *testing.T) {
	t.Setenv("LAZYMIND_BUILTIN_SKILLS_DIR", filepath.Join("..", "..", "..", "..", "skills"))
	const uid = "bsk_01K2A3B4C5D6E7F8G9HJKMNPQR"

	pkg, found, err := PackageByUID(uid)
	if err != nil {
		t.Fatalf("load data-report package: %v", err)
	}
	if !found {
		t.Fatal("data-report manifest not found")
	}
	if pkg.Category != "external" || pkg.Name != "data-report" {
		t.Fatalf("unexpected package metadata: category=%q name=%q", pkg.Category, pkg.Name)
	}
	if pkg.SkillCategory != "data" {
		t.Fatalf("data-report install category=%q, want data", pkg.SkillCategory)
	}
	if len(pkg.Files) != 3 {
		t.Fatalf("data-report package has %d files, want 3", len(pkg.Files))
	}
	for _, name := range []string{"SKILL.md", "example.html", "open-design.json"} {
		if len(pkg.Files[name]) == 0 {
			t.Fatalf("data-report package missing %s", name)
		}
	}
}
