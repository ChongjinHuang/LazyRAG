package builtin

import (
	"crypto/sha256"
	"fmt"
	"path/filepath"
	"testing"
)

const xiaohongshuCopywriterUID = "bsk_01K2XHSCOPYWRITER7M4N8P9Q"

func TestXiaohongshuCopywriterPackageIsShippedCompleteAndExternal(t *testing.T) {
	t.Setenv("LAZYMIND_BUILTIN_SKILLS_DIR", filepath.Join("..", "..", "..", "..", "skills"))

	pkg, found, err := PackageByUID(xiaohongshuCopywriterUID)
	if err != nil {
		t.Fatalf("load xiaohongshu-copywriter-plus package: %v", err)
	}
	if !found {
		t.Fatal("xiaohongshu-copywriter-plus manifest not found")
	}
	if pkg.Category != "external" || pkg.Name != "xiaohongshu-copywriter" || pkg.DisplayName != "小红书爆款文案生成器增强版" {
		t.Fatalf("unexpected package metadata: category=%q name=%q display_name=%q", pkg.Category, pkg.Name, pkg.DisplayName)
	}

	requiredPaths := []string{
		"SKILL.md",
		"_meta.json",
		"references/copywriting-structure.md",
		"references/emoji-and-tags.md",
		"references/publishing-strategy.md",
		"references/title-formulas.md",
	}
	if len(pkg.Files) != len(requiredPaths) {
		t.Fatalf("xiaohongshu-copywriter-plus package has %d files, want %d", len(pkg.Files), len(requiredPaths))
	}
	for _, name := range requiredPaths {
		if len(pkg.Files[name]) == 0 {
			t.Errorf("xiaohongshu-copywriter-plus package missing %s", name)
		}
	}

	gotHash := fmt.Sprintf("%x", sha256.Sum256(pkg.Files["SKILL.md"]))
	const wantHash = "e560204b64a974c955de1f5cd3f6aa83bd0c62bd47e74e7cf3184fd40e661771"
	if gotHash != wantHash {
		t.Fatalf("SKILL.md sha256=%s, want %s", gotHash, wantHash)
	}
}
