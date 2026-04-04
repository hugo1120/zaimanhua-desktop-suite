import { useState, type FormEvent } from "react";

import {
  ActionIcon,
  Button,
  Checkbox,
  PasswordInput,
  TextInput,
  useComputedColorScheme,
  useMantineColorScheme,
} from "@mantine/core";
import { useLocation, useNavigate } from "react-router-dom";

import type { LoginRequest } from "../../lib/api/contracts";
import { login } from "../../lib/api/auth";
import { emitDesktopLog } from "../../lib/desktop-debug";
import { ApiError } from "../../lib/api/http";
import { useSessionStore } from "../../stores/session-store";
import { Logo } from "../../components/logo";

const SunIcon = (
  <svg
    viewBox="0 0 24 24"
    width="20"
    height="20"
    strokeWidth="1.5"
    stroke="currentColor"
    fill="none"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="12" cy="12" r="5" />
    <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
  </svg>
);

const MoonIcon = (
  <svg
    viewBox="0 0 24 24"
    width="20"
    height="20"
    strokeWidth="1.5"
    stroke="currentColor"
    fill="none"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M21 12.79A9 9 0 1111.21 3a7 7 0 009.79 9.79Z" />
  </svg>
);

interface LoginPageProps {
  onLogin?(request: LoginRequest): Promise<void>;
  pending?: boolean;
  errorMessage?: string;
}

export function LoginPage(props: LoginPageProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useSessionStore((state) => state.setSession);
  const storedUsername = useSessionStore((state) => state.username);
  const storedRememberedPassword = useSessionStore((state) => state.rememberedPassword);
  const storedRememberPassword = useSessionStore((state) => state.rememberPassword);
  const [username, setUsername] = useState(storedUsername);
  const [password, setPassword] = useState(storedRememberedPassword);
  const [rememberPassword, setRememberPassword] = useState(storedRememberPassword);
  const [internalPending, setInternalPending] = useState(false);
  const [internalError, setInternalError] = useState("");
  const [passwordVisible, setPasswordVisible] = useState(false);
  const { toggleColorScheme } = useMantineColorScheme();
  const computedColorScheme = useComputedColorScheme("dark", { getInitialValueInEffect: true });
  const isDarkMode = computedColorScheme === "dark";

  const pending = props.pending ?? internalPending;
  const errorMessage = props.errorMessage ?? internalError;

  async function submitLogin(request: LoginRequest) {
    emitDesktopLog("frontend.login", "submit_start", {
      username: request.username,
      rememberPassword,
    });

    if (props.onLogin) {
      await props.onLogin(request);
      emitDesktopLog("frontend.login", "submit_success_external", {
        username: request.username,
        rememberPassword,
      });
      return;
    }

    setInternalPending(true);
    setInternalError("");
    try {
      const session = await login(request);
      setSession({
        username: session.username,
        loggedIn: session.logged_in,
        rememberPassword: session.remember_password,
        rememberedPassword: session.remembered_password,
      });
      const returnPath = resolveReturnPath(location.state);
      emitDesktopLog("frontend.login", "navigate_after_login", {
        returnPath,
        username: session.username,
      });
      navigate(returnPath, { replace: true });
    } catch (error) {
      emitDesktopLog("frontend.login", "submit_failed", {
        username: request.username,
        error: error instanceof Error ? error.message : String(error),
      });
      if (error instanceof ApiError) {
      setInternalError(error.message);
      } else {
        setInternalError("登录失败");
      }
    } finally {
      setInternalPending(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitLogin({
      username: username.trim(),
      password,
      remember_password: rememberPassword,
    });
  }

  return (
    <div className="login-screen">
      <div className="login-screen__grid" aria-hidden="true" />
      <div className="login-screen__glow login-screen__glow--primary" aria-hidden="true" />
      <div className="login-screen__glow login-screen__glow--secondary" aria-hidden="true" />
      <div className="login-panel">
        <div className="login-panel__header">
          <div className="login-panel__brand">
            <div className="login-panel__logo-shell">
              <Logo className="login-panel__logo" size={48} />
            </div>
            <div className="login-panel__brand-copy">
              <div className="login-eyebrow">Web UI</div>
              <h1 className="login-title">连接到 Web 控制台</h1>
              <p className="login-subtitle">登录后可直接搜索、查看最近更新并管理本地书库。</p>
            </div>
          </div>
          <ActionIcon
            className="login-panel__theme-toggle"
            aria-label="切换主题"
            title={isDarkMode ? "切换到浅色模式" : "切换到深色模式"}
            variant="outline"
            size="lg"
            onClick={() => toggleColorScheme()}
          >
            {isDarkMode ? SunIcon : MoonIcon}
          </ActionIcon>
        </div>
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="login-form__field">
            <TextInput
              classNames={{
                input: "login-form__control",
              }}
              label="用户名"
              value={username}
              onChange={(event) => setUsername(event.currentTarget.value)}
              autoComplete="username"
            />
          </div>
          <div className="login-form__field">
            <PasswordInput
              classNames={{
                input: "login-form__control",
                innerInput: "login-form__control-inner",
                visibilityToggle: "login-form__visibility-toggle",
              }}
              label="密码"
              value={password}
              onChange={(event) => setPassword(event.currentTarget.value)}
              autoComplete="current-password"
              visible={passwordVisible}
              onVisibilityChange={setPasswordVisible}
              visibilityToggleButtonProps={{
                "aria-label": passwordVisible ? "隐藏密码" : "显示密码",
              }}
            />
          </div>
          <div className="login-form__meta">
            <Checkbox
              label="记住密码"
              checked={rememberPassword}
              onChange={(event) => setRememberPassword(event.currentTarget.checked)}
              size="sm"
            />
          </div>
          {errorMessage ? <div className="login-error">{errorMessage}</div> : null}
          <Button className="login-form__submit" type="submit" loading={pending}>
            登录
          </Button>
        </form>
      </div>
    </div>
  );
}

function resolveReturnPath(state: unknown) {
  if (state && typeof state === "object") {
    const candidate = (state as { from?: unknown }).from;
    if (typeof candidate === "string") {
      const normalizedPath = candidate.trim();
      if (
        normalizedPath.length > 0 &&
        normalizedPath.startsWith("/") &&
        !normalizedPath.startsWith("//")
      ) {
        return normalizedPath;
      }
    }
  }
  return "/search";
}
