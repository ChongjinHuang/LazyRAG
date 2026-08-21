package builtin

import (
	"crypto/sha256"
	"fmt"
	"path/filepath"
	"testing"
)

const interviewSimulatorUID = "bsk_01K2IVSIMULATOR7M4N8P9Q"

func TestInterviewSimulatorPackageIsShippedCompleteAndExternal(t *testing.T) {
	t.Setenv("LAZYMIND_BUILTIN_SKILLS_DIR", filepath.Join("..", "..", "..", "..", "skills"))

	pkg, found, err := PackageByUID(interviewSimulatorUID)
	if err != nil {
		t.Fatalf("load interview-simulator package: %v", err)
	}
	if !found {
		t.Fatal("interview-simulator manifest not found")
	}
	if pkg.Category != "external" || pkg.Name != "interview-simulator" || pkg.Description == "" {
		t.Fatalf("unexpected package metadata: category=%q name=%q description=%q", pkg.Category, pkg.Name, pkg.Description)
	}

	requiredPaths := []string{"README.md", "SKILL.md", "_meta.json"}
	if len(pkg.Files) != len(requiredPaths) {
		t.Fatalf("interview-simulator package has %d files, want %d", len(pkg.Files), len(requiredPaths))
	}
	for _, name := range requiredPaths {
		if len(pkg.Files[name]) == 0 {
			t.Errorf("interview-simulator package missing %s", name)
		}
	}

	gotHash := fmt.Sprintf("%x", sha256.Sum256(pkg.Files["SKILL.md"]))
	const wantHash = "02f3f0a81577dc8ec91c0d1218ca7bf482ffbe42970305ab742d595415e667ef"
	if gotHash != wantHash {
		t.Fatalf("SKILL.md sha256=%s, want %s", gotHash, wantHash)
	}
}
