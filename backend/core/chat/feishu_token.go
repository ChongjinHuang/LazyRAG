package chat

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"

	"lazymind/core/common"
)

const (
	_scanSourcesTimeout = 5 * time.Second
	_authTokenTimeout   = 5 * time.Second
	_feishuProvider     = "feishu"
	_notionProvider     = "notion"
	_cloudBindingActive = "active"
)

var _cloudToolProviders = []string{_feishuProvider, _notionProvider}

// _scanSourceItem is a minimal projection of the scan-control-plane Source model.
type _scanSourceItem struct {
	ID           string `json:"id"`
	SourceType   string `json:"source_type"`
	Status       string `json:"status"`
	CloudBinding *struct {
		AuthConnectionID string `json:"auth_connection_id"`
		Provider         string `json:"provider"`
		Status           string `json:"status"`
	} `json:"cloud_binding,omitempty"`
}

type _scanSourcesResponse struct {
	Items []_scanSourceItem `json:"items"`
}

// _authTokenResponse is a minimal projection of the auth-service token response.
type _authTokenResponse struct {
	Data struct {
		AccessToken string `json:"access_token"`
	} `json:"data"`
}

func authServiceInternalHeaders() map[string]string {
	headers := map[string]string{}
	if tok := strings.TrimSpace(os.Getenv("LAZYMIND_AUTH_SERVICE_INTERNAL_TOKEN")); tok != "" {
		headers["X-LazyMind-Internal-Token"] = tok
	}
	return headers
}

// fetchCloudToolConfig looks up active cloud sources for providers that can be
// used directly by chat tools, retrieves their tokens from auth-service, and
// returns a tool_config map accepted by the algorithm chat service.
func fetchCloudToolConfig(ctx context.Context, r *http.Request, userID string) (map[string]string, error) {
	fmt.Printf("[Core] [CLOUD_TOOL_TOKEN] fetchCloudToolConfig called userID=%q\n", userID)
	if strings.TrimSpace(userID) == "" {
		fmt.Printf("[Core] [CLOUD_TOOL_TOKEN] empty userID, skip\n")
		return nil, nil
	}

	scanURL := fmt.Sprintf("%s/api/scan/sources", common.ScanControlPlaneEndpoint())
	var sourcesResp _scanSourcesResponse
	err := common.ApiGet(
		ctx,
		scanURL,
		map[string]string{"X-User-Id": userID},
		&sourcesResp,
		_scanSourcesTimeout,
	)
	if err != nil {
		return nil, fmt.Errorf("list scan sources: %w", err)
	}

	connectionIDs := map[string]string{}
	for _, src := range sourcesResp.Items {
		cb := src.CloudBinding
		if cb == nil || strings.TrimSpace(cb.AuthConnectionID) == "" {
			continue
		}
		if !strings.EqualFold(cb.Status, _cloudBindingActive) {
			continue
		}
		provider := strings.ToLower(strings.TrimSpace(cb.Provider))
		if provider == "" || connectionIDs[provider] != "" {
			continue
		}
		connectionIDs[provider] = strings.TrimSpace(cb.AuthConnectionID)
	}

	toolConfig := map[string]string{}
	for _, provider := range _cloudToolProviders {
		connectionID := connectionIDs[provider]
		if connectionID == "" {
			fmt.Printf("[Core] [CLOUD_TOOL_TOKEN] no active %s binding found for userID=%q (total sources=%d)\n", provider, userID, len(sourcesResp.Items))
			continue
		}
		fmt.Printf("[Core] [CLOUD_TOOL_TOKEN] found provider=%q connectionID=%q for userID=%q\n", provider, connectionID, userID)
		tok, err := fetchCloudProviderToken(ctx, provider, connectionID)
		if err != nil {
			return nil, err
		}
		if tok != "" {
			toolConfig[provider] = tok
		}
	}
	if len(toolConfig) == 0 {
		return nil, nil
	}
	return toolConfig, nil
}

func fetchCloudProviderToken(ctx context.Context, provider, connectionID string) (string, error) {
	tokenURL := fmt.Sprintf(
		"%s/v1/cloud/connections/%s/token",
		common.AuthServiceBaseURL(),
		connectionID,
	)
	var tokenResp _authTokenResponse
	err := common.ApiGet(
		ctx,
		tokenURL,
		authServiceInternalHeaders(),
		&tokenResp,
		_authTokenTimeout,
	)
	if err != nil {
		return "", fmt.Errorf("fetch %s token for connection %s: %w", provider, connectionID, err)
	}

	tok := strings.TrimSpace(tokenResp.Data.AccessToken)
	fmt.Printf("[Core] [CLOUD_TOOL_TOKEN] got provider=%q token len=%d for connectionID=%q\n", provider, len(tok), connectionID)
	return tok, nil
}

// fetchFeishuToken keeps the old helper available for focused tests and callers
// while the chat path uses the generic cloud tool config fetcher.
func fetchFeishuToken(ctx context.Context, r *http.Request, userID string) (string, error) {
	tokens, err := fetchCloudToolConfig(ctx, r, userID)
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(tokens[_feishuProvider]), nil
}

func mergeToolConfig(reqBody map[string]any, toolConfig map[string]string) {
	if len(toolConfig) == 0 {
		return
	}
	merged := map[string]string{}
	if existing, ok := reqBody["tool_config"].(map[string]string); ok {
		for k, v := range existing {
			if strings.TrimSpace(k) != "" && strings.TrimSpace(v) != "" {
				merged[k] = v
			}
		}
	} else if existing, ok := reqBody["tool_config"].(map[string]any); ok {
		for k, v := range existing {
			if sv, ok := v.(string); ok && strings.TrimSpace(k) != "" && strings.TrimSpace(sv) != "" {
				merged[k] = sv
			}
		}
	}
	for k, v := range toolConfig {
		if strings.TrimSpace(k) != "" && strings.TrimSpace(v) != "" {
			merged[k] = v
		}
	}
	if len(merged) > 0 {
		reqBody["tool_config"] = merged
	}
}
