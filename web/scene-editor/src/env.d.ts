/// <reference types="react" />
/// <reference types="react-dom" />
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SCENE_API_BASE_URL?: string;
  readonly [key: string]: string | boolean | undefined;
}
