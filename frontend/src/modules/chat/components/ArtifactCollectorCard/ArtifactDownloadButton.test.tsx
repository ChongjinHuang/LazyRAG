import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { CHAT_OPEN_ARTIFACT_PANEL_EVENT } from '@/modules/chat/constants/chat';
import ArtifactDownloadButton from './ArtifactDownloadButton';

vi.mock('@/modules/chat/store/taskCenter', () => ({
  useTaskCenterStore: (selector: (state: {
    artifactsByConversation: Record<string, Array<{ artifact_id: string; history_id: string; filename: string }>>;
  }) => unknown) => selector({
    artifactsByConversation: { 'conv-1': [{ artifact_id: 'artifact-1', history_id: 'turn-1', filename: '出差申请审批流程图.html' }] },
  }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock('antd', () => ({
  Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button type="button" {...props}>{children}</button>
  ),
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe('ArtifactDownloadButton', () => {
  it('opens the conversation files drawer instead of a batch-download popover', () => {
    const open = vi.fn();
    window.addEventListener(CHAT_OPEN_ARTIFACT_PANEL_EVENT, open);
    render(<ArtifactDownloadButton sessionId="conv-1" historyId="turn-1" />);

    expect(screen.getByRole('button', { name: 'chat.artifactPanelOpenMenu' }))
      .toHaveTextContent('出差申请审批流程图.html');

    fireEvent.click(screen.getByRole('button'));

    expect(open).toHaveBeenCalledWith(expect.objectContaining({
      detail: { conversationId: 'conv-1' },
    }));
    window.removeEventListener(CHAT_OPEN_ARTIFACT_PANEL_EVENT, open);
  });
});
