import { ActionIcon, Affix, Button, Transition, rem, useMantineColorScheme, useComputedColorScheme, Group } from "@mantine/core";
import { useWindowScroll } from "@mantine/hooks";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { logout } from "../lib/api/auth";
import { useSessionStore } from "../stores/session-store";
import { Logo } from "../components/logo";

const navigationItems = [
  { href: "/search", label: "搜索" },
  { href: "/downloads", label: "下载" },
  { href: "/library", label: "书库" },
  { href: "/settings", label: "设置" },
];

function IconArrowUp() {
  return <svg fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" height="1.5rem" width="1.5rem"><path d="M5 10l7-7 7 7M12 3v18" /></svg>;
}

function IconSun() {
  return <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" height="1.2rem" width="1.2rem"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" /></svg>;
}

function IconMoon() {
  return <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" height="1.2rem" width="1.2rem"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" /></svg>;
}

export function WebShell() {
  const navigate = useNavigate();
  const username = useSessionStore((state) => state.username);
  const clear = useSessionStore((state) => state.clear);
  const [scroll, scrollTo] = useWindowScroll();
  const { toggleColorScheme } = useMantineColorScheme();
  const computedColorScheme = useComputedColorScheme("dark", { getInitialValueInEffect: true });

  async function handleLogout() {
    try { await logout(); } finally { clear(); navigate("/login", { replace: true }); }
  }

  return (
    <div className="shell-layout">
      <header className="shell-header">
        <div className="shell-brand">
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <Logo size={36} style={{ color: "var(--accent)" }} />
            <div style={{ display: "flex", flexDirection: "column", lineHeight: "1.1" }}>
              <span style={{ fontSize: "20px", fontWeight: 900, color: "var(--text-primary)", letterSpacing: "-0.5px" }}>再漫画</span>
              <span style={{ fontSize: "9px", fontWeight: 600, opacity: 0.3, letterSpacing: "0.5px" }}>DESIGNED BY HUGO2233</span>
            </div>
          </div>
        </div>

        <nav className="shell-nav">
          {navigationItems.map((item) => (
            <NavLink key={item.href} className={({ isActive }) => `shell-link${isActive ? " active" : ""}`} to={item.href}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="shell-user">
          <Group gap="lg">
            <ActionIcon onClick={() => toggleColorScheme()} variant="subtle" color="gray" size="lg" radius="md">
              {computedColorScheme === "dark" ? <IconSun /> : <IconMoon />}
            </ActionIcon>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <span style={{ fontSize: "14px", fontWeight: 700, opacity: 0.8 }}>{username || "未登录"}</span>
              <Button variant="light" size="xs" radius="md" onClick={handleLogout} color="red" fw={700}>退出</Button>
            </div>
          </Group>
        </div>
      </header>

      <main className="shell-main">
        <Outlet />
      </main>

      <Affix position={{ bottom: rem(24), right: rem(24) }}>
        <Transition transition="slide-up" mounted={scroll.y > 100}>
          {(transitionStyles) => (
            <ActionIcon
              color="teal" size="xl" radius="xl" variant="filled"
              style={{ ...transitionStyles, boxShadow: "0 8px 24px rgba(16, 185, 129, 0.3)" }}
              onClick={() => scrollTo({ y: 0 })}
            >
              <IconArrowUp />
            </ActionIcon>
          )}
        </Transition>
      </Affix>
    </div>
  );
}
