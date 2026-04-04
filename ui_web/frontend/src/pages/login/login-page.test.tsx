import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MantineProvider } from "@mantine/core";
import { createMemoryRouter, MemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, test, vi, beforeEach } from "vitest";
import type { ReactElement } from "react";
import "@mantine/core/styles.css";
import "../../styles/index.css";

import { login } from "../../lib/api/auth";
import { useSessionStore } from "../../stores/session-store";
import { LoginPage } from "./login-page";

function renderWithProviders(ui: ReactElement) {
  return render(
    <MantineProvider>
      <MemoryRouter>{ui}</MemoryRouter>
    </MantineProvider>,
  );
}

vi.mock("../../lib/api/auth", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api/auth")>("../../lib/api/auth");
  return {
    ...actual,
    login: vi.fn(),
  };
});

describe("LoginPage", () => {
  beforeEach(() => {
    vi.mocked(login).mockClear();
    useSessionStore.setState({
      username: "",
      loggedIn: false,
      rememberPassword: false,
      rememberedPassword: "",
      hydrated: true,
    });
  });
  test("submits credentials to login handler", async () => {
    const user = userEvent.setup();
    const onLogin = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(<LoginPage onLogin={onLogin} pending={false} errorMessage="" />);

    await user.type(screen.getByLabelText("用户名"), "hugo");
    await user.type(screen.getByLabelText("密码"), "secret");
    await user.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => {
      expect(onLogin).toHaveBeenCalledWith({
        username: "hugo",
        password: "secret",
        remember_password: false,
      });
    });
  });

  test("renders Web UI eyebrow", () => {
    renderWithProviders(<LoginPage onLogin={vi.fn()} pending={false} errorMessage="" />);

    // SVG 不包含 role="img" 和 accessible name，我们直接查包含 "Web UI" 的元素或检查其他部分
    expect(screen.getByText("Web UI")).toBeInTheDocument();
  });

  test("renders console headline", () => {
    renderWithProviders(<LoginPage onLogin={vi.fn()} pending={false} errorMessage="" />);

    expect(screen.getByText("连接到 Web 控制台")).toBeInTheDocument();
  });

  test("renders remember password label without helper copy", () => {
    renderWithProviders(<LoginPage onLogin={vi.fn()} pending={false} errorMessage="" />);

    expect(screen.getByLabelText("记住密码")).toBeInTheDocument();
    expect(
      screen.queryByText("用户名可保存在当前浏览器，密码由浏览器或系统自动填充。"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("控制台入口在线，等待账号校验与会话接入。"),
    ).not.toBeInTheDocument();
  });

  test("renders legacy login subtitle", () => {
    renderWithProviders(<LoginPage onLogin={vi.fn()} pending={false} errorMessage="" />);

    expect(screen.getByText("登录后可直接搜索、查看最近更新并管理本地书库。")).toBeInTheDocument();
  });

  test("toggles password visibility button", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    const passwordField = screen.getByLabelText("密码") as HTMLInputElement;
    expect(passwordField.type).toBe("password");

    const showToggle = screen.getByRole("button", { name: "显示密码" });
    await user.click(showToggle);

    expect(passwordField.type).toBe("text");
    expect(screen.getByRole("button", { name: "隐藏密码" })).toBeInTheDocument();

    const hideToggle = screen.getByRole("button", { name: "隐藏密码" });
    await user.click(hideToggle);
    expect(passwordField.type).toBe("password");
  });

  test("keeps password field chrome on wrapper instead of inner input", () => {
    renderWithProviders(<LoginPage />);

    const passwordField = screen.getByLabelText("密码") as HTMLInputElement;
    expect(passwordField).toHaveClass("login-form__control-inner");
    expect(passwordField).not.toHaveClass("login-form__control");
    expect(getComputedStyle(passwordField).borderTopWidth).toBe("0px");
    expect(getComputedStyle(passwordField).borderTopStyle).toBe("none");

    const passwordShell = passwordField.closest(".login-form__control");
    expect(passwordShell).not.toBeNull();
    expect(getComputedStyle(passwordShell as HTMLElement).borderTopWidth).toBe("1px");
  });

  test("theme toggle button updates title", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    const toggleButton = screen.getByRole("button", { name: "切换主题" });
    const firstTitle = toggleButton.getAttribute("title");
    expect(firstTitle).toMatch(/切换到(浅色|深色)模式/);

    await user.click(toggleButton);

    const secondTitle = screen.getByRole("button", { name: "切换主题" }).getAttribute("title");
    expect(secondTitle).not.toBe(firstTitle);
    expect(secondTitle).toBe(
      firstTitle === "切换到深色模式" ? "切换到浅色模式" : "切换到深色模式",
    );
  });

  test("redirects back to requested route after successful login", async () => {
    const user = userEvent.setup();
    vi.mocked(login).mockResolvedValue({
      username: "hugo",
      logged_in: true,
      remember_password: false,
      remembered_password: "",
    });
    useSessionStore.setState({
      username: "",
      loggedIn: false,
      hydrated: true,
    });

    const router = createMemoryRouter(
      [
        { path: "/login", element: <LoginPage /> },
        { path: "/downloads", element: <div>下载页</div> },
        { path: "/search", element: <div>搜索页</div> },
      ],
      {
        initialEntries: [
          {
            pathname: "/login",
            state: { from: "/downloads" },
          },
        ],
      },
    );

    render(
      <MantineProvider>
        <RouterProvider router={router} />
      </MantineProvider>,
    );

    await user.type(screen.getByLabelText("用户名"), "hugo");
    await user.type(screen.getByLabelText("密码"), "secret");
    await user.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => {
      expect(screen.getByText("下载页")).toBeInTheDocument();
    });

    expect(useSessionStore.getState().loggedIn).toBe(true);
  });

  test("falls back to /search when no prior route", async () => {
    const user = userEvent.setup();
    vi.mocked(login).mockResolvedValue({
      username: "hugo",
      logged_in: true,
      remember_password: false,
      remembered_password: "",
    });
    useSessionStore.setState({
      username: "",
      loggedIn: false,
      hydrated: true,
    });

    const router = createMemoryRouter(
      [
        { path: "/login", element: <LoginPage /> },
        { path: "/search", element: <div>搜索页</div> },
      ],
      {
        initialEntries: ["/login"],
      },
    );

    render(
      <MantineProvider>
        <RouterProvider router={router} />
      </MantineProvider>,
    );

    await user.type(screen.getByLabelText("用户名"), "hugo");
    await user.type(screen.getByLabelText("密码"), "secret");
    await user.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => {
      expect(screen.getByText("搜索页")).toBeInTheDocument();
    });

    expect(useSessionStore.getState().loggedIn).toBe(true);
  });

  test("ignores external return path and falls back to /search", async () => {
    const user = userEvent.setup();
    vi.mocked(login).mockResolvedValue({
      username: "hugo",
      logged_in: true,
      remember_password: false,
      remembered_password: "",
    });
    useSessionStore.setState({
      username: "",
      loggedIn: false,
      hydrated: true,
    });

    const router = createMemoryRouter(
      [
        { path: "/login", element: <LoginPage /> },
        { path: "/search", element: <div>搜索页</div> },
      ],
      {
        initialEntries: [
          {
            pathname: "/login",
            state: { from: "https://example.com/malicious" },
          },
        ],
      },
    );

    render(
      <MantineProvider>
        <RouterProvider router={router} />
      </MantineProvider>,
    );

    await user.type(screen.getByLabelText("用户名"), "hugo");
    await user.type(screen.getByLabelText("密码"), "secret");
    await user.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => {
      expect(screen.getByText("搜索页")).toBeInTheDocument();
    });
  });
  test("prefills username and password from remembered session state", () => {
    const remembered = "remembered-user";
    useSessionStore.setState({
      username: remembered,
      loggedIn: false,
      rememberPassword: true,
      rememberedPassword: "secret",
      hydrated: true,
    });
    renderWithProviders(<LoginPage onLogin={vi.fn()} pending={false} errorMessage="" />);

    expect(screen.getByLabelText("用户名")).toHaveValue(remembered);
    expect(screen.getByLabelText("密码")).toHaveValue("secret");
    expect(screen.getByLabelText("记住密码")).toBeChecked();
  });
  test("real login path sends remember password flag when enabled", async () => {
    const user = userEvent.setup();
    vi.mocked(login).mockResolvedValue({
      username: "hugo",
      logged_in: true,
      remember_password: true,
      remembered_password: "secret",
    });
    useSessionStore.setState({
      username: "",
      loggedIn: false,
      rememberPassword: false,
      rememberedPassword: "",
      hydrated: true,
    });

    renderWithProviders(<LoginPage />);

    await user.type(screen.getByLabelText("用户名"), "hugo");
    await user.type(screen.getByLabelText("密码"), "secret");
    const rememberCheckbox = screen.getByRole("checkbox", { name: "记住密码" }) as HTMLInputElement;
    if (!rememberCheckbox.checked) {
      await user.click(rememberCheckbox);
    }
    await user.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith({
        username: "hugo",
        password: "secret",
        remember_password: true,
      });
    });
  });
  test("external login path receives remember password flag", async () => {
    const user = userEvent.setup();
    const onLogin = vi.fn().mockResolvedValue(undefined);
    const typedUsername = "remembered-user";
    renderWithProviders(<LoginPage onLogin={onLogin} pending={false} errorMessage="" />);

    await user.type(screen.getByLabelText("用户名"), typedUsername);
    await user.type(screen.getByLabelText("密码"), "secret");
    const rememberCheckbox = screen.getByRole("checkbox", { name: "记住密码" }) as HTMLInputElement;
    if (!rememberCheckbox.checked) {
      await user.click(rememberCheckbox);
    }
    await user.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => {
      expect(onLogin).toHaveBeenCalledWith({
        username: typedUsername,
        password: "secret",
        remember_password: true,
      });
    });
  });
  test("real login path sends remember password false when disabled", async () => {
    const user = userEvent.setup();
    vi.mocked(login).mockResolvedValue({
      username: "legacy-user",
      logged_in: true,
      remember_password: false,
      remembered_password: "",
    });
    useSessionStore.setState({
      username: "legacy-user",
      loggedIn: false,
      rememberPassword: true,
      rememberedPassword: "old-secret",
      hydrated: true,
    });
    renderWithProviders(<LoginPage pending={false} errorMessage="" />);

    const rememberCheckbox = screen.getByRole("checkbox", { name: "记住密码" }) as HTMLInputElement;
    expect(rememberCheckbox).toBeChecked();
    await user.click(rememberCheckbox);
    await user.clear(screen.getByLabelText("用户名"));
    await user.type(screen.getByLabelText("用户名"), "new-user");
    await user.clear(screen.getByLabelText("密码"));
    await user.type(screen.getByLabelText("密码"), "secret");
    await user.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith({
        username: "new-user",
        password: "secret",
        remember_password: false,
      });
    });
  });
});
