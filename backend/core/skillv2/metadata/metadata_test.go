package metadata

import (
	"strings"
	"testing"
)

func TestParseRequired(t *testing.T) {
	meta, err := ParseRequired([]byte("---\nname: imported-skill\ndescription: Imported description\nversion: 1.2.3\ncategory: external\ntags: [test, test, '  verified  ']\n---\n# Skill\n"))
	if err != nil {
		t.Fatalf("ParseRequired returned error: %v", err)
	}
	if meta.Name != "imported-skill" || meta.Description != "Imported description" || meta.Version != "1.2.3" || meta.Category != "external" {
		t.Fatalf("ParseRequired metadata = %#v", meta)
	}
	if strings.Join(meta.Tags, ",") != "test,verified" {
		t.Fatalf("ParseRequired tags = %#v", meta.Tags)
	}
}

func TestParseRequiredPrefersDisplayName(t *testing.T) {
	meta, err := ParseRequired([]byte("---\nname: cangjie-skill\ndisplayName: 拆书成技能\ndescription: 把书蒸馏成可执行的技能\n---\n# Skill\n"))
	if err != nil {
		t.Fatalf("ParseRequired returned error: %v", err)
	}
	if meta.Name != "拆书成技能" || meta.Description != "把书蒸馏成可执行的技能" {
		t.Fatalf("ParseRequired metadata = %#v", meta)
	}
}

func TestParseRequiredRejectsInvalidDisplayName(t *testing.T) {
	_, err := ParseRequired([]byte("---\nname: canonical-name\ndisplayName: bad/name\ndescription: description\n---\n# Skill\n"))
	if err == nil || !strings.Contains(err.Error(), "invalid") {
		t.Fatalf("ParseRequired error = %v, want invalid display name error", err)
	}
}

func TestParseRequiredRejectsMissingFields(t *testing.T) {
	for name, content := range map[string]string{
		"frontmatter":  "# Skill\n",
		"name":         "---\ndescription: description\n---\n# Skill\n",
		"description":  "---\nname: skill\n---\n# Skill\n",
		"invalid name": "---\nname: bad/name\ndescription: description\n---\n# Skill\n",
	} {
		t.Run(name, func(t *testing.T) {
			_, err := ParseRequired([]byte(content))
			if err == nil {
				t.Fatal("ParseRequired succeeded")
			}
			if !strings.Contains(err.Error(), strings.Split(name, " ")[0]) {
				t.Fatalf("ParseRequired error = %q", err)
			}
		})
	}
}
