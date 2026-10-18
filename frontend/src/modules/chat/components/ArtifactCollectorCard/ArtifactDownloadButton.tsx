import { Button, Tooltip } from "antd";
import { FileTextOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";

import { useTaskCenterStore, type ConversationArtifact } from "@/modules/chat/store/taskCenter";
import { openConversationArtifactPanel } from "@/modules/chat/constants/chat";

const EMPTY_ARTIFACTS: ConversationArtifact[] = [];

interface Props {
  sessionId: string;
  historyId?: string;
  currentExportIds?: string[];
}

export default function ArtifactDownloadButton({ sessionId, historyId, currentExportIds }: Props) {
  void currentExportIds;
  const { t } = useTranslation();
  const artifacts = useTaskCenterStore((state) =>
    sessionId ? (state.artifactsByConversation[sessionId] ?? EMPTY_ARTIFACTS) : EMPTY_ARTIFACTS,
  );

  if (!sessionId || !historyId || artifacts.length === 0) return null;
  const currentArtifacts = artifacts.filter((artifact) => artifact.history_id === historyId);
  const label = currentArtifacts.length === 1
    ? currentArtifacts[0].filename || currentArtifacts[0].name || currentArtifacts[0].slot
    : `${t("chat.artifactPanelPublished")} (${currentArtifacts.length || artifacts.length})`;

  return (
    <Tooltip title={t("chat.artifactPanelOpenMenu")}>
      <Button
        className="tool-btn"
        icon={<FileTextOutlined />}
        aria-label={t("chat.artifactPanelOpenMenu")}
        onClick={() => openConversationArtifactPanel({ conversationId: sessionId })}
      >{label}</Button>
    </Tooltip>
  );
}
