interface ImportMetaEnv {
  readonly VITE_SCENE_API_BASE_URL?: string;
  readonly [key: string]: string | undefined;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
