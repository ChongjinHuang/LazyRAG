package builtin

import (
	"path/filepath"
	"testing"
)

// TestTemplateID prefixes the UID with the builtin prefix.
func TestTemplateID(t *testing.T) {
	got := TemplateID("abc123")
	want := "builtin:abc123"
	if got != want {
		t.Fatalf("got %q, want %q", got, want)
	}
}

// TestTemplateID_TrimsWhitespace trims whitespace from the input UID.
func TestTemplateID_TrimsWhitespace(t *testing.T) {
	got := TemplateID("  uid-1  ")
	want := "builtin:uid-1"
	if got != want {
		t.Fatalf("got %q, want %q", got, want)
	}
}

// TestIsTemplateID detects the builtin prefix.
func TestIsTemplateID(t *testing.T) {
	tests := []struct {
		id   string
		want bool
	}{
		{"builtin:abc", true},
		{"builtin:", true},
		{"normal-id", false},
		{"", false},
		{"BUILTIN:abc", false},
	}
	for _, tt := range tests {
		t.Run(tt.id, func(t *testing.T) {
			if got := IsTemplateID(tt.id); got != tt.want {
				t.Fatalf("got %v, want %v", got, tt.want)
			}
		})
	}
}

// TestParseSkillMDMetadata extracts name and description from YAML frontmatter.
func TestParseSkillMDMetadata(t *testing.T) {
	content := "---\nname: My Skill\ndescription: A test skill\n---\n\n# Body content"
	name, desc := parseSkillMDMetadata(content)
	if name != "My Skill" || desc != "A test skill" {
		t.Fatalf("got name=%q desc=%q", name, desc)
	}
}

// TestParseSkillMDMetadata_NoFrontmatter returns empty strings.
func TestParseSkillMDMetadata_NoFrontmatter(t *testing.T) {
	name, desc := parseSkillMDMetadata("# Just a heading")
	if name != "" || desc != "" {
		t.Fatalf("got name=%q desc=%q, want empty", name, desc)
	}
}

// TestParseSkillMDMetadata_MissingClosing returns empty strings.
func TestParseSkillMDMetadata_MissingClosing(t *testing.T) {
	content := "---\nname: Test\n# no closing ---"
	name, desc := parseSkillMDMetadata(content)
	if name != "" || desc != "" {
		t.Fatalf("got name=%q desc=%q, want empty", name, desc)
	}
}

// TestParseSkillMDMetadata_EmptyFrontmatter returns empty strings.
func TestParseSkillMDMetadata_EmptyFrontmatter(t *testing.T) {
	content := "---\n---\nbody"
	name, desc := parseSkillMDMetadata(content)
	if name != "" || desc != "" {
		t.Fatalf("got name=%q desc=%q, want empty", name, desc)
	}
}

// TestParseSkillMDMetadata_WindowsLineEndings handles CRLF.
func TestParseSkillMDMetadata_WindowsLineEndings(t *testing.T) {
	content := "---\r\nname: Win Skill\r\ndescription: CRLF test\r\n---\r\n\r\nBody"
	name, desc := parseSkillMDMetadata(content)
	if name != "Win Skill" || desc != "CRLF test" {
		t.Fatalf("got name=%q desc=%q", name, desc)
	}
}

// TestParseSkillMDMetadata_TrimsWhitespace trims name and description.
func TestParseSkillMDMetadata_TrimsWhitespace(t *testing.T) {
	content := "---\nname:   Padded   \ndescription:   Desc with spaces   \n---\nbody"
	name, desc := parseSkillMDMetadata(content)
	if name != "Padded" || desc != "Desc with spaces" {
		t.Fatalf("got name=%q desc=%q", name, desc)
	}
}

func TestSmartChartsPackageIsShippedCompleteAndExternal(t *testing.T) {
	builtinRoot, err := filepath.Abs("../../../../skills")
	if err != nil {
		t.Fatalf("resolve builtin skills root: %v", err)
	}
	t.Setenv("LAZYMIND_BUILTIN_SKILLS_DIR", builtinRoot)

	var manifest Manifest
	found := false
	for _, item := range Manifests {
		if item.DirName == "smart-charts" {
			manifest = item
			found = true
			break
		}
	}
	if !found {
		t.Fatal("smart-charts builtin manifest not found")
	}
	if manifest.Category != "external" {
		t.Fatalf("smart-charts category = %q, want external", manifest.Category)
	}

	pkg, err := LoadPackage(manifest)
	if err != nil {
		t.Fatalf("load smart-charts package: %v", err)
	}
	if pkg.Name != "smart-charts" {
		t.Fatalf("smart-charts package name = %q", pkg.Name)
	}
	for _, requiredPath := range []string{
		"SKILL.md",
		"REFERENCE.md",
		"requirements.txt",
		"_icon.png",
		"_meta.json",
		"_skillhub_meta.json",
		"core/__init__.py",
		"core/chart_generator.py",
		"core/data_parser.py",
		"core/data_transformer.py",
		"core/exceptions.py",
		"core/generate_hashes.py",
	} {
		if _, ok := pkg.Files[requiredPath]; !ok {
			t.Errorf("smart-charts package missing %s", requiredPath)
		}
	}
}
