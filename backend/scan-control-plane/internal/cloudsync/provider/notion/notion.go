package notion

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"path"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/lazymind/scan_control_plane/internal/cloudsync/provider"
	"go.uber.org/zap"
)

const (
	apiBase       = "https://api.notion.com/v1"
	notionVersion = "2022-06-28"
	pageSize      = 100
)

var notionIDPattern = regexp.MustCompile(`(?i)([0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})`)

type Provider struct {
	baseURL string
	client  *http.Client
	log     *zap.Logger
}

func New(timeout time.Duration) *Provider {
	return NewWithLogger(timeout, nil)
}

func NewWithLogger(timeout time.Duration, logger *zap.Logger) *Provider {
	if timeout <= 0 {
		timeout = 30 * time.Second
	}
	if logger == nil {
		logger = zap.NewNop()
	}
	return &Provider{
		baseURL: strings.TrimRight(apiBase, "/"),
		client:  &http.Client{Timeout: timeout},
		log:     logger,
	}
}

func (p *Provider) Name() string { return "notion" }

func (p *Provider) ValidateTarget(ctx context.Context, req provider.ListRequest) error {
	accessToken := strings.TrimSpace(req.AccessToken)
	if accessToken == "" {
		return fmt.Errorf("notion access_token is empty")
	}
	targetType := normalizeTargetType(req.TargetType)
	targetRef := firstNonEmpty(req.TargetRef, stringOption(req.ProviderOptions, "page_id"), stringOption(req.ProviderOptions, "database_id"))
	targetID := normalizeNotionTargetRef(targetRef)
	if targetID == "" {
		return fmt.Errorf("notion target_ref(page_id or database_id) is required")
	}
	switch targetType {
	case "database", "notion_database":
		_, err := p.retrieveDatabase(ctx, accessToken, targetID)
		return err
	case "page", "notion_page", "":
		_, err := p.retrievePage(ctx, accessToken, targetID)
		return err
	default:
		return fmt.Errorf("unsupported notion target_type: %s", req.TargetType)
	}
}

func (p *Provider) ListObjects(ctx context.Context, req provider.ListRequest) ([]provider.RemoteObject, error) {
	accessToken := strings.TrimSpace(req.AccessToken)
	if accessToken == "" {
		return nil, fmt.Errorf("notion access_token is empty")
	}
	targetType := normalizeTargetType(req.TargetType)
	targetRef := firstNonEmpty(req.TargetRef, stringOption(req.ProviderOptions, "page_id"), stringOption(req.ProviderOptions, "database_id"))
	targetID := normalizeNotionTargetRef(targetRef)
	if targetID == "" {
		return nil, fmt.Errorf("notion target_ref(page_id or database_id) is required")
	}
	visited := make(map[string]struct{}, 128)
	out := make([]provider.RemoteObject, 0, 256)
	switch targetType {
	case "database", "notion_database":
		if err := p.walkDatabase(ctx, accessToken, targetID, "", "", visited, &out); err != nil {
			return nil, err
		}
	case "page", "notion_page", "":
		if err := p.walkPage(ctx, accessToken, targetID, "", "", visited, &out); err != nil {
			return nil, err
		}
	default:
		return nil, fmt.Errorf("unsupported notion target_type: %s", req.TargetType)
	}
	return out, nil
}

func (p *Provider) DownloadObject(ctx context.Context, accessToken string, object provider.RemoteObject) ([]byte, error) {
	accessToken = strings.TrimSpace(accessToken)
	if accessToken == "" {
		return nil, fmt.Errorf("notion access_token is empty")
	}
	ref := normalizeNotionTargetRef(firstNonEmpty(object.DownloadRef, object.ExternalObjectID))
	if ref == "" {
		return nil, fmt.Errorf("notion object download ref is empty")
	}
	kind := normalizeKind(object.ExternalKind, object.ProviderMeta)
	switch kind {
	case "notion_database", "database":
		text, err := p.databaseToMarkdown(ctx, accessToken, ref, 1, map[string]struct{}{})
		if err != nil {
			return nil, err
		}
		return []byte(text), nil
	default:
		text, err := p.pageToMarkdown(ctx, accessToken, ref, 1, map[string]struct{}{})
		if err != nil {
			return nil, err
		}
		return []byte(text), nil
	}
}

func (p *Provider) walkPage(
	ctx context.Context,
	accessToken, pageID, parentPath, parentID string,
	visited map[string]struct{},
	out *[]provider.RemoteObject,
) error {
	pageID = normalizeNotionTargetRef(pageID)
	if pageID == "" {
		return nil
	}
	if _, ok := visited["page:"+pageID]; ok {
		return nil
	}
	visited["page:"+pageID] = struct{}{}
	pageObj, err := p.retrievePage(ctx, accessToken, pageID)
	if err != nil {
		return err
	}
	children, err := p.listBlockChildren(ctx, accessToken, pageID)
	if err != nil {
		return err
	}
	title := pageTitle(pageObj)
	if title == "" {
		title = pageID
	}
	currentPath := joinPath(parentPath, title)
	hasChild := hasNotionChild(children)
	*out = append(*out, pageRemoteObject(pageObj, parentID, currentPath, hasChild))
	for _, child := range children {
		childType := strings.TrimSpace(valueAsString(child["type"]))
		childID := strings.TrimSpace(valueAsString(child["id"]))
		if childID == "" {
			continue
		}
		switch childType {
		case "child_page":
			if err := p.walkPage(ctx, accessToken, childID, currentPath, pageID, visited, out); err != nil {
				return err
			}
		case "child_database":
			if err := p.walkDatabase(ctx, accessToken, childID, currentPath, pageID, visited, out); err != nil {
				return err
			}
		}
	}
	return nil
}

func (p *Provider) walkDatabase(
	ctx context.Context,
	accessToken, databaseID, parentPath, parentID string,
	visited map[string]struct{},
	out *[]provider.RemoteObject,
) error {
	databaseID = normalizeNotionTargetRef(databaseID)
	if databaseID == "" {
		return nil
	}
	if _, ok := visited["database:"+databaseID]; ok {
		return nil
	}
	visited["database:"+databaseID] = struct{}{}
	dbObj, err := p.retrieveDatabase(ctx, accessToken, databaseID)
	if err != nil {
		return err
	}
	title := databaseTitle(dbObj)
	if title == "" {
		title = databaseID
	}
	currentPath := joinPath(parentPath, title)
	*out = append(*out, databaseRemoteObject(dbObj, parentID, currentPath))
	pages, err := p.queryDatabase(ctx, accessToken, databaseID)
	if err != nil {
		return err
	}
	for _, pageObj := range pages {
		pageID := strings.TrimSpace(valueAsString(pageObj["id"]))
		if pageID == "" {
			continue
		}
		if err := p.walkPage(ctx, accessToken, pageID, currentPath, databaseID, visited, out); err != nil {
			return err
		}
	}
	return nil
}

func (p *Provider) retrievePage(ctx context.Context, accessToken, pageID string) (map[string]any, error) {
	var out map[string]any
	err := p.getJSON(ctx, accessToken, "/pages/"+url.PathEscape(normalizeNotionTargetRef(pageID)), nil, &out)
	return out, err
}

func (p *Provider) retrieveDatabase(ctx context.Context, accessToken, databaseID string) (map[string]any, error) {
	var out map[string]any
	err := p.getJSON(ctx, accessToken, "/databases/"+url.PathEscape(normalizeNotionTargetRef(databaseID)), nil, &out)
	return out, err
}

func (p *Provider) listBlockChildren(ctx context.Context, accessToken, blockID string) ([]map[string]any, error) {
	return p.paginateGet(ctx, accessToken, "/blocks/"+url.PathEscape(normalizeNotionTargetRef(blockID))+"/children", map[string]string{"page_size": strconv.Itoa(pageSize)})
}

func (p *Provider) queryDatabase(ctx context.Context, accessToken, databaseID string) ([]map[string]any, error) {
	return p.paginatePost(ctx, accessToken, "/databases/"+url.PathEscape(normalizeNotionTargetRef(databaseID))+"/query", map[string]any{"page_size": pageSize})
}

func (p *Provider) pageToMarkdown(ctx context.Context, accessToken, pageID string, headingLevel int, visited map[string]struct{}) (string, error) {
	pageID = normalizeNotionTargetRef(pageID)
	if pageID == "" {
		return "", fmt.Errorf("notion page id is empty")
	}
	if _, ok := visited["page-md:"+pageID]; ok {
		return "", nil
	}
	visited["page-md:"+pageID] = struct{}{}
	pageObj, err := p.retrievePage(ctx, accessToken, pageID)
	if err != nil {
		return "", err
	}
	title := pageTitle(pageObj)
	if title == "" {
		title = pageID
	}
	children, err := p.listBlockChildren(ctx, accessToken, pageID)
	if err != nil {
		return "", err
	}
	lines := []string{fmt.Sprintf("%s %s", markdownHeading(headingLevel), title)}
	lines = append(lines, p.blocksToMarkdown(ctx, accessToken, children, headingLevel+1, visited)...)
	return joinMarkdown(lines), nil
}

func (p *Provider) databaseToMarkdown(ctx context.Context, accessToken, databaseID string, headingLevel int, visited map[string]struct{}) (string, error) {
	databaseID = normalizeNotionTargetRef(databaseID)
	dbObj, err := p.retrieveDatabase(ctx, accessToken, databaseID)
	if err != nil {
		return "", err
	}
	title := databaseTitle(dbObj)
	if title == "" {
		title = databaseID
	}
	lines := []string{fmt.Sprintf("%s %s", markdownHeading(headingLevel), title)}
	pages, err := p.queryDatabase(ctx, accessToken, databaseID)
	if err != nil {
		return "", err
	}
	for _, pageObj := range pages {
		pageID := strings.TrimSpace(valueAsString(pageObj["id"]))
		if pageID != "" {
			body, err := p.pageToMarkdown(ctx, accessToken, pageID, headingLevel+1, visited)
			if err == nil && strings.TrimSpace(body) != "" {
				lines = append(lines, body)
			}
		}
	}
	return joinMarkdown(lines), nil
}

func (p *Provider) blocksToMarkdown(ctx context.Context, accessToken string, blocks []map[string]any, headingLevel int, visited map[string]struct{}) []string {
	lines := make([]string, 0, len(blocks))
	for _, block := range blocks {
		lines = append(lines, p.blockToMarkdown(ctx, accessToken, block, headingLevel, visited)...)
	}
	return lines
}

func (p *Provider) blockToMarkdown(ctx context.Context, accessToken string, block map[string]any, headingLevel int, visited map[string]struct{}) []string {
	blockType := strings.TrimSpace(valueAsString(block["type"]))
	content, _ := block[blockType].(map[string]any)
	text := richText(content["rich_text"])
	var lines []string
	switch blockType {
	case "paragraph":
		if text != "" {
			lines = append(lines, text)
		}
	case "heading_1":
		lines = append(lines, fmt.Sprintf("# %s", text))
	case "heading_2":
		lines = append(lines, fmt.Sprintf("## %s", text))
	case "heading_3":
		lines = append(lines, fmt.Sprintf("### %s", text))
	case "bulleted_list_item":
		lines = append(lines, "- "+text)
	case "numbered_list_item":
		lines = append(lines, "1. "+text)
	case "to_do":
		mark := " "
		if boolOption(content, "checked") {
			mark = "x"
		}
		lines = append(lines, fmt.Sprintf("- [%s] %s", mark, text))
	case "toggle":
		lines = append(lines, "- "+text)
	case "quote":
		lines = append(lines, "> "+text)
	case "callout":
		lines = append(lines, "> "+text)
	case "code":
		lang := strings.TrimSpace(valueAsString(content["language"]))
		lines = append(lines, "```"+lang, text, "```")
	case "divider":
		lines = append(lines, "---")
	case "child_page":
		title := strings.TrimSpace(valueAsString(content["title"]))
		if title != "" {
			lines = append(lines, fmt.Sprintf("%s %s", markdownHeading(headingLevel), title))
		}
	case "child_database":
		title := strings.TrimSpace(valueAsString(content["title"]))
		if title != "" {
			lines = append(lines, fmt.Sprintf("%s %s", markdownHeading(headingLevel), title))
		}
	case "image", "file", "pdf", "video", "audio":
		if fileURL := fileBlockURL(content); fileURL != "" {
			caption := richText(content["caption"])
			label := blockType
			if caption != "" {
				label = caption
			}
			lines = append(lines, fmt.Sprintf("[%s](%s)", label, fileURL))
		}
	default:
		if text != "" {
			lines = append(lines, text)
		}
	}
	if boolOption(block, "has_children") {
		blockID := normalizeNotionTargetRef(valueAsString(block["id"]))
		if blockID != "" {
			children, err := p.listBlockChildren(ctx, accessToken, blockID)
			if err == nil {
				lines = append(lines, p.blocksToMarkdown(ctx, accessToken, children, headingLevel+1, visited)...)
			}
		}
	}
	return lines
}

func (p *Provider) paginateGet(ctx context.Context, accessToken, apiPath string, params map[string]string) ([]map[string]any, error) {
	params = cloneStringMap(params)
	var results []map[string]any
	cursor := ""
	for {
		pageParams := cloneStringMap(params)
		if cursor != "" {
			pageParams["start_cursor"] = cursor
		}
		var data pageListResponse
		if err := p.getJSON(ctx, accessToken, apiPath, pageParams, &data); err != nil {
			return nil, err
		}
		results = append(results, data.Results...)
		if !data.HasMore || strings.TrimSpace(data.NextCursor) == "" {
			return results, nil
		}
		cursor = strings.TrimSpace(data.NextCursor)
	}
}

func (p *Provider) paginatePost(ctx context.Context, accessToken, apiPath string, payload map[string]any) ([]map[string]any, error) {
	payload = cloneAnyMap(payload)
	var results []map[string]any
	cursor := ""
	for {
		pagePayload := cloneAnyMap(payload)
		if cursor != "" {
			pagePayload["start_cursor"] = cursor
		}
		var data pageListResponse
		if err := p.postJSON(ctx, accessToken, apiPath, pagePayload, &data); err != nil {
			return nil, err
		}
		results = append(results, data.Results...)
		if !data.HasMore || strings.TrimSpace(data.NextCursor) == "" {
			return results, nil
		}
		cursor = strings.TrimSpace(data.NextCursor)
	}
}

type pageListResponse struct {
	Results    []map[string]any `json:"results"`
	NextCursor string           `json:"next_cursor"`
	HasMore    bool             `json:"has_more"`
}

func (p *Provider) getJSON(ctx context.Context, accessToken, apiPath string, params map[string]string, out any) error {
	endpoint := p.baseURL + apiPath
	u, err := url.Parse(endpoint)
	if err != nil {
		return err
	}
	q := u.Query()
	for k, v := range params {
		if strings.TrimSpace(v) != "" {
			q.Set(k, strings.TrimSpace(v))
		}
	}
	u.RawQuery = q.Encode()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	if err != nil {
		return err
	}
	return p.doJSON(req, accessToken, out)
}

func (p *Provider) postJSON(ctx context.Context, accessToken, apiPath string, payload map[string]any, out any) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, p.baseURL+apiPath, bytes.NewReader(body))
	if err != nil {
		return err
	}
	return p.doJSON(req, accessToken, out)
}

func (p *Provider) doJSON(req *http.Request, accessToken string, out any) error {
	req.Header.Set("Authorization", "Bearer "+strings.TrimSpace(accessToken))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Notion-Version", notionVersion)
	resp, err := p.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}
	if resp.StatusCode >= 400 {
		return fmt.Errorf("notion api %s returned %d: %s", req.URL.Path, resp.StatusCode, strings.TrimSpace(string(body)))
	}
	if out == nil || len(body) == 0 {
		return nil
	}
	if err := json.Unmarshal(body, out); err != nil {
		return fmt.Errorf("decode notion api %s response failed: %w", req.URL.Path, err)
	}
	return nil
}

func pageRemoteObject(pageObj map[string]any, parentID, currentPath string, hasChild bool) provider.RemoteObject {
	pageID := strings.TrimSpace(valueAsString(pageObj["id"]))
	title := pageTitle(pageObj)
	if title == "" {
		title = pageID
	}
	mod := parseNotionTime(valueAsString(pageObj["last_edited_time"]))
	return provider.RemoteObject{
		ExternalObjectID:   pageID,
		ExternalParentID:   strings.TrimSpace(parentID),
		ExternalPath:       currentPath,
		ExternalName:       title,
		ExternalKind:       "notion_page",
		ExternalVersion:    firstNonEmpty(valueAsString(pageObj["last_edited_time"]), pageID),
		ExternalModifiedAt: mod,
		DownloadRef:        pageID,
		ProviderMeta: map[string]any{
			"obj_type":         "notion_page",
			"page_id":          pageID,
			"url":              valueAsString(pageObj["url"]),
			"public_url":       valueAsString(pageObj["public_url"]),
			"has_child":        hasChild,
			"last_edited_time": valueAsString(pageObj["last_edited_time"]),
		},
	}
}

func databaseRemoteObject(dbObj map[string]any, parentID, currentPath string) provider.RemoteObject {
	databaseID := strings.TrimSpace(valueAsString(dbObj["id"]))
	title := databaseTitle(dbObj)
	if title == "" {
		title = databaseID
	}
	mod := parseNotionTime(valueAsString(dbObj["last_edited_time"]))
	return provider.RemoteObject{
		ExternalObjectID:   databaseID,
		ExternalParentID:   strings.TrimSpace(parentID),
		ExternalPath:       currentPath,
		ExternalName:       title,
		ExternalKind:       "notion_database",
		ExternalVersion:    firstNonEmpty(valueAsString(dbObj["last_edited_time"]), databaseID),
		ExternalModifiedAt: mod,
		DownloadRef:        databaseID,
		ProviderMeta: map[string]any{
			"obj_type":         "notion_database",
			"database_id":      databaseID,
			"url":              valueAsString(dbObj["url"]),
			"has_child":        true,
			"last_edited_time": valueAsString(dbObj["last_edited_time"]),
		},
	}
}

func normalizeTargetType(raw string) string {
	return strings.TrimPrefix(strings.ToLower(strings.TrimSpace(raw)), "notion_")
}

func normalizeKind(kind string, meta map[string]any) string {
	kind = strings.ToLower(strings.TrimSpace(kind))
	if kind != "" {
		return kind
	}
	return strings.ToLower(strings.TrimSpace(stringOption(meta, "obj_type")))
}

func normalizeNotionTargetRef(raw string) string {
	raw = strings.Trim(strings.TrimSpace(raw), "<>")
	if raw == "" {
		return ""
	}
	if parsed, err := url.Parse(raw); err == nil {
		resolvedFromQuery := false
		for _, key := range []string{"page_id", "database_id", "block_id", "p"} {
			if value := strings.TrimSpace(parsed.Query().Get(key)); value != "" {
				raw = value
				resolvedFromQuery = true
				break
			}
		}
		if !resolvedFromQuery && strings.TrimSpace(parsed.Host) != "" && strings.TrimSpace(parsed.Path) != "" {
			parts := strings.Split(strings.Trim(parsed.Path, "/"), "/")
			if len(parts) > 0 {
				raw = parts[len(parts)-1]
			}
		}
	}
	raw = strings.TrimSuffix(raw, "?")
	matches := notionIDPattern.FindAllString(raw, -1)
	if len(matches) == 0 {
		return strings.ReplaceAll(raw, "-", "")
	}
	return strings.ReplaceAll(matches[len(matches)-1], "-", "")
}

func hasNotionChild(children []map[string]any) bool {
	for _, child := range children {
		switch strings.TrimSpace(valueAsString(child["type"])) {
		case "child_page", "child_database":
			return true
		}
	}
	return false
}

func pageTitle(pageObj map[string]any) string {
	props, _ := pageObj["properties"].(map[string]any)
	for _, value := range props {
		prop, _ := value.(map[string]any)
		if strings.TrimSpace(valueAsString(prop["type"])) == "title" {
			return richText(prop["title"])
		}
	}
	if title := richText(pageObj["title"]); title != "" {
		return title
	}
	return ""
}

func databaseTitle(dbObj map[string]any) string {
	return richText(dbObj["title"])
}

func richText(raw any) string {
	items, ok := raw.([]any)
	if !ok {
		return ""
	}
	parts := make([]string, 0, len(items))
	for _, item := range items {
		obj, _ := item.(map[string]any)
		text := strings.TrimSpace(valueAsString(obj["plain_text"]))
		if text == "" {
			textObj, _ := obj["text"].(map[string]any)
			text = strings.TrimSpace(valueAsString(textObj["content"]))
		}
		if text != "" {
			parts = append(parts, text)
		}
	}
	return strings.Join(parts, "")
}

func fileBlockURL(content map[string]any) string {
	for _, key := range []string{"external", "file"} {
		obj, _ := content[key].(map[string]any)
		if value := strings.TrimSpace(valueAsString(obj["url"])); value != "" {
			return value
		}
	}
	return ""
}

func parseNotionTime(raw string) *time.Time {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil
	}
	if t, err := time.Parse(time.RFC3339Nano, raw); err == nil {
		utc := t.UTC()
		return &utc
	}
	return nil
}

func markdownHeading(level int) string {
	if level < 1 {
		level = 1
	}
	if level > 6 {
		level = 6
	}
	return strings.Repeat("#", level)
}

func joinMarkdown(lines []string) string {
	out := make([]string, 0, len(lines))
	for _, line := range lines {
		line = strings.TrimRight(line, " \t")
		if strings.TrimSpace(line) == "" {
			continue
		}
		out = append(out, line)
	}
	return strings.Join(out, "\n\n")
}

func joinPath(parent, name string) string {
	parent = strings.Trim(strings.TrimSpace(parent), "/")
	name = strings.Trim(strings.TrimSpace(name), "/")
	switch {
	case parent == "" && name == "":
		return ""
	case parent == "":
		return name
	case name == "":
		return parent
	default:
		return path.Clean(parent + "/" + name)
	}
}

func valueAsString(v any) string {
	switch x := v.(type) {
	case string:
		return x
	case fmt.Stringer:
		return x.String()
	case json.Number:
		return x.String()
	case float64:
		return strconv.FormatFloat(x, 'f', -1, 64)
	case int:
		return strconv.Itoa(x)
	case int64:
		return strconv.FormatInt(x, 10)
	case bool:
		if x {
			return "true"
		}
		return "false"
	default:
		return ""
	}
}

func stringOption(m map[string]any, key string) string {
	if m == nil {
		return ""
	}
	return strings.TrimSpace(valueAsString(m[key]))
}

func boolOption(m map[string]any, key string) bool {
	if m == nil {
		return false
	}
	v, ok := m[key].(bool)
	return ok && v
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func cloneStringMap(in map[string]string) map[string]string {
	out := make(map[string]string, len(in))
	for k, v := range in {
		out[k] = v
	}
	return out
}

func cloneAnyMap(in map[string]any) map[string]any {
	out := make(map[string]any, len(in))
	for k, v := range in {
		out[k] = v
	}
	return out
}
