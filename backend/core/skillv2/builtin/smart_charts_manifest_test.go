package builtin

import (
	"path/filepath"
	"testing"
)

func TestSmartChartsPackageIsShippedCompleteAndExternal(t *testing.T) {
	builtinRoot, err := filepath.Abs("../../../../skills")
	if err != nil {
		t.Fatalf("resolve builtin skills root: %v", err)
	}
	t.Setenv("LAZYMIND_BUILTIN_SKILLS_DIR", builtinRoot)

	const uid = "bsk_01K2SMARTCHARTS5V0A1B2C3D4"
	pkg, found, err := PackageByUID(uid)
	if err != nil {
		t.Fatalf("load smart-charts package: %v", err)
	}
	if !found {
		t.Fatal("smart-charts builtin manifest not found")
	}
	if pkg.Category != "external" || pkg.Name != "smart-charts" {
		t.Fatalf("unexpected package metadata: category=%q name=%q", pkg.Category, pkg.Name)
	}
	for _, requiredPath := range []string{
		"SKILL.md", "REFERENCE.md", "requirements.txt", "_icon.png", "_meta.json",
		"_skillhub_meta.json", "core/__init__.py", "core/chart_generator.py",
		"core/data_parser.py", "core/data_transformer.py", "core/exceptions.py",
		"core/generate_hashes.py",
	} {
		if _, ok := pkg.Files[requiredPath]; !ok {
			t.Errorf("smart-charts package missing %s", requiredPath)
		}
	}
}
