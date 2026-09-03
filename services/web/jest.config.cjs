// Configuration Jest du front React. Le projet est en ESM ("type": "module") :
// la transformation passe par babel-jest avec une config inline
// (configFile: false) pour ne pas interferer avec le babel qu'utilise
// @vitejs/plugin-react au build. Le typage des tests est verifie a part par
// tsconfig.test.json (npm run typecheck:test).
//
// Le plugin babel local reecrit `import.meta.env` (Vite) en `process.env`, que
// Babel ne sait pas parser en CommonJS. `<rootDir>` n'est pas interpole dans les
// options passees a babel-jest, d'ou le chemin construit avec __dirname.
/** @type {import('jest').Config} */
module.exports = {
  testEnvironment: 'jsdom',
  roots: ['<rootDir>/src', '<rootDir>/tests'],
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],
  testMatch: ['**/*.(test|spec).(ts|tsx)'],
  moduleNameMapper: {
    // Les imports de styles et d'assets ne sont pas resolus par Jest.
    '\\.(css|less|sass|scss)$': 'identity-obj-proxy',
    '\\.(png|jpe?g|gif|webp|avif|svg)$': '<rootDir>/tests/__mocks__/fileMock.cjs',
  },
  transform: {
    '^.+\\.(ts|tsx|js|jsx)$': [
      'babel-jest',
      {
        babelrc: false,
        configFile: false,
        presets: [
          ['@babel/preset-env', { targets: { node: 'current' } }],
          ['@babel/preset-react', { runtime: 'automatic' }],
          '@babel/preset-typescript',
        ],
        plugins: [`${__dirname}/tests/babel-plugin-import-meta-env.cjs`],
      },
    ],
  },
  clearMocks: true,
  collectCoverageFrom: ['src/**/*.{ts,tsx}', '!src/**/*.d.ts', '!src/main.tsx'],
}
