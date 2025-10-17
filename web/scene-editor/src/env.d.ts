/// <reference types="react" />
/// <reference types="react-dom" />
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SCENE_API_BASE_URL?: string;
  readonly VITE_SCENE_EDITOR_ACTING_USER_ID?: string;
  readonly [key: string]: string | boolean | undefined;
}
