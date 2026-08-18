package builtin

import (
	"crypto/sha256"
	"fmt"
	"path/filepath"
	"testing"
)

const cangjieDistillUID = "bsk_01K2CANGJIEDISTILL7M4N8P9Q"

func TestCangjieDistillPackageIsShippedCompleteAndExternal(t *testing.T) {
	t.Setenv("LAZYMIND_BUILTIN_SKILLS_DIR", filepath.Join("..", "..", "..", "..", "skills"))

	pkg, found, err := PackageByUID(cangjieDistillUID)
	if err != nil {
		t.Fatalf("load cangjie-distill package: %v", err)
	}
	if !found {
		t.Fatal("cangjie-distill manifest not found")
	}
	if pkg.Category != "external" || pkg.Name != "拆书成技能" {
		t.Fatalf("unexpected package metadata: category=%q name=%q", pkg.Category, pkg.Name)
	}

	requiredPaths := []string{
		"SKILL.md",
		"_meta.json",
		"_skillhub_meta.json",
		"extractors/case-extractor.md",
		"extractors/counter-example-extractor.md",
		"extractors/framework-extractor.md",
		"extractors/glossary-extractor.md",
		"extractors/principle-extractor.md",
		"methodology/00-overview.md",
		"methodology/01-stage0-adler.md",
		"methodology/02-stage1-parallel-extract.md",
		"methodology/03-stage1.5-triple-verify.md",
		"methodology/04-stage2-ria-plus.md",
		"methodology/05-stage3-zettelkasten.md",
		"methodology/06-stage4-pressure-test.md",
		"templates/BOOK_OVERVIEW.md",
		"templates/INDEX.md",
		"templates/SKILL.md",
		"templates/test-prompts.json",
	}
	if len(pkg.Files) != len(requiredPaths) {
		t.Fatalf("cangjie-distill package has %d files, want %d", len(pkg.Files), len(requiredPaths))
	}
	for _, name := range requiredPaths {
		if len(pkg.Files[name]) == 0 {
			t.Errorf("cangjie-distill package missing %s", name)
		}
	}

	gotHash := fmt.Sprintf("%x", sha256.Sum256(pkg.Files["SKILL.md"]))
	const wantHash = "4304c951370d6c18bc097ddac49e19f19289756e8e42c59043aca6787b381c7d"
	if gotHash != wantHash {
		t.Fatalf("SKILL.md sha256=%s, want %s", gotHash, wantHash)
	}
}
