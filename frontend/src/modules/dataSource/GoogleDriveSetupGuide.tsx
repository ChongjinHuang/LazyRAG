import { useRef } from "react";
import { Button, Typography } from "antd";
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import "./feishuSetupGuide.scss";

const { Paragraph, Text } = Typography;

const GOOGLE_CLOUD_CONSOLE_URL = "https://console.cloud.google.com/apis/dashboard";
const GOOGLE_DRIVE_API_URL = "https://console.cloud.google.com/apis/library/drive.googleapis.com";
const GOOGLE_CLOUD_CREDENTIALS_URL = "https://console.cloud.google.com/apis/credentials";
const GOOGLE_DRIVE_REDIRECT_URI = "http://localhost:8090/oauth/googledrive/data-source/callback";

type GuideStep = {
  title: string;
  description: string;
  details?: string[];
  linkLabel?: string;
  linkHref?: string;
};

function buildGuideSteps(t: TFunction): GuideStep[] {
  const stepKey = (key: string) => `admin.dataSourceGoogleDriveSetupGuide.steps.${key}`;
  return [
    {
      title: t(stepKey("openConsoleTitle")),
      description: t(stepKey("openConsoleDesc")),
      linkLabel: t("admin.dataSourceGoogleDriveSetupGuide.openConsole"),
      linkHref: GOOGLE_CLOUD_CONSOLE_URL,
    },
    {
      title: t(stepKey("enableApiTitle")),
      description: t(stepKey("enableApiDesc")),
      linkLabel: t("admin.dataSourceGoogleDriveSetupGuide.openDriveApi"),
      linkHref: GOOGLE_DRIVE_API_URL,
    },
    {
      title: t(stepKey("consentTitle")),
      description: t(stepKey("consentDesc")),
      details: [
        t(stepKey("consentUserType")),
        t(stepKey("consentTestUsers")),
        t(stepKey("consentScopes")),
      ],
    },
    {
      title: t(stepKey("credentialsTitle")),
      description: t(stepKey("credentialsDesc")),
      linkLabel: t("admin.dataSourceGoogleDriveSetupGuide.openCredentials"),
      linkHref: GOOGLE_CLOUD_CREDENTIALS_URL,
      details: [
        t(stepKey("credentialsType")),
        t(stepKey("credentialsName")),
      ],
    },
    {
      title: t(stepKey("redirectTitle")),
      description: t(stepKey("redirectDesc")),
      details: [
        t("admin.dataSourceGoogleDriveSetupGuide.callbackUrl", {
          uri: GOOGLE_DRIVE_REDIRECT_URI,
        }),
        t(stepKey("redirectOriginHint")),
      ],
    },
    {
      title: t(stepKey("copyCredentialsTitle")),
      description: t(stepKey("copyCredentialsDesc")),
      details: [
        t(stepKey("copyClientId")),
        t(stepKey("copyClientSecret")),
      ],
    },
    {
      title: t(stepKey("enterCredentialsTitle")),
      description: t(stepKey("enterCredentialsDesc")),
      details: [
        t(stepKey("enterCredentialsPath")),
        t(stepKey("enterCredentialsSave")),
      ],
    },
    {
      title: t(stepKey("finishTitle")),
      description: t(stepKey("finishDesc")),
      details: [
        t(stepKey("finishChat")),
        t(stepKey("finishNoIngestion")),
      ],
    },
  ];
}

export default function GoogleDriveSetupGuide() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const pageRef = useRef<HTMLDivElement | null>(null);
  const headerRef = useRef<HTMLElement | null>(null);
  const stepRefs = useRef<Array<HTMLElement | null>>([]);
  const orderedGuideSteps = buildGuideSteps(t);

  const scrollToStep = (index: number) => {
    const page = pageRef.current;
    const target = stepRefs.current[index];

    if (!page || !target) {
      return;
    }

    const pageRect = page.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const headerHeight = headerRef.current?.getBoundingClientRect().height || 0;

    page.scrollTo({
      top: page.scrollTop + targetRect.top - pageRect.top - headerHeight - 12,
      behavior: "smooth",
    });
  };

  return (
    <div className="feishu-setup-guide-page" ref={pageRef}>
      <header className="feishu-setup-guide-header" ref={headerRef}>
        <div>
          <Button
            type="link"
            icon={<ArrowLeftOutlined />}
            className="feishu-setup-guide-back"
            onClick={() => navigate("/model-providers/tools")}
          >
            {t("admin.dataSourceGoogleDriveSetupGuide.backTools")}
          </Button>
          <h1>{t("admin.dataSourceGoogleDriveSetupGuide.title")}</h1>
          <Paragraph className="feishu-setup-guide-subtitle">
            {t("admin.dataSourceGoogleDriveSetupGuide.subtitle")}
          </Paragraph>
        </div>
      </header>

      <main className="feishu-setup-guide-shell">
        <aside
          className="feishu-setup-guide-summary"
          aria-label={t("admin.dataSourceGoogleDriveSetupGuide.summaryAria")}
        >
          <Text strong>{t("admin.dataSourceGoogleDriveSetupGuide.summaryTitle")}</Text>
          <ol>
            {orderedGuideSteps.map((step, index) => (
              <li key={step.title}>
                <button type="button" onClick={() => scrollToStep(index)}>
                  {step.title}
                </button>
              </li>
            ))}
          </ol>
        </aside>

        <section className="feishu-setup-guide-content">
          {orderedGuideSteps.map((step, index) => (
            <article
              className="feishu-setup-guide-step"
              id={`google-drive-setup-step-${index + 1}`}
              key={step.title}
              ref={(node) => {
                stepRefs.current[index] = node;
              }}
            >
              <div className="feishu-setup-guide-step-copy">
                <span className="feishu-setup-guide-step-index">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div>
                  <h2>{step.title}</h2>
                  <Paragraph>
                    {"linkLabel" in step && step.linkLabel ? (
                      <>
                        <a
                          className="feishu-setup-guide-inline-link"
                          href={step.linkHref}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {step.linkLabel}
                        </a>
                        ，
                      </>
                    ) : null}
                    {step.description}
                  </Paragraph>
                  {"details" in step && step.details ? (
                    <ul className="feishu-setup-guide-step-details">
                      {step.details.map((detail) => (
                        <li key={detail}>{detail}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
                <CheckCircleOutlined className="feishu-setup-guide-step-icon" />
              </div>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
