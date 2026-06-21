/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// @ant-design/icons поставляется без единого .d.ts для barrell-импорта
// (node_modules/@ant-design/icons/lib/index.d.ts отсутствует), поэтому
// именованные импорты иконок разрешаем как any.
declare module '@ant-design/icons';
