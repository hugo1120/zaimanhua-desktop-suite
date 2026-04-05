/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BACKEND_ORIGIN?: string;
}

declare const __ZAIMANHUA_BACKEND_ORIGIN__: string | undefined;

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
