import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { invoke } from "@tauri-apps/api/core";
import { IconInfo, IconEye, IconEyeOff } from "../icons";
import type { EnvMap } from "../types";
import { envGet, envSet } from "../utils";

type EnvFieldProps = {
  envDraft: EnvMap;
  onEnvChange: (updater: (prev: EnvMap) => EnvMap) => void;
  busy?: string | null;
};

export function FieldText({
  k, label, placeholder, help, type,
  envDraft, onEnvChange, busy,
  secretShown, onToggleSecret,
}: EnvFieldProps & {
  k: string; label: string; placeholder?: string; help?: string; type?: "text" | "password";
  secretShown: Record<string, boolean>;
  onToggleSecret: (key: string) => void;
}) {
  const { t } = useTranslation();
  const isSecret = (type || "text") === "password";
  const shown = !!secretShown[k];
  return (
    <div className="field">
      <div className="labelRow">
        <div className="label">
          {label}
          {help && <span className="fieldTip" title={help}><IconInfo size={13} /></span>}
        </div>
        {k ? <div className="help">{k}</div> : null}
      </div>
      <div style={{ position: "relative" }}>
        <input
          value={envGet(envDraft, k)}
          onChange={(e) => onEnvChange((m) => envSet(m, k, e.target.value))}
          placeholder={placeholder}
          type={isSecret ? (shown ? "text" : "password") : "text"}
          style={isSecret ? { paddingRight: 44 } : undefined}
        />
        {isSecret && (
          <button type="button" className="btnEye"
            onClick={() => onToggleSecret(k)}
            disabled={!!busy}
            title={shown ? t("skills.hide") : t("skills.show")}>
            {shown ? <IconEyeOff size={16} /> : <IconEye size={16} />}
          </button>
        )}
      </div>
    </div>
  );
}

export function FieldBool({
  k, label, help, defaultValue,
  envDraft, onEnvChange,
}: EnvFieldProps & {
  k: string; label: string; help?: string; defaultValue?: boolean;
}) {
  const { t } = useTranslation();
  const v = envGet(envDraft, k, defaultValue ? "true" : "false").toLowerCase() === "true";
  return (
    <div className="field">
      <div className="labelRow">
        <div className="label">
          {label}
          {help && <span className="fieldTip" title={help}><IconInfo size={13} /></span>}
        </div>
        <div className="help">{k}</div>
      </div>
      <label className="pill" style={{ cursor: "pointer" }}>
        <input style={{ width: 16, height: 16 }} type="checkbox" checked={v}
          onChange={(e) => onEnvChange((m) => envSet(m, k, String(e.target.checked)))} />
        {t("skills.enabled")}
      </label>
    </div>
  );
}

export function FieldSelect({
  k, label, options, help,
  envDraft, onEnvChange,
}: EnvFieldProps & {
  k: string; label: string; options: { value: string; label: string }[]; help?: string;
}) {
  return (
    <div className="field">
      <div className="labelRow">
        <div className="label">
          {label}
          {help && <span className="fieldTip" title={help}><IconInfo size={13} /></span>}
        </div>
        {k ? <div className="help">{k}</div> : null}
      </div>
      <select
        value={envGet(envDraft, k)}
        onChange={(e) => onEnvChange((m) => envSet(m, k, e.target.value))}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </div>
  );
}

export function FieldCombo({
  k, label, options, placeholder, help,
  envDraft, onEnvChange,
}: EnvFieldProps & {
  k: string; label: string; options: { value: string; label: string }[]; placeholder?: string; help?: string;
}) {
  const { t } = useTranslation();
  const currentVal = envGet(envDraft, k);
  const isPreset = options.some((o) => o.value === currentVal);
  return (
    <div className="field">
      <div className="labelRow">
        <div className="label">
          {label}
          {help && <span className="fieldTip" title={help}><IconInfo size={13} /></span>}
        </div>
        {k ? <div className="help">{k}</div> : null}
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <select
          style={{ flex: "0 0 auto", minWidth: 140 }}
          value={isPreset ? currentVal : "__custom__"}
          onChange={(e) => {
            if (e.target.value !== "__custom__") {
              onEnvChange((m) => envSet(m, k, e.target.value));
            }
          }}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
          <option value="__custom__">{t("common.custom") || "自定义..."}</option>
        </select>
        {(!isPreset || currentVal === "") && (
          <input
            style={{ flex: 1 }}
            value={currentVal}
            onChange={(e) => onEnvChange((m) => envSet(m, k, e.target.value))}
            placeholder={placeholder || t("common.custom") || "自定义输入..."}
          />
        )}
      </div>
    </div>
  );
}

export function TelegramPairingCodeHint({ currentWorkspaceId }: { currentWorkspaceId: string | null }) {
  const { t } = useTranslation();
  const [currentCode, setCurrentCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadCode = useCallback(async () => {
    if (!currentWorkspaceId) return;
    setLoading(true);
    try {
      const code = await invoke<string>("workspace_read_file", {
        workspaceId: currentWorkspaceId,
        relativePath: "data/telegram/pairing/pairing_code.txt",
      });
      setCurrentCode(code.trim());
    } catch {
      setCurrentCode(null);
    } finally {
      setLoading(false);
    }
  }, [currentWorkspaceId]);

  useEffect(() => { loadCode(); }, [loadCode]);

  return (
    <div style={{
      fontSize: 12, color: "var(--text3, #666)", margin: "4px 0 0 0", lineHeight: 1.7,
      display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap",
    }}>
      <span>🔑 {t("config.imCurrentPairingCode")}：</span>
      {loading ? (
        <span style={{ opacity: 0.5 }}>...</span>
      ) : currentCode ? (
        <code style={{
          background: "var(--bg2, #f5f5f5)", padding: "2px 8px", borderRadius: 4,
          fontSize: 13, fontWeight: 600, letterSpacing: 2, userSelect: "all",
        }}>{currentCode}</code>
      ) : (
        <span style={{ opacity: 0.5 }}>{t("config.imPairingCodeNotGenerated")}</span>
      )}
      <button
        type="button"
        className="btnSmall"
        style={{ fontSize: 11, padding: "1px 8px" }}
        onClick={loadCode}
        disabled={loading}
      >↻ {t("common.refresh")}</button>
    </div>
  );
}
